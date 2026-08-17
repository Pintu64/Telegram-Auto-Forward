from __future__ import annotations
import asyncio
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from forwarder.config import Config
async def login():
    config = Config.from_env(); Path(config.session_name).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(StringSession(), config.api_id, config.api_hash); await client.start(); me = await client.get_me()
    print(f"Signed in as {me.first_name} (user ID: {me.id})")
    print("\nAdd this exact value to your cloud environment variables. Keep it secret:")
    print(f"TELEGRAM_SESSION={client.session.save()}")
    await client.disconnect()
if __name__ == "__main__": asyncio.run(login())
