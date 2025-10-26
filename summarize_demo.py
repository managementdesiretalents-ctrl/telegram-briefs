import sqlite3, textwrap
from datetime import datetime, timedelta, timezone

DB="briefs.db"
NOW_UTC=datetime.now(timezone.utc)
SINCE=NOW_UTC - timedelta(days=1)  # last 24h for this demo

FILLER = {"ok","okay","k","kk","thanks","thx","thank you","👍","👌","yo","hey","hi","hello","lol","haha","hahaha"}

def is_signal(t: str)->bool:
    s=t.strip().lower()
    if not s: return False
    if s in FILLER: return False
    if len(s)<3: return False
    return True

con=sqlite3.connect(DB)
cur=con.cursor()
rows=cur.execute("""
  SELECT ts_utc, from_me, text
  FROM messages
  WHERE peer_id=? AND ts_utc >= ?
  ORDER BY ts_utc ASC
""",(7740422022, SINCE.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchall()
con.close()

signals=[]
for ts, me, txt in rows:
    if not txt: continue
    if is_signal(txt):
        who="YOU" if me==1 else "THEM"
        signals.append(f"{who}: {txt.strip()}")

# keep it short
signals=signals[-20:]

title=f"Daily summary for William — last 24h ({SINCE.strftime('%Y-%m-%d %H:%M')}Z → {NOW_UTC.strftime('%Y-%m-%d %H:%M')}Z)"
body = "\n".join(f"- {s[:180]}" for s in signals)

# hard cap ~250 words
words=(title+" "+body).split()
if len(words)>250:
    words=words[:250]+["…"]
    clipped=" ".join(words)
    # reformat bullets
    lines=["- "+l for l in clipped.split(" - ")[1:]]
    body="\n".join(lines)
print(title)
print(body if body else "- No significant messages in the last 24 hours.")
