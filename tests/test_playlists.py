from __future__ import annotations

import unittest

from yandex_spike.application.migrate_playlists import (
    playlist_migration_entry,
    sandbox_playlist_name,
    select_playlist_headers,
)


HEADERS = [
    {"kind": 1061, "title": "какая-то дичь", "track_count": 1},
    {"kind": 1062, "title": "оркестра", "track_count": 2},
    {"kind": 1063, "title": "помонтируем?", "track_count": 6},
    {"kind": 1000, "title": "пусто", "track_count": 0},
]


class PlaylistSelectTests(unittest.TestCase):
    def test_sandbox_name(self) -> None:
        self.assertEqual(
            sandbox_playlist_name("оркестра"),
            "YaSpotSurfer: оркестра",
        )
        self.assertEqual(sandbox_playlist_name("  "), "YaSpotSurfer: untitled")

    def test_selects_smallest_nonempty(self) -> None:
        selected = select_playlist_headers(HEADERS, limit=2)
        self.assertEqual([row["kind"] for row in selected], [1061, 1062])

    def test_selects_by_kind(self) -> None:
        selected = select_playlist_headers(HEADERS, limit=9, kind=1063)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["title"], "помонтируем?")

    def test_unknown_kind_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            select_playlist_headers(HEADERS, kind=1)

    def test_empty_kind_is_not_selected(self) -> None:
        with self.assertRaises(RuntimeError):
            select_playlist_headers(HEADERS, kind=1000)

    def test_limit_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            select_playlist_headers(HEADERS, limit=0)

    def test_report_entry_drops_write_state(self) -> None:
        entry = playlist_migration_entry(
            yandex_kind=1062,
            yandex_title="оркестра",
            spotify_playlist_id="abc",
            spotify_playlist_name="YaSpotSurfer: оркестра",
            migrate_report={
                "track_count": 2,
                "counts": {"saved": 2},
                "results": [{"write_status": "saved"}],
                "write_state": {"secret": True},
            },
        )
        self.assertNotIn("write_state", entry)
        self.assertEqual(entry["spotify_playlist_id"], "abc")
        self.assertEqual(entry["counts"]["saved"], 2)


if __name__ == "__main__":
    unittest.main()
