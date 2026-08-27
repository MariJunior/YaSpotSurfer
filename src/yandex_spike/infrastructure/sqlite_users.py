"""SQLite: один пользователь бота на telegram_id. Токены только в шифротексте."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from yandex_spike.domain.bot_user import BotUser
from yandex_spike.infrastructure.token_cipher import TokenCipher

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_users (
    telegram_id INTEGER PRIMARY KEY,
    yandex_token_enc TEXT,
    spotify_token_enc TEXT,
    spotify_refresh_enc TEXT,
    spotify_display_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_callbacks (
    token TEXT PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SqliteUserStore:
    def __init__(self, path: Path, cipher: TokenCipher) -> None:
        self._cipher = cipher
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: PTB может дергать handlers не из того потока, где открыли БД.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # DELETE: на Windows WAL мешает удалять файл в тестах.
            self._conn.execute("PRAGMA journal_mode=DELETE")
            self._conn.commit()

    def get(self, telegram_id: int) -> BotUser:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bot_users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None:
            return BotUser(telegram_id=telegram_id)
        yandex_ok = self._has_secret(row["yandex_token_enc"])
        spotify_ok = self._has_secret(row["spotify_token_enc"])
        name = row["spotify_display_name"] if spotify_ok else None
        return BotUser(
            telegram_id=telegram_id,
            yandex_connected=yandex_ok,
            spotify_connected=spotify_ok,
            spotify_display_name=name,
        )

    def ensure(self, telegram_id: int) -> BotUser:
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO bot_users (telegram_id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO NOTHING
                """,
                (telegram_id, now, now),
            )
            self._conn.commit()
        return self.get(telegram_id)

    def save_yandex_token(self, telegram_id: int, access_token: str) -> None:
        self.ensure(telegram_id)
        blob = self._cipher.encrypt(access_token)
        with self._lock:
            self._conn.execute(
                """
                UPDATE bot_users
                SET yandex_token_enc = ?, updated_at = ?
                WHERE telegram_id = ?
                """,
                (blob, _now(), telegram_id),
            )
            self._conn.commit()

    def save_spotify_tokens(
        self,
        telegram_id: int,
        access_token: str,
        refresh_token: str | None,
        display_name: str | None,
    ) -> None:
        self.ensure(telegram_id)
        access_blob = self._cipher.encrypt(access_token)
        refresh_blob = self._cipher.encrypt(refresh_token) if refresh_token else None
        with self._lock:
            self._conn.execute(
                """
                UPDATE bot_users
                SET spotify_token_enc = ?,
                    spotify_refresh_enc = ?,
                    spotify_display_name = ?,
                    updated_at = ?
                WHERE telegram_id = ?
                """,
                (access_blob, refresh_blob, display_name, _now(), telegram_id),
            )
            self._conn.commit()

    def logout(self, telegram_id: int) -> bool:
        before = self.get(telegram_id)
        had = before.yandex_connected or before.spotify_connected
        with self._lock:
            # Строку удаляем целиком: не оставляем чужие секреты и имя Spotify.
            self._conn.execute("DELETE FROM bot_users WHERE telegram_id = ?", (telegram_id,))
            self._conn.execute(
                "DELETE FROM review_callbacks WHERE telegram_id = ?",
                (telegram_id,),
            )
            self._conn.commit()
        return had

    def put_review_token(self, token: str, telegram_id: int, source_id: str) -> None:
        """Короткий token в callback_data → source_id (лимит Telegram 64 байта)."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM review_callbacks WHERE telegram_id = ?",
                (telegram_id,),
            )
            self._conn.execute(
                """
                INSERT INTO review_callbacks (token, telegram_id, source_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, telegram_id, source_id, _now()),
            )
            self._conn.commit()

    def get_review_token(self, token: str) -> tuple[int, str] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT telegram_id, source_id FROM review_callbacks WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        return int(row["telegram_id"]), str(row["source_id"])

    def clear_review_tokens(self, telegram_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM review_callbacks WHERE telegram_id = ?",
                (telegram_id,),
            )
            self._conn.commit()

    def read_yandex_token(self, telegram_id: int) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT yandex_token_enc FROM bot_users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None or not row["yandex_token_enc"]:
            return None
        return self._cipher.decrypt(row["yandex_token_enc"])

    def read_spotify_tokens(self, telegram_id: int) -> tuple[str | None, str | None]:
        with self._lock:
            row = self._conn.execute(
                "SELECT spotify_token_enc, spotify_refresh_enc FROM bot_users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None:
            return None, None
        access = self._cipher.decrypt(row["spotify_token_enc"]) if row["spotify_token_enc"] else None
        refresh = (
            self._cipher.decrypt(row["spotify_refresh_enc"]) if row["spotify_refresh_enc"] else None
        )
        return access, refresh

    def _has_secret(self, blob: str | None) -> bool:
        if not blob:
            return False
        plaintext = self._cipher.decrypt(blob)
        if plaintext is None:
            logger.error("Stored token blob could not be decrypted; treating as disconnected")
            return False
        return bool(plaintext)

    def close(self) -> None:
        # Windows не даёт удалить файл SQLite, пока соединение открыто.
        with self._lock:
            self._conn.close()
