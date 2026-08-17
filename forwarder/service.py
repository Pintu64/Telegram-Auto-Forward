from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, events
from telethon import utils
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel as TelegramChannel, InputPeerChannel, MessageService, PeerChannel

from .database import Channel, Database

LOGGER = logging.getLogger(__name__)


class ForwardingService:
    def __init__(self, client: TelegramClient, database: Database, history_limit: int = 50, poll_interval: int = 20):
        self.client = client
        self.database = database
        self.history_limit = history_limit
        self.poll_interval = poll_interval
        self._sync_lock = asyncio.Lock()

    def register(self):
        # Own posts in a source channel have message.out=True. incoming=True
        # would drop them, so live forwarding would never run for the owner.
        self.client.add_event_handler(self._on_album, events.Album())
        self.client.add_event_handler(self._on_message, events.NewMessage())

    async def start_history_watch(self) -> None:
        while True:
            try:
                await self.sync_recent_history()
            except Exception:
                LOGGER.exception("History watch cycle failed")
            if self.poll_interval <= 0:
                return
            await asyncio.sleep(self.poll_interval)

    async def sync_recent_history(self) -> None:
        if self.history_limit <= 0:
            return
        async with self._sync_lock:
            for source in self.database.channels("source"):
                try:
                    peer = await self._input_peer(source)
                    messages = await self.client.get_messages(peer, limit=self.history_limit)
                    for message in reversed(messages):
                        await self._deliver(source.chat_id, [message])
                except Exception:
                    LOGGER.exception("History sync failed for source %s", source.chat_id)

    async def resolve_channel(self, value: str) -> Channel:
        entity = await self.client.get_entity(normalize_reference(value))
        if not isinstance(entity, TelegramChannel):
            raise ValueError("Not a channel")
        # Store the same peer ID shape emitted by Telethon events (-100...).
        # `entity.id` alone is only the positive channel ID and will not match
        # `event.chat_id` for broadcast channels.
        return Channel(int(utils.get_peer_id(entity)), entity.title or "Untitled channel", entity.username, entity.access_hash)

    async def _on_message(self, event):
        if event.message.grouped_id is None:
            await self._deliver(message_chat_id(event.message), [event.message])

    async def _on_album(self, event):
        messages = list(event.messages)
        if messages:
            await self._deliver(message_chat_id(messages[0]), messages)

    async def _deliver(self, raw_source_id, messages):
        if raw_source_id is None or self.database.get_setting("enabled") != "1":
            return
        source_id = canonical_peer_id(raw_source_id)
        source_ids = {canonical_peer_id(chat_id) for chat_id in self.database.channel_ids("source")}
        if source_id not in source_ids:
            return
        messages = [message for message in messages if is_forwardable(message)]
        if not messages:
            return
        message_ids, mode = [int(message.id) for message in messages], self.database.get_setting("mode")
        for target_channel in self.database.channels("target"):
            target_id = canonical_peer_id(target_channel.chat_id)
            if target_id == source_id:
                continue
            if all(self.database.is_delivered(source_id, message_id, target_id) for message_id in message_ids):
                continue
            try:
                await self._send(target_channel, messages, mode)
                self.database.mark_delivered(source_id, message_ids, target_id)
                LOGGER.info("Delivered %s message(s) from %s to %s", len(message_ids), source_id, target_id)
                await asyncio.sleep(1)
            except FloodWaitError as error:
                LOGGER.warning("Telegram requested a %s second flood wait", error.seconds)
                await asyncio.sleep(error.seconds + 1)
                await self._send(target_channel, messages, mode)
                self.database.mark_delivered(source_id, message_ids, target_id)
            except Exception:
                LOGGER.exception("Delivery failed from %s to %s", source_id, target_id)

    async def _send(self, target_channel, messages, mode):
        target = await self._input_peer(target_channel)
        if mode == "forward":
            await self.client.forward_messages(target, messages)
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


def message_chat_id(message) -> int | None:
    peer = getattr(message, "peer_id", None)
    if peer is not None:
        return canonical_peer_id(utils.get_peer_id(peer))
    chat_id = getattr(message, "chat_id", None)
    return None if chat_id is None else canonical_peer_id(chat_id)


def canonical_peer_id(value: int) -> int:
    chat_id = int(value)
    if chat_id > 0:
        return int(utils.get_peer_id(PeerChannel(chat_id)))
    return chat_id


def is_forwardable(message) -> bool:
    if getattr(message, "id", None) is None:
        return False
    if getattr(message, "action", None) is not None:
        return False
    return not isinstance(message, MessageService)


def normalize_reference(value: str) -> str | int:
    cleaned = value.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].split("?", 1)[0].strip("/")
            break
    if cleaned.startswith("@"):
        return cleaned
    try:
        return int(cleaned)
    except ValueError:
        return f"@{cleaned}"
