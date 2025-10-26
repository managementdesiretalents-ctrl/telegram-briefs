import os, sqlite3, requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DB="briefs.db"
PEER_ID=7740422022
WEBHOOK=os.getenv("SLACK_WEBHOOK_URL")
OPENAI_KEY=os.getenv("OPENAI_API_KEY")
assert WEBHOOK, "Missing SLACK_WEBHOOK_URL in .env"
assert OPENAI_KEY, "Missing OPENAI_API_KEY in .env"

client = OpenAI(api_key=OPENAI_KEY)

# Brisbane local day (midnight -> now)
tz = ZoneInfo("Australia/Brisbane")
now_local = datetime.now(tz)
start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
start_utc = start_local.astimezone(timezone.utc)
date_au = f"{int(now_local.strftime('%d'))}/{int(now_local.strftime('%m'))}/{now_local.strftime('%y')}"

# Load today's messages
con = sqlite3.connect(DB)
rows = con.execute("""
  SELECT ts_utc, from_me, text
  FROM messages
  WHERE peer_id=? AND ts_utc >= ?
  ORDER BY ts_utc ASC
""",(PEER_ID, start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchall()
con.close()

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
    style = open("summary_style.txt","r",encoding="utf-8").read().replace("{date_au}", date_au)

    resp = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=[
        {"role":"system","content":style},
        {"role":"user","content":f"Here are today's messages (UTC):\n\n{chat_snippet}\n\nCall-related lines only (filtered):\n{call_snippet}\n\nWrite the report now, following the layout and rules exactly."}
      ],
      temperature=0.2,
    )
    summary = resp.choices[0].message.content.strip()

    # Guardrail: shrink if over 250 words
    if len(summary.split()) > 250:
        resp2 = client.chat.completions.create(
          model="gpt-4o-mini",
          messages=[
            {"role":"system","content":"Shorten to ≤250 words. Keep EXACT same format and meaning."},
            {"role":"user","content":summary}
          ],
          temperature=0.0
        )
        summary = resp2.choices[0].message.content.strip()

r = requests.post(WEBHOOK, json={"text": summary})
if r.status_code != 200:
    raise SystemExit(f"Slack webhook error: {r.status_code} {r.text}")
print("Posted to Slack.")
