import os, sqlite3
from datetime import datetime
from telethon.sync import TelegramClient
from dotenv import load_dotenv

load_dotenv()
api_id     = int(os.getenv("API_ID"))
api_hash   = os.getenv("API_HASH")
phone      = os.getenv("PHONE_NUMBER")
peer_id    = int(os.getenv("PEER_ID"))
session    = os.getenv("SESSION_NAME","telegram_briefs")

# 1) DB setup
db = sqlite3.connect("briefs.db")
db.execute("PRAGMA journal_mode=WAL;")
db.execute("""
CREATE TABLE IF NOT EXISTS messages (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  peer_id  INTEGER NOT NULL,
  msg_id   INTEGER NOT NULL,
  ts_utc   TEXT    NOT NULL,
  from_me  INTEGER NOT NULL,
  text     TEXT
);
""")
db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_peer_msg ON messages(peer_id, msg_id);")

# 2) Telegram fetch (last ~200 msgs)
new_rows = 0
with TelegramClient(session, api_id, api_hash) as client:
    client.start(phone=phone)

    target = None
    for d in client.iter_dialogs():
        if getattr(d.entity, "id", None) == peer_id:
            target = d.entity
            break
    if not target:
        raise SystemExit("Open the DM with William once in Telegram, then run again.")

    for m in client.iter_messages(target, limit=200):
        text = m.message if m.message else "[media]"
        try:
            db.execute(
              "INSERT INTO messages(peer_id,msg_id,ts_utc,from_me,text) VALUES (?,?,?,?,?)",
              (peer_id, m.id, m.date.strftime("%Y-%m-%dT%H:%M:%SZ"), 1 if m.out else 0, text)
            )
            new_rows += 1
        except sqlite3.IntegrityError:
            pass  # already saved

db.commit()
total = db.execute("SELECT COUNT(*) FROM messages WHERE peer_id=?", (peer_id,)).fetchone()[0]
db.close()

print(f"Saved {new_rows} new messages. Total for this chat: {total}.")
