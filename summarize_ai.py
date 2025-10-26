import os, sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DB="briefs.db"
PEER_ID=7740422022
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Brisbane local day (midnight -> now)
tz = ZoneInfo("Australia/Brisbane")
now_local = datetime.now(tz)
start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
start_utc = start_local.astimezone(timezone.utc)

# Date like 2/10/25 (no leading zeros on D/M)
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
    print(f"Date: {date_au}\n\n- No significant messages today.\n\nAny privates/ calls?\n- None mentioned.")
    raise SystemExit(0)

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

chat_snippet = "\n".join(lines[-400:])       # general context
call_snippet = "\n".join(call_lines[-200:])  # call-related hints

# Load style and inject date
style = open("summary_style.txt","r",encoding="utf-8").read().replace("{date_au}", date_au)

messages = [
  {"role":"system","content":style},
  {"role":"user","content":f"""Here are today's messages (UTC):

{chat_snippet}

Call-related lines only (filtered):
{call_snippet if call_snippet else "(none)"}

Write the report now, following the layout and rules exactly.
"""}]

resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, temperature=0.2)
out = resp.choices[0].message.content.strip()

# Guardrail: if >250 words, ask the model to shorten without changing meaning/format.
def word_count(s:str)->int: return len(s.split())
if word_count(out) > 250:
    resp2 = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=[
        {"role":"system","content":"Shorten to ≤250 words. Keep EXACT same format and meaning."},
        {"role":"user","content":out}
      ],
      temperature=0.0
    )
    out = resp2.choices[0].message.content.strip()

print(out)
