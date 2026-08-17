from forwarder.config import Config


def test_config_reads_telegram_string_session(monkeypatch):
    monkeypatch.setenv("API_ID", "123")
    monkeypatch.setenv("API_HASH", "hash")
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("OWNER_USER_ID", "456")
    monkeypatch.setenv("TELEGRAM_SESSION", "session-value")
    monkeypatch.setenv("POLL_INTERVAL", "15")

    config = Config.from_env()

    assert config.telegram_session == "session-value"
    assert config.poll_interval == 15
