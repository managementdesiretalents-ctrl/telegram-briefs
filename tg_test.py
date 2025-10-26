from telethon.sync import TelegramClient
from dotenv import load_dotenv
import os

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("PHONE_NUMBER")
peer_id = int(os.getenv("PEER_ID"))
session_name = os.getenv("SESSION_NAME", "telegram_briefs")

with TelegramClient(session_name, api_id, api_hash) as client:
    # First run will ask for a login code (in your Telegram app) and maybe your 2FA password
    client.start(phone=phone)

    me = client.get_me()
    print(f"Logged in as: {me.first_name} (id: {me.id})")

    entity = client.get_entity(peer_id)
    print("Last 5 messages with the target chat:")
    for msg in client.iter_messages(entity, limit=5):
        who = "YOU" if msg.out else "THEM"
        text = (msg.message or "[media]").replace("\n", " ")
        print(f"- {msg.date} | {who}: {text[:120]}")
