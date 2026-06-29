"""SQLite-хранилище связей сообщений (защита от петель)."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from bridge.config import bridge_db_path


class BridgeStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or bridge_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bridge_messages (
                    bridge_key TEXT PRIMARY KEY,
                    src_platform TEXT NOT NULL,
                    src_chat_id INTEGER NOT NULL,
                    src_message_id TEXT NOT NULL,
                    dst_platform TEXT NOT NULL,
                    dst_chat_id INTEGER NOT NULL,
                    dst_message_id TEXT,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bridge_src
                    ON bridge_messages(src_platform, src_chat_id, src_message_id);
                CREATE INDEX IF NOT EXISTS idx_bridge_dst
                    ON bridge_messages(dst_platform, dst_chat_id, dst_message_id);
                CREATE TABLE IF NOT EXISTS bridge_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def save_pair(
        self,
        *,
        bridge_key: str,
        src_platform: str,
        src_chat_id: int,
        src_message_id: str,
        dst_platform: str,
        dst_chat_id: int,
        dst_message_id: str | None = None,
    ) -> None:
        now = time.time()
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO bridge_messages (
                    bridge_key, src_platform, src_chat_id, src_message_id,
                    dst_platform, dst_chat_id, dst_message_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bridge_key,
                    src_platform,
                    int(src_chat_id),
                    str(src_message_id),
                    dst_platform,
                    int(dst_chat_id),
                    str(dst_message_id) if dst_message_id is not None else None,
                    now,
                ),
            )

    def update_dst_message_id(self, bridge_key: str, dst_message_id: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                'UPDATE bridge_messages SET dst_message_id = ? WHERE bridge_key = ?',
                (str(dst_message_id), bridge_key),
            )

    def is_known_src(self, platform: str, chat_id: int, message_id: str) -> bool:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM bridge_messages
                WHERE src_platform = ? AND src_chat_id = ? AND src_message_id = ?
                LIMIT 1
                """,
                (platform, int(chat_id), str(message_id)),
            ).fetchone()
            return row is not None

    def is_known_dst(self, platform: str, chat_id: int, message_id: str) -> bool:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM bridge_messages
                WHERE dst_platform = ? AND dst_chat_id = ? AND dst_message_id = ?
                LIMIT 1
                """,
                (platform, int(chat_id), str(message_id)),
            ).fetchone()
            return row is not None

    def get_marker(self, key: str) -> str | None:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                'SELECT value FROM bridge_state WHERE key = ?',
                (key,),
            ).fetchone()
            return row['value'] if row else None

    def set_marker(self, key: str, value: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO bridge_state (key, value) VALUES (?, ?)',
                (key, value),
            )


_store: BridgeStore | None = None


def get_store() -> BridgeStore:
    global _store
    if _store is None:
        _store = BridgeStore()
    return _store
