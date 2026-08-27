from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from yandex_spike.application.bot_migrate import MigrateError, migrate_liked_from_plan
from yandex_spike.application.migrate import write_matched_tracks
from yandex_spike.telegram.copy import (
    MIGRATE_LIBRARY_CONFIRM_WORD,
    migrate_done_text,
)


class WriteCancelTests(unittest.TestCase):
    def test_should_stop_sets_cancelled(self) -> None:
        writer = MagicMock()
        writer.contains.return_value = False
        rows = [
            {
                "source_id": f"yandex:{i}",
                "title": f"T{i}",
                "status": "exact",
                "selected": {"id": f"spotify:{i}", "title": f"T{i}"},
            }
            for i in range(4)
        ]
        calls = {"n": 0}

        def stop() -> bool:
            calls["n"] += 1
            return calls["n"] > 2

        report = write_matched_tracks(
            rows,
            writer,
            migration_id="m1",
            should_stop=stop,
        )
        self.assertTrue(report["cancelled"])
        self.assertLess(report["track_count"], 4)


class BotMigrateTests(unittest.TestCase):
    def test_requires_plan(self) -> None:
        store = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MigrateError) as ctx:
                migrate_liked_from_plan(store, 1, dest="playlist", data_root=Path(tmp))
            self.assertIn("/plan", str(ctx.exception))

    @patch("yandex_spike.application.bot_migrate.SpotifyPlaylistClient")
    @patch("yandex_spike.application.bot_migrate.resolve_spotify_access")
    def test_sandbox_writes_report(self, access_mock, client_cls) -> None:
        access_mock.return_value = "tok"
        client = client_cls.return_value
        client.find_or_create.return_value = "pl1"
        client.item_uris.return_value = set()

        store = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "9"
            user_dir.mkdir()
            (user_dir / "dry-run-state.json").write_text(
                json.dumps(
                    {
                        "processed": {
                            "yandex:1": {
                                "source_id": "yandex:1",
                                "title": "A",
                                "status": "exact",
                                "selected": {"id": "spotify:aaa", "title": "A"},
                            },
                            "yandex:2": {
                                "source_id": "yandex:2",
                                "title": "B",
                                "status": "review",
                                "selected": None,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = migrate_liked_from_plan(
                store, 9, dest="playlist", data_root=root, resume=False
            )
            self.assertEqual(result.saved, 1)
            self.assertEqual(result.skipped, 1)
            self.assertTrue(result.report_path.exists())
            self.assertEqual(result.playlist_name, "YaSpotSurfer sandbox")
            client.add_item.assert_called()


class MigrateCopyTests(unittest.TestCase):
    def test_confirm_word_and_done(self) -> None:
        self.assertEqual(MIGRATE_LIBRARY_CONFIRM_WORD, "СОХРАНИТЬ")
        text = migrate_done_text(
            dest="playlist",
            track_count=10,
            saved=7,
            already=1,
            skipped=2,
            cancelled=False,
            playlist_name="YaSpotSurfer sandbox",
        )
        self.assertIn("sandbox", text)
        self.assertIn("7", text)


if __name__ == "__main__":
    unittest.main()
