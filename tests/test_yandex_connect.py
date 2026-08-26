from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import Timeout

from yandex_spike.application.yandex_connect import (
    YandexConnectError,
    begin_yandex_connect,
    complete_yandex_connect,
)


class YandexConnectTests(unittest.TestCase):
    def test_begin_builds_authorize_url(self) -> None:
        link = begin_yandex_connect()
        self.assertIn("oauth.yandex.ru/authorize", link.authorize_url)
        self.assertIn("response_type=token", link.authorize_url)

    @patch("yandex_spike.application.yandex_connect.probe_music_http")
    def test_complete_saves_when_probe_ok(self, probe_mock) -> None:
        probe_mock.return_value = {"http_status": 200, "ok": True}
        store = MagicMock()
        url = "https://music.yandex.ru/#access_token=secret-token&token_type=bearer"
        result = complete_yandex_connect(store, 55, url)
        self.assertTrue(result.ok)
        store.save_yandex_token.assert_called_once_with(55, "secret-token")

    @patch("yandex_spike.application.yandex_connect.probe_music_http")
    def test_complete_rejects_bad_probe(self, probe_mock) -> None:
        probe_mock.return_value = {"http_status": 403, "ok": False}
        store = MagicMock()
        url = "https://music.yandex.ru/#access_token=bad&token_type=bearer"
        with self.assertRaises(YandexConnectError):
            complete_yandex_connect(store, 1, url)
        store.save_yandex_token.assert_not_called()

    @patch("yandex_spike.application.yandex_connect.probe_music_http")
    def test_complete_network_error_mentions_split_tunnel(self, probe_mock) -> None:
        probe_mock.side_effect = Timeout()
        store = MagicMock()
        url = "https://music.yandex.ru/#access_token=t&token_type=bearer"
        with self.assertRaises(YandexConnectError) as ctx:
            complete_yandex_connect(store, 1, url)
        self.assertIn("split tunnel", str(ctx.exception).lower())
        store.save_yandex_token.assert_not_called()

    def test_complete_rejects_url_without_token(self) -> None:
        store = MagicMock()
        with self.assertRaises(YandexConnectError):
            complete_yandex_connect(store, 1, "https://music.yandex.ru/")
        store.save_yandex_token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
