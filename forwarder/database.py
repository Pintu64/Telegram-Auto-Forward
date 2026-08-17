from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Channel:
    chat_id: int
    title: str
    username: str | None
    access_hash: int | None = None

    @property
    def label(self) -> str:
        return f"{self.title} (@{self.username})" if self.username else f"{self.title} ({self.chat_id})"


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS channels (kind TEXT NOT NULL CHECK(kind IN ('source', 'target')), chat_id INTEGER NOT NULL, title TEXT NOT NULL, username TEXT, PRIMARY KEY (kind, chat_id));
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries (source_id INTEGER NOT NULL, message_id INTEGER NOT NULL, target_id INTEGER NOT NULL, PRIMARY KEY (source_id, message_id, target_id));
        """)
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(channels)")}
        if "access_hash" not in columns:
            self.connection.execute("ALTER TABLE channels ADD COLUMN access_hash INTEGER")
        self.connection.execute("UPDATE channels SET chat_id = -1000000000000 - chat_id WHERE chat_id > 0")
        self.connection.execute("INSERT OR IGNORE INTO settings VALUES ('enabled', '1')")
        self.connection.execute("INSERT OR IGNORE INTO settings VALUES ('mode', 'copy')")
        if self.connection.execute("SELECT 1 FROM settings WHERE key = 'attribution_default_v2'").fetchone() is None:
            self.connection.execute("UPDATE settings SET value = 'copy' WHERE key = 'mode'")
            self.connection.execute("INSERT INTO settings VALUES ('attribution_default_v2', '1')")
        self.connection.commit()

    def close(self) -> None: self.connection.close()
    def add_channel(self, kind: str, channel: Channel) -> None:
        self.connection.execute("INSERT OR REPLACE INTO channels(kind, chat_id, title, username, access_hash) VALUES (?, ?, ?, ?, ?)", (kind, channel.chat_id, channel.title, channel.username, channel.access_hash)); self.connection.commit()
    def remove_channel(self, kind: str, chat_id: int) -> None:
        self.connection.execute("DELETE FROM channels WHERE kind = ? AND chat_id = ?", (kind, chat_id)); self.connection.commit()
    def channels(self, kind: str) -> list[Channel]:
        rows = self.connection.execute("SELECT chat_id, title, username, access_hash FROM channels WHERE kind = ? ORDER BY title COLLATE NOCASE", (kind,)).fetchall()
        return [Channel(row["chat_id"], row["title"], row["username"], row["access_hash"]) for row in rows]
    def channel_ids(self, kind: str) -> set[int]: return {channel.chat_id for channel in self.channels(kind)}
    def get_setting(self, key: str) -> str:
        row = self.connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None: raise KeyError(key)
        return str(row["value"])
    def set_setting(self, key: str, value: str) -> None:
        self.connection.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, value)); self.connection.commit()
    def is_delivered(self, source_id: int, message_id: int, target_id: int) -> bool:
        return self.connection.execute("SELECT 1 FROM deliveries WHERE source_id = ? AND message_id = ? AND target_id = ?", (source_id, message_id, target_id)).fetchone() is not None
    def mark_delivered(self, source_id: int, message_ids: list[int], target_id: int) -> None:
        self.connection.executemany("INSERT OR IGNORE INTO deliveries(source_id, message_id, target_id) VALUES (?, ?, ?)", [(source_id, message_id, target_id) for message_id in message_ids]); self.connection.commit()
