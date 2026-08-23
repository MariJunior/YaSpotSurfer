from __future__ import annotations

import unittest

from yandex_spike.telegram.copy import HELP_TEXT, start_text


class TelegramCopyTests(unittest.TestCase):
    def test_start_explains_unofficial_and_risk(self) -> None:
        text = start_text()
        self.assertIn("неофициальный", text)
        self.assertIn("свой страх и риск", text)
        self.assertIn("Яндекс Музыка: не подключена", text)
        self.assertIn("Spotify: не подключён", text)
        self.assertIn("плейлист для проверки", text)

    def test_start_connected_status(self) -> None:
        text = start_text(yandex_connected=True, spotify_display_name="Ada")
        self.assertIn("Яндекс Музыка: подключена", text)
        self.assertIn("Spotify: подключён как Ada", text)

    def test_help_is_plain_language(self) -> None:
        self.assertIn("/scan", HELP_TEXT)
        self.assertIn("VPN", HELP_TEXT)
        self.assertIn("/logout", HELP_TEXT)
        self.assertIn("нейросет", HELP_TEXT)
        self.assertIn("Любимые", HELP_TEXT)
        self.assertNotIn("LLM", HELP_TEXT)
        self.assertNotIn("OAuth", HELP_TEXT)
        self.assertNotIn("auto-match", HELP_TEXT)
        self.assertNotIn("заглуш", HELP_TEXT)


if __name__ == "__main__":
    unittest.main()
