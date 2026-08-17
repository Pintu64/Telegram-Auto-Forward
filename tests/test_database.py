import sqlite3
from pathlib import Path
from forwarder.database import Channel, Database
def test_channel_and_settings_round_trip(tmp_path: Path):
    database = Database(tmp_path / "test.db"); channel = Channel(-100123, "News", "news", 999); database.add_channel("source", channel)
    assert database.channels("source") == [channel]; assert database.get_setting("enabled") == "1"; assert database.get_setting("mode") == "copy"
    database.set_setting("mode", "copy"); assert database.get_setting("mode") == "copy"; database.remove_channel("source", -100123); assert database.channels("source") == []; database.close()
def test_delivery_tracking(tmp_path: Path):
    database = Database(tmp_path / "test.db"); assert not database.is_delivered(1, 2, 3); database.mark_delivered(1, [2, 4], 3); assert database.is_delivered(1, 2, 3); assert database.is_delivered(1, 4, 3); database.close()


def test_migrates_legacy_positive_channel_ids(tmp_path: Path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE channels (kind TEXT, chat_id INTEGER, title TEXT, username TEXT, PRIMARY KEY (kind, chat_id))")
    connection.execute("INSERT INTO channels VALUES ('source', 123456, 'Legacy', 'legacy')")
    connection.commit()
    connection.close()

    database = Database(path)

    assert database.channels("source")[0].chat_id == -1000000123456
    database.close()


def test_switches_legacy_forward_default_to_copy(tmp_path: Path):
    path = tmp_path / "legacy-mode.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE channels (kind TEXT, chat_id INTEGER, title TEXT, username TEXT, access_hash INTEGER, PRIMARY KEY (kind, chat_id));
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE deliveries (source_id INTEGER, message_id INTEGER, target_id INTEGER, PRIMARY KEY (source_id, message_id, target_id));
        INSERT INTO settings VALUES ('enabled', '1');
        INSERT INTO settings VALUES ('mode', 'forward');
    """)
    connection.commit()
    connection.close()

    database = Database(path)

    assert database.get_setting("mode") == "copy"
    database.close()
