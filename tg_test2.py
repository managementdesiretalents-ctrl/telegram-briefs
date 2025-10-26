from telethon.sync import TelegramClient
from dotenv import load_dotenv
import os, sys

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("PHONE_NUMBER")
peer_id = int(os.getenv("PEER_ID"))
session_name = os.getenv("SESSION_NAME", "telegram_briefs")

with TelegramClient(session_name, api_id, api_hash) as client:
    client.start(phone=phone)

    # find the dialog whose entity id matches PEER_ID
    target = None
    for d in client.iter_dialogs():
        ent = d.entity
        if getattr(ent, "id", None) == peer_id:
            target = ent
            break

    if not target:
        print("Could not find the DM in your dialogs. Open the DM with William once in Telegram, then run again.")
        sys.exit(1)

    print("Last 5 messages with William:")
    for msg in client.iter_messages(target, limit=5):
        who = "YOU" if msg.out else "THEM"
        text = (msg.message or "[media]").replace("\n", " ")
        print(f"- {msg.date} | {who}: {text[:140]}")
