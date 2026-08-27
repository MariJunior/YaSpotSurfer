from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from yandex_spike.application.bot_playlists import PlaylistsError, migrate_playlists_for_user
from yandex_spike.telegram.copy import playlists_done_text


class BotPlaylistsTests(unittest.TestCase):
    def test_requires_scan(self) -> None:
        store = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PlaylistsError) as ctx:
                migrate_playlists_for_user(store, 1, data_root=Path(tmp))
            self.assertIn("/scan", str(ctx.exception))

    @patch("yandex_spike.application.bot_playlists.write_matched_tracks")
    @patch("yandex_spike.application.bot_playlists.run_dry_run")
    @patch("yandex_spike.application.bot_playlists.fetch_playlist_with_tracks")
    @patch("yandex_spike.application.bot_playlists.load_cached_playlist")
    @patch("yandex_spike.application.bot_playlists.SpotifyPlaylistClient")
    @patch("yandex_spike.application.bot_playlists.SpotifySearcher")
    @patch("yandex_spike.application.bot_playlists.resolve_spotify_access")
    def test_copies_shortest_playlist(
        self,
        access_mock,
        searcher_cls,
        client_cls,
        cache_mock,
        fetch_mock,
        dry_mock,
        write_mock,
    ) -> None:
        del searcher_cls
        access_mock.return_value = "tok"
        cache_mock.return_value = {
            "kind": 10,
            "title": "Short",
            "tracks": [
                {
                    "sourceId": "1",
                    "title": "A",
                    "artists": [{"name": "B"}],
                    "durationMs": 1000,
                }
            ],
        }
        fetch_mock.side_effect = cache_mock
        dry_mock.return_value = {
            "processed": {
                "yandex:1": {
                    "source_id": "yandex:1",
                    "status": "exact",
                    "selected": {"id": "spotify:a", "title": "A"},
                }
            },
            "cancelled": False,
            "track_count": 1,
            "counts": {},
            "results": [],
        }
        write_mock.return_value = {
            "migration_id": "m1",
            "write_state": {},
            "counts": {"saved": 1, "already": 0, "skipped": 0},
            "track_count": 1,
            "results": [],
            "cancelled": False,
        }
        client = client_cls.return_value
        client.find_or_create.return_value = "pl-id"

        store = MagicMock()
        store.read_yandex_token.return_value = "ya-tok"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "3"
            user_dir.mkdir()
            (user_dir / "library-snapshot.json").write_text(
                json.dumps(
                    {
                        "playlists": [
                            {"kind": 10, "title": "Short", "track_count": 2, "uid": 1},
                            {"kind": 99, "title": "Long", "track_count": 500, "uid": 1},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = migrate_playlists_for_user(store, 3, data_root=root)
            self.assertEqual(result.playlist_count, 1)
            self.assertIn("YaSpotSurfer: Short", result.entries[0]["spotify_playlist_name"])
            self.assertTrue(result.report_path.exists())


class PlaylistsCopyTests(unittest.TestCase):
    def test_done_lists_entries(self) -> None:
        text = playlists_done_text(
            playlist_count=1,
            entries=[
                {
                    "spotify_playlist_name": "YaSpotSurfer: Short",
                    "counts": {"saved": 3, "already": 0, "skipped": 1},
                }
            ],
            cancelled=False,
        )
        self.assertIn("Short", text)
        self.assertIn("3", text)


if __name__ == "__main__":
    unittest.main()
