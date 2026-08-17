from pathlib import Path
from forwarder.database import Channel, Database
def test_channel_and_settings_round_trip(tmp_path: Path):
    database = Database(tmp_path / "test.db"); channel = Channel(123, "News", "news"); database.add_channel("source", channel)
    assert database.channels("source") == [channel]; assert database.get_setting("enabled") == "1"
    database.set_setting("mode", "copy"); assert database.get_setting("mode") == "copy"; database.remove_channel("source", 123); assert database.channels("source") == []; database.close()
def test_delivery_tracking(tmp_path: Path):
    database = Database(tmp_path / "test.db"); assert not database.is_delivered(1, 2, 3); database.mark_delivered(1, [2, 4], 3); assert database.is_delivered(1, 2, 3); assert database.is_delivered(1, 4, 3); database.close()

