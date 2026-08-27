from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from yandex_spike.application.cli_dashboard import (
    SPOTIFY_DAILY_SEARCH_SOFT_CAP,
    load_cli_dashboard,
)


class CliDashboardTests(unittest.TestCase):
    def test_empty_data_dir_stage_yandex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            dash = load_cli_dashboard(
                data_dir=data,
                yandex_token_path=data / "yandex-token-music.json",
                spotify_token_path=data / "spotify-token.json",
                snapshot_path=data / "library-snapshot.json",
            )
        self.assertFalse(dash.yandex_token)
        self.assertFalse(dash.spotify_token)
        self.assertIn("Яндекс", dash.stage_hint)
        by_cmd = {c.command: c for c in dash.commands}
        self.assertTrue(by_cmd["auth-implicit"].enabled)
        self.assertFalse(by_cmd["migrate-dry-run"].enabled)
        self.assertEqual(dash.bars[1].total, SPOTIFY_DAILY_SEARCH_SOFT_CAP)

    def test_progress_from_snapshot_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "yandex-token-music.json").write_text(
                json.dumps({"access_token": "y"}),
                encoding="utf-8",
            )
            (data / "spotify-token.json").write_text(
                json.dumps({"access_token": "s"}),
                encoding="utf-8",
            )
            (data / "library-snapshot.json").write_text(
                json.dumps(
                    {
                        "liked_tracks_count": 100,
                        "playlists_count": 3,
                        "liked_tracks": [],
                        "playlists": [],
                    }
                ),
                encoding="utf-8",
            )
            (data / "dry-run-state.json").write_text(
                json.dumps(
                    {
                        "processed": {
                            "yandex:1": {
                                "source_id": "yandex:1",
                                "status": "exact",
                            },
                            "yandex:2": {
                                "source_id": "yandex:2",
                                "status": "review",
                            },
                            "yandex:3": {
                                "source_id": "yandex:3",
                                "status": "review",
                                "decision": "skip",
                                "selected": {"id": "x"},
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            dash = load_cli_dashboard(
                data_dir=data,
                yandex_token_path=data / "yandex-token-music.json",
                spotify_token_path=data / "spotify-token.json",
                snapshot_path=data / "library-snapshot.json",
            )

        self.assertTrue(dash.yandex_token)
        self.assertEqual(dash.likes_total, 100)
        self.assertEqual(dash.dry_done, 3)
        self.assertEqual(dash.review_open, 1)
        by_cmd = {c.command: c for c in dash.commands}
        self.assertTrue(by_cmd["migrate-dry-run"].enabled)
        self.assertTrue(by_cmd["review"].enabled)
        dry_bar = next(b for b in dash.bars if b.key == "dry")
        self.assertEqual(dry_bar.done, 3)
        self.assertEqual(dry_bar.total, 100)


if __name__ == "__main__":
    unittest.main()
