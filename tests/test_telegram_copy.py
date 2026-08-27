from __future__ import annotations

import unittest

from yandex_spike.telegram.copy import (
    HELP_TEXT,
    SPOTIFY_DAILY_SEARCH_SOFT_CAP,
    plan_quota_exceeded_text,
    start_text,
)


class TelegramCopyTests(unittest.TestCase):
    def test_start_explains_unofficial_and_risk(self) -> None:
        text = start_text()
        self.assertIn("неофициальный", text)
        self.assertIn("свой страх и риск", text)
        self.assertIn("Яндекс Музыка: ⚪ не подключена", text)
        self.assertIn("Spotify: ⚪ не подключён", text)
        self.assertIn("проверочный плейлист", text)
        self.assertIn(str(SPOTIFY_DAILY_SEARCH_SOFT_CAP), text)

    def test_start_connected_status(self) -> None:
        text = start_text(yandex_connected=True, spotify_display_name="Ada")
        self.assertIn("Яндекс Музыка: ✅ подключена", text)
        self.assertIn("Spotify: ✅ подключён как Ada", text)

    def test_help_is_plain_language(self) -> None:
        self.assertIn("/scan", HELP_TEXT)
        self.assertIn("/connect_yandex", HELP_TEXT)
        self.assertIn("/connect_spotify", HELP_TEXT)
        self.assertIn("VPN", HELP_TEXT)
        self.assertIn("/logout", HELP_TEXT)
        self.assertIn("нейросет", HELP_TEXT)
        self.assertIn("Любимое", HELP_TEXT)
        self.assertIn("/playlists", HELP_TEXT)
        self.assertIn("/review", HELP_TEXT)
        self.assertIn("/migrate", HELP_TEXT)
        self.assertIn(str(SPOTIFY_DAILY_SEARCH_SOFT_CAP), HELP_TEXT)
        self.assertIn("квота", HELP_TEXT.lower())
        self.assertNotIn("LLM", HELP_TEXT)
        self.assertNotIn("OAuth", HELP_TEXT)
        self.assertNotIn("auto-match", HELP_TEXT)
        self.assertNotIn("заглуш", HELP_TEXT)

    def test_quota_copy_explains_batches(self) -> None:
        text = plan_quota_exceeded_text(done=650, hours=18)
        self.assertIn("650", text)
        self.assertIn("18", text)
        self.assertIn("/plan", text)
        self.assertIn(str(SPOTIFY_DAILY_SEARCH_SOFT_CAP), text)


if __name__ == "__main__":
    unittest.main()
