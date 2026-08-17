from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    owner_user_id: int
    session_name: str
    database_path: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        required = ("API_ID", "API_HASH", "BOT_TOKEN", "OWNER_USER_ID")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(int(os.environ["API_ID"]), os.environ["API_HASH"].strip(), os.environ["BOT_TOKEN"].strip(), int(os.environ["OWNER_USER_ID"]), os.getenv("SESSION_NAME", "data/user").strip(), Path(os.getenv("DATABASE_PATH", "data/forwarder.db")), os.getenv("LOG_LEVEL", "INFO").upper())

