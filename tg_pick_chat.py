from telethon.sync import TelegramClient
from dotenv import load_dotenv
import os

load_dotenv()
api_id=int(os.getenv("API_ID"))
api_hash=os.getenv("API_HASH")
phone=os.getenv("PHONE_NUMBER")
session=os.getenv("SESSION_NAME","telegram_briefs")

with TelegramClient(session, api_id, api_hash) as client:
    client.start(phone=phone)
    print("Looking for chats with 'William' in the name...\n")
    found = 0
    for d in client.iter_dialogs():
        name = (d.name or "").strip()
        if "william" in name.lower():
            ent = d.entity
            kind = type(ent).__name__
            username = getattr(ent, "username", None)
            print(f"- {name} | type={kind} | id={ent.id} | username={username}")
            found += 1
    if not found:
        print("No matches. Open Telegram, open the DM with William once, then run me again.")
