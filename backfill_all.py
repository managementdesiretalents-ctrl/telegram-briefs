import os, sqlite3, time
from telethon.sync import TelegramClient
from dotenv import load_dotenv

load_dotenv()
api_id   = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone    = os.getenv("PHONE_NUMBER")
peer_id  = int(os.getenv("PEER_ID"))
session  = os.getenv("SESSION_NAME","telegram_briefs")

# DB
db = sqlite3.connect("briefs.db")
db.execute("PRAGMA journal_mode=WAL;")
db.execute("""
CREATE TABLE IF NOT EXISTS messages(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  peer_id  INTEGER NOT NULL,
  msg_id   INTEGER NOT NULL,
  ts_utc   TEXT    NOT NULL,
  from_me  INTEGER NOT NULL,
  text     TEXT
);
""")
db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_peer_msg ON messages(peer_id,msg_id);")

with TelegramClient(session, api_id, api_hash) as client:
  client.start(phone=phone)

  # find dialog by peer_id (safe)
  target = None
  for d in client.iter_dialogs():
    if getattr(d.entity, "id", None) == peer_id:
      target = d.entity
      break
  if not target:
    raise SystemExit("Open the DM once in Telegram, then run again.")

  # start from oldest we DON'T have yet
  # offset_id means "fetch messages with id < offset_id" (older pages)
  row = db.execute("SELECT MIN(msg_id) FROM messages WHERE peer_id=?", (peer_id,)).fetchone()
  offset_id = row[0] if row and row[0] else 0

  total_before = db.execute("SELECT COUNT(*) FROM messages WHERE peer_id=?", (peer_id,)).fetchone()[0]
  saved = 0
  batches = 0
  while True:
    batch = list(client.iter_messages(target, limit=500, offset_id=offset_id))
    if not batch:
      break
    # insert this batch
    for m in batch:
      text = m.message if m.message else "[media]"
      try:
        db.execute(
          "INSERT INTO messages(peer_id,msg_id,ts_utc,from_me,text) VALUES (?,?,?,?,?)",
          (peer_id, m.id, m.date.strftime("%Y-%m-%dT%H:%M:%SZ"), 1 if m.out else 0, text)
        )
        saved += 1
      except sqlite3.IntegrityError:
        pass
    db.commit()
    batches += 1
    oldest = min(x.id for x in batch)
    offset_id = oldest  # next loop fetches older-than-this
    if batches % 10 == 0:
      print(f"...progress: {saved} saved so far; oldest msg_id now {offset_id}")
    time.sleep(0.5)  # gentle pacing

  total_after = db.execute("SELECT COUNT(*) FROM messages WHERE peer_id=?", (peer_id,)).fetchone()[0]
  oldest_ts = db.execute("SELECT ts_utc FROM messages WHERE peer_id=? ORDER BY msg_id ASC LIMIT 1", (peer_id,)).fetchone()
  newest_ts = db.execute("SELECT ts_utc FROM messages WHERE peer_id=? ORDER BY msg_id DESC LIMIT 1", (peer_id,)).fetchone()
  db.close()

print(f"Backfill complete. Added {saved} messages. Total now: {total_after} (was {total_before}).")
print(f"Oldest message UTC: {oldest_ts[0] if oldest_ts else 'n/a'}")
print(f"Newest message UTC: {newest_ts[0] if newest_ts else 'n/a'}")
