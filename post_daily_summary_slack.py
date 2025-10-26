import os, sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()
DB="briefs.db"
PEER_ID=7740422022
OPENAI_KEY=os.getenv("OPENAI_API_KEY")
SLACK_BOT=os.getenv("SLACK_BOT_TOKEN")
CHANNEL_NAME=os.getenv("SLACK_CHANNEL_NAME")
assert OPENAI_KEY, "Missing OPENAI_API_KEY in .env"
assert SLACK_BOT, "Missing SLACK_BOT_TOKEN in .env"
assert CHANNEL_NAME, "Missing SLACK_CHANNEL_NAME in .env"

client_ai = OpenAI(api_key=OPENAI_KEY)
slack = WebClient(token=SLACK_BOT)

# Summaries table (stores Slack ts)
con = sqlite3.connect(DB)
con.execute("""
CREATE TABLE IF NOT EXISTS summaries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  posted_utc TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  date_label TEXT NOT NULL,
  text TEXT NOT NULL
);
""")
con.commit()

# Brisbane local day (midnight -> now)
tz = ZoneInfo("Australia/Brisbane")
now_local = datetime.now(tz)
start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
start_utc = start_local.astimezone(timezone.utc)
date_au = f"{int(now_local.strftime('%d'))}/{int(now_local.strftime('%m'))}/{now_local.strftime('%y')}"

# Load today's messages
rows = con.execute("""
  SELECT ts_utc, from_me, text
  FROM messages
  WHERE peer_id=? AND ts_utc >= ?
  ORDER BY ts_utc ASC
""",(PEER_ID, start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchall()

def clean(t:str)->str:
    return " ".join(((t or "").replace("\n"," ").replace("\r"," ")).split())

if not rows:
    summary = f"Date: {date_au}\n\n- No significant messages today.\n\nAny privates/ calls?\n- None mentioned."
else:
    lines=[]
    call_lines=[]
    CALL_KEYS=("call","private","cb","chaturbate","stream","record","book","booked","confirm","confirmed",
               "resched","reschedule","cancel","canceled","time","am","pm","o'clock","tomorrow","today",
               "makeup","no makeup","natural","surprise")
    for ts, me, txt in rows:
        who = "SHE" if me==1 else "HE"
        s = f"{ts} — {who}: {clean(txt)}"
        lines.append(s)
        low = s.lower()
        if any(k in low for k in CALL_KEYS):
            call_lines.append(s)

    chat_snippet = "\n".join(lines[-400:])
    call_snippet  = "\n".join(call_lines[-200:]) if call_lines else "(none)"

    # Style guide (your exact format)
    style = open("summary_style.txt","r",encoding="utf-8").read().replace("{date_au}", date_au)

    resp = client_ai.chat.completions.create(
      model="gpt-4o-mini",
      messages=[
        {"role":"system","content":style},
        {"role":"user","content":f"Here are today's messages (UTC):\n\n{chat_snippet}\n\nCall-related lines only (filtered):\n{call_snippet}\n\nWrite the report now, following the layout and rules exactly."}
      ],
      temperature=0.2,
    )
    summary = resp.choices[0].message.content.strip()

    # shrink if > 250 words
    if len(summary.split()) > 250:
        resp2 = client_ai.chat.completions.create(
          model="gpt-4o-mini",
          messages=[
            {"role":"system","content":"Shorten to ≤250 words. Keep EXACT same format and meaning."},
            {"role":"user","content":summary}
          ],
          temperature=0.0
        )
        summary = resp2.choices[0].message.content.strip()

# Find channel ID by name
chan_id = None
cursor = None
while True:
    res = slack.conversations_list(limit=1000, cursor=cursor, types="public_channel,private_channel")
    for ch in res["channels"]:
        if ch.get("name") == CHANNEL_NAME:
            chan_id = ch["id"]; break
    if chan_id or not res.get("response_metadata", {}).get("next_cursor"):
        break
    cursor = res["response_metadata"]["next_cursor"]
if not chan_id:
    raise SystemExit(f"Could not find channel named #{CHANNEL_NAME}. Invite the bot to the channel and retry.")

# Try join (no-op if already a member)
try:
    slack.conversations_join(channel=chan_id)
except SlackApiError:
    pass

# Post and store ts
try:
    res = slack.chat_postMessage(channel=chan_id, text=summary)
except SlackApiError as e:
    raise SystemExit(f"Slack post failed: {e.response['error']}")
ts = res["ts"]
con.execute(
    "INSERT INTO summaries(posted_utc, channel_id, ts, date_label, text) VALUES (?,?,?,?,?)",
    (datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), chan_id, ts, date_au, summary)
)
con.commit(); con.close()
print(f"Posted to Slack. Channel={chan_id} ts={ts}")
