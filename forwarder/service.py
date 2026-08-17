from __future__ import annotations
import asyncio
import logging
from telethon import TelegramClient, events
from telethon import utils
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel as TelegramChannel, InputPeerChannel
from .database import Channel, Database

LOGGER = logging.getLogger(__name__)

class ForwardingService:
    def __init__(self, client: TelegramClient, database: Database): self.client, self.database = client, database
    def register(self):
        self.client.add_event_handler(self._on_album, events.Album())
        self.client.add_event_handler(self._on_message, events.NewMessage(incoming=True))
    async def sync_recent_history(self, limit: int) -> None:
        if limit <= 0: return
        for source in self.database.channels("source"):
            try:
                peer = await self._input_peer(source)
                messages = await self.client.get_messages(peer, limit=limit)
                for message in reversed(messages):
                    await self._deliver(source.chat_id, [message])
            except Exception:
                LOGGER.exception("History sync failed for source %s", source.chat_id)
    async def resolve_channel(self, value: str) -> Channel:
        entity = await self.client.get_entity(normalize_reference(value))
        if not isinstance(entity, TelegramChannel): raise ValueError("Not a channel")
        # Store the same peer ID shape emitted by Telethon events (-100...).
        # `entity.id` alone is only the positive channel ID and will not match
        # `event.chat_id` for broadcast channels.
        return Channel(int(utils.get_peer_id(entity)), entity.title or "Untitled channel", entity.username, entity.access_hash)
    async def _on_message(self, event):
        if event.message.grouped_id is None: await self._deliver(event.chat_id, [event.message])
    async def _on_album(self, event): await self._deliver(event.chat_id, list(event.messages))
    async def _deliver(self, raw_source_id, messages):
        if raw_source_id is None or self.database.get_setting("enabled") != "1": return
        source_id = int(raw_source_id)
        if source_id not in self.database.channel_ids("source"): return
        message_ids, mode = [int(message.id) for message in messages], self.database.get_setting("mode")
        for target_channel in self.database.channels("target"):
            target_id = target_channel.chat_id
            if all(self.database.is_delivered(source_id, message_id, target_id) for message_id in message_ids): continue
            try:
                await self._send(target_channel, messages, mode)
                self.database.mark_delivered(source_id, message_ids, target_id)
                await asyncio.sleep(1)
            except FloodWaitError as error:
                LOGGER.warning("Telegram requested a %s second flood wait", error.seconds)
                await asyncio.sleep(error.seconds + 1)
                await self._send(target_channel, messages, mode)
                self.database.mark_delivered(source_id, message_ids, target_id)
            except Exception: LOGGER.exception("Delivery failed from %s to %s", source_id, target_id)
    async def _send(self, target_channel, messages, mode):
        target = await self._input_peer(target_channel)
        if mode == "forward": await self.client.forward_messages(target, messages)
        else:
            # Telethon copies a Message object, including its media and caption.
            # Sending separately is reliable for mixed albums, though Telegram
            # may display copied album items as individual posts.
            for message in messages:
                await self.client.send_message(target, message)
    async def _input_peer(self, channel):
        if channel.access_hash is not None:
            entity_id, _ = utils.resolve_id(channel.chat_id)
            return InputPeerChannel(entity_id, channel.access_hash)
        if channel.username:
            return await self.client.get_input_entity(channel.username)
        return await self.client.get_input_entity(channel.chat_id)

def normalize_reference(value: str) -> str | int:
    cleaned = value.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if cleaned.lower().startswith(prefix): cleaned = cleaned[len(prefix):].split("?", 1)[0].strip("/"); break
    if cleaned.startswith("@"): return cleaned
    try: return int(cleaned)
    except ValueError: return f"@{cleaned}"
