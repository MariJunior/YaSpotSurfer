from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from yandex_spike.application.accounts import load_account, logout_account
from yandex_spike.infrastructure.sqlite_users import SqliteUserStore
from yandex_spike.infrastructure.token_cipher import TokenCipher


class SqliteUserStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmp.name) / "users.sqlite"
        self.cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
        self.store = SqliteUserStore(self.db_path, self.cipher)

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_missing_user_is_disconnected(self) -> None:
        user = self.store.get(101)
        self.assertFalse(user.yandex_connected)
        self.assertFalse(user.spotify_connected)

    def test_tokens_roundtrip_and_are_not_stored_plaintext(self) -> None:
        secret = "yandex-access-token-value"
        self.store.save_yandex_token(7, secret)
        self.assertEqual(self.store.read_yandex_token(7), secret)
        self.assertTrue(load_account(self.store, 7).yandex_connected)

        with sqlite3.connect(self.db_path) as conn:
            raw = conn.execute(
                "SELECT yandex_token_enc FROM bot_users WHERE telegram_id = 7"
            ).fetchone()[0]
        self.assertIsInstance(raw, str)
        self.assertNotIn(secret, raw)

    def test_users_do_not_share_tokens(self) -> None:
        self.store.save_yandex_token(1, "token-one")
        self.store.save_spotify_tokens(2, "sp-access", "sp-refresh", "Ada")
        self.assertEqual(self.store.read_yandex_token(1), "token-one")
        self.assertIsNone(self.store.read_yandex_token(2))
        access, refresh = self.store.read_spotify_tokens(2)
        self.assertEqual(access, "sp-access")
        self.assertEqual(refresh, "sp-refresh")
        self.assertIsNone(self.store.read_spotify_tokens(1)[0])

    def test_logout_wipes_row(self) -> None:
        self.store.save_yandex_token(9, "secret")
        self.store.save_spotify_tokens(9, "a", "r", "Bo")
        self.assertTrue(logout_account(self.store, 9))
        self.assertFalse(self.store.get(9).yandex_connected)
        self.assertFalse(self.store.get(9).spotify_connected)
        self.assertIsNone(self.store.read_yandex_token(9))
        self.assertFalse(logout_account(self.store, 9))

    def test_review_token_roundtrip_and_logout_clears(self) -> None:
        self.store.put_review_token("aabbccdd", 5, "yandex:42")
        self.assertEqual(self.store.get_review_token("aabbccdd"), (5, "yandex:42"))
        self.store.save_yandex_token(5, "tok")
        logout_account(self.store, 5)
        self.assertIsNone(self.store.get_review_token("aabbccdd"))

    def test_wrong_key_looks_disconnected(self) -> None:
        self.store.save_yandex_token(3, "secret")
        other = SqliteUserStore(
            self.db_path,
            TokenCipher(Fernet.generate_key().decode("ascii")),
        )
        self.assertFalse(other.get(3).yandex_connected)
        self.assertIsNone(other.read_yandex_token(3))
        other.close()


if __name__ == "__main__":
    unittest.main()
