from __future__ import annotations

import unittest

from yandex_spike.cli_catalog import (
    COMMAND_NAMES,
    format_help_text,
    normalize_command,
)
from yandex_spike.cli_menu import menu_commands_for_tests


class CliHelpTests(unittest.TestCase):
    def test_normalize_slash_help(self) -> None:
        self.assertEqual(normalize_command("/help"), "help")
        self.assertEqual(normalize_command("Help"), "help")
        self.assertIsNone(normalize_command("  "))

    def test_help_lists_core_commands(self) -> None:
        text = format_help_text()
        for name in (
            "auth-implicit",
            "scan",
            "migrate-dry-run",
            "review",
            "migrate",
            "migrate-playlists",
            "menu",
        ):
            self.assertIn(name, text)
        self.assertIn("650", text)

    def test_catalog_includes_help_and_menu(self) -> None:
        self.assertIn("help", COMMAND_NAMES)
        self.assertIn("menu", COMMAND_NAMES)
        self.assertIn("scan", menu_commands_for_tests())


if __name__ == "__main__":
    unittest.main()
