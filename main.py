from __future__ import annotations
import asyncio, logging
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from forwarder.config import Config
from forwarder.control import CONFLICT_MESSAGE, ControlBot, PollingGuard
from forwarder.database import Database
from forwarder.service import ForwardingService

LOGGER = logging.getLogger(__name__)

async def run():
    config = Config.from_env(); logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Path(config.session_name).parent.mkdir(parents=True, exist_ok=True); database = Database(config.database_path)
    session = StringSession(config.telegram_session) if config.telegram_session else config.session_name
    client = TelegramClient(session, config.api_id, config.api_hash); await client.connect()
    if not await client.is_user_authorized(): await client.disconnect(); database.close(); raise RuntimeError("User session is not authorized. Run python login.py locally, then set TELEGRAM_SESSION in your deployment variables.")
    service = ForwardingService(client, database, config.history_limit, config.poll_interval); service.register()
    watch_task = asyncio.create_task(service.start_history_watch()); control = ControlBot(config.bot_token, config.owner_user_id, database, service)
    await control.application.initialize(); await control.set_commands(); await control.application.start()
    if control.application.updater is None: raise RuntimeError("Telegram bot updater is unavailable")
    await control.application.bot.delete_webhook(drop_pending_updates=True)
    # Give a previous container's long-poll a moment to die after a deploy.
    await asyncio.sleep(3)
    stop_event = asyncio.Event()
    await control.application.updater.start_polling(drop_pending_updates=True, error_callback=PollingGuard(stop_event.set))
    LOGGER.info("Auto forwarder is running")
    try:
        disconnect = asyncio.create_task(client.run_until_disconnected())
        stopped = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait({disconnect, stopped}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if stop_event.is_set() and disconnect not in done:
            raise RuntimeError(CONFLICT_MESSAGE)
    finally:
        watch_task.cancel()
        await control.application.updater.stop(); await control.application.stop(); await control.application.shutdown(); database.close()
if __name__ == "__main__":
    try: asyncio.run(run())
    except KeyboardInterrupt: pass
