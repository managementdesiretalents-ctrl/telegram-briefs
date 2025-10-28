"""Utility script for quickly checking the Telegram DM history.

``pytest`` imports any ``*_test.py`` modules during collection.  The previous
implementation of this script executed the Telethon login flow at import time
which immediately failed when environment variables (or Telethon itself) were
missing.  By moving the work behind a ``main`` guard we keep pytest happy while
preserving the original behaviour when the file is run directly.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


def _env_int(name: str) -> int:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return int(value)


def main() -> None:
    """Start a Telethon client and print the latest messages."""

    try:
        from telethon.sync import TelegramClient
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Telethon is required to run tg_test.py. Install dependencies first."
        ) from exc

    load_dotenv()

    api_id = _env_int("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE_NUMBER")
    peer_id = _env_int("PEER_ID")
    session_name = os.getenv("SESSION_NAME", "telegram_briefs")

    if not api_hash or not phone:
        raise RuntimeError("API_HASH and PHONE_NUMBER must be set in the environment")

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


if __name__ == "__main__":
    main()
