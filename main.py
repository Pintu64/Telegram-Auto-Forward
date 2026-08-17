from __future__ import annotations
import asyncio, logging
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from forwarder.config import Config
from forwarder.control import ControlBot
from forwarder.database import Database
from forwarder.service import ForwardingService

async def run():
    config = Config.from_env(); logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Path(config.session_name).parent.mkdir(parents=True, exist_ok=True); database = Database(config.database_path)
    session = StringSession(config.telegram_session) if config.telegram_session else config.session_name
    client = TelegramClient(session, config.api_id, config.api_hash); await client.connect()
    if not await client.is_user_authorized(): await client.disconnect(); database.close(); raise RuntimeError("User session is not authorized. Run python login.py locally, then set TELEGRAM_SESSION in your deployment variables.")
    service = ForwardingService(client, database); service.register(); control = ControlBot(config.bot_token, config.owner_user_id, database, service)
    await control.application.initialize(); await control.application.start()
    if control.application.updater is None: raise RuntimeError("Telegram bot updater is unavailable")
    await control.application.updater.start_polling(drop_pending_updates=True); logging.getLogger(__name__).info("Auto forwarder is running")
    try: await client.run_until_disconnected()
    finally: await control.application.updater.stop(); await control.application.stop(); await control.application.shutdown(); database.close()
if __name__ == "__main__":
    try: asyncio.run(run())
    except KeyboardInterrupt: pass
