import asyncio
from types import SimpleNamespace

from telethon import events, utils
from telethon.tl.types import PeerChannel

from forwarder.database import Channel, Database
from forwarder.service import ForwardingService, canonical_peer_id, message_chat_id, normalize_reference


def test_normalize_reference():
    assert normalize_reference("https://t.me/example/") == "@example"
    assert normalize_reference("@example") == "@example"
    assert normalize_reference("example") == "@example"
    assert normalize_reference("-1001234567890") == -1001234567890


def test_canonical_peer_id_matches_telethon_events():
    assert canonical_peer_id(1234567890) == utils.get_peer_id(PeerChannel(1234567890))
    assert canonical_peer_id(-1001234567890) == -1001234567890


def test_message_chat_id_from_peer():
    message = SimpleNamespace(peer_id=PeerChannel(1234567890), chat_id=None)
    assert message_chat_id(message) == -1001234567890


def test_telethon_incoming_filter_drops_own_posts():
    event = SimpleNamespace(message=SimpleNamespace(out=True, message="hi", fwd_from=None, sender_id=1))
    assert events.NewMessage(incoming=True).filter(event) is None


def test_register_accepts_own_channel_posts():
    captured = []

    class Client:
        def add_event_handler(self, callback, event):
            captured.append(event)

    ForwardingService(Client(), None, history_limit=0, poll_interval=0).register()
    new_message = next(event for event in captured if isinstance(event, events.NewMessage))
    assert new_message.incoming is not True
    assert new_message.outgoing is not True


def test_live_handler_forwards_own_source_posts(tmp_path):
    database = Database(tmp_path / "live.db")
    source_id = -1001234567890
    database.add_channel("source", Channel(source_id, "Source", "source", 88))
    database.add_channel("target", Channel(-1001987654321, "Target", "target", 99))
    client = FakeClient()
    service = ForwardingService(client, database, history_limit=0, poll_interval=0)
    event = SimpleNamespace(message=FakeMessage(12, PeerChannel(1234567890), out=True, grouped_id=None))

    asyncio.run(service._on_message(event))

    assert [message_ids for _, message_ids in client.forwarded] == [[12]]
    assert database.is_delivered(source_id, 12, -1001987654321)
    database.close()


def test_delivers_own_channel_posts(tmp_path):
    database = Database(tmp_path / "forwarder.db")
    source_id = -1001234567890
    target = Channel(-1001987654321, "Target", "target", 99)
    database.add_channel("source", Channel(source_id, "Source", "source", 88))
    database.add_channel("target", target)
    client = FakeClient()
    service = ForwardingService(client, database, history_limit=0, poll_interval=0)
    message = FakeMessage(10, PeerChannel(1234567890), out=True)

    asyncio.run(service._deliver(message_chat_id(message), [message]))

    assert [message_ids for _, message_ids in client.forwarded] == [[10]]
    assert database.is_delivered(source_id, 10, target.chat_id)
    database.close()


def test_skips_service_messages_and_same_channel_targets(tmp_path):
    database = Database(tmp_path / "forwarder.db")
    source_id = -1001234567890
    database.add_channel("source", Channel(source_id, "Source", "source", 88))
    database.add_channel("target", Channel(source_id, "Same", "same", 88))
    client = FakeClient()
    service = ForwardingService(client, database, history_limit=0, poll_interval=0)
    service_message = FakeMessage(11, PeerChannel(1234567890), action=object())

    asyncio.run(service._deliver(source_id, [service_message]))

    assert client.forwarded == []
    database.close()


class FakeMessage:
    def __init__(self, message_id, peer_id, out=True, action=None, grouped_id=None):
        self.id = message_id
        self.peer_id = peer_id
        self.out = out
        self.action = action
        self.grouped_id = grouped_id


class FakeClient:
    def __init__(self):
        self.forwarded = []

    async def forward_messages(self, target, messages):
        self.forwarded.append((target.channel_id if hasattr(target, "channel_id") else target, [message.id for message in messages]))

    async def get_input_entity(self, value):
        return value
