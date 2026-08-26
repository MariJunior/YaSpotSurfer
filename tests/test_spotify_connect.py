from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

from yandex_spike.application.spotify_connect import SpotifyConnectService, SpotifyOAuthError
from yandex_spike.infrastructure.oauth_state import make_oauth_state, parse_oauth_state
from yandex_spike.infrastructure.spotify.oauth import SpotifyProfile, SpotifyTokenBundle
from yandex_spike.infrastructure.token_cipher import TokenCipher


class OAuthStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cipher = TokenCipher(Fernet.generate_key().decode("ascii"))

    def test_roundtrip(self) -> None:
        state = make_oauth_state(self.cipher, 42, now=1_000_000)
        self.assertEqual(parse_oauth_state(self.cipher, state, now=1_000_000), 42)

    def test_expired(self) -> None:
        state = make_oauth_state(self.cipher, 42, ttl_sec=10, now=1_000_000)
        self.assertIsNone(parse_oauth_state(self.cipher, state, now=1_000_020))

    def test_tampered(self) -> None:
        state = make_oauth_state(self.cipher, 42)
        # Меняем середину blob — хвост base64 иногда «проглатывается».
        mid = len(state) // 2
        tweaked = state[:mid] + ("A" if state[mid] != "A" else "B") + state[mid + 1 :]
        self.assertIsNone(parse_oauth_state(self.cipher, tweaked))
        other = TokenCipher(Fernet.generate_key().decode("ascii"))
        self.assertIsNone(parse_oauth_state(other, state))


class SpotifyConnectServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
        self.store = MagicMock()
        self.service = SpotifyConnectService(
            store=self.store,
            cipher=self.cipher,
            client_id="cid",
            client_secret="secret",
            redirect_uri="http://127.0.0.1:8766/callback",
        )

    def test_begin_includes_client_and_state(self) -> None:
        link = self.service.begin(99)
        self.assertIn("client_id=cid", link.authorize_url)
        self.assertIn("state=", link.authorize_url)
        self.assertIn("response_type=code", link.authorize_url)

    @patch("yandex_spike.application.spotify_connect.fetch_profile")
    @patch("yandex_spike.application.spotify_connect.exchange_code")
    def test_complete_saves_tokens(self, exchange_mock, profile_mock) -> None:
        state = make_oauth_state(self.cipher, 77)
        exchange_mock.return_value = SpotifyTokenBundle("access", "refresh", 3600)
        profile_mock.return_value = SpotifyProfile("Ada", "spotify-user")

        result = self.service.complete(code="auth-code", state=state, error=None)

        self.assertEqual(result.telegram_id, 77)
        self.assertEqual(result.display_name, "Ada")
        self.store.save_spotify_tokens.assert_called_once_with(
            77, "access", "refresh", "Ada"
        )

    def test_complete_rejects_bad_state(self) -> None:
        with self.assertRaises(SpotifyOAuthError):
            self.service.complete(code="x", state="not-a-token", error=None)


if __name__ == "__main__":
    unittest.main()
