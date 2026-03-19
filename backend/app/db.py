from __future__ import annotations

from contextlib import asynccontextmanager

import aiosqlite

from app.config import settings


def _sqlite_path_from_database_url(database_url: str) -> str:
    # Accept:
    # - sqlite:///./app.db
    # - sqlite:////absolute/path/app.db
    # - app.db (fallback)
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///") :]
    if database_url.startswith("sqlite:////"):
        return database_url[len("sqlite:") :]
    return database_url


async def init_db() -> None:
    path = _sqlite_path_from_database_url(settings.database_url)
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
              id TEXT PRIMARY KEY,
              user_sub TEXT NOT NULL,
              created_at REAL NOT NULL,
              title TEXT,
              model TEXT,
              model_id TEXT
            )
            """
        )
        # Backward-compatible migrations for existing DBs.
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN model TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN model_id TEXT")
        except Exception:
            pass
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at REAL NOT NULL,
              FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_events (
              id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              tool_call_id TEXT NOT NULL,
              tool_name TEXT NOT NULL,
              arguments_json TEXT NOT NULL,
              result_text TEXT,
              created_at REAL NOT NULL,
              FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
            """
        )
        await db.commit()


@asynccontextmanager
async def get_db() -> aiosqlite.Connection:
    path = _sqlite_path_from_database_url(settings.database_url)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        yield db

