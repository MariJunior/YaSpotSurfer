from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from yandex_spike.domain.normalization import normalize_artist, normalize_title
from yandex_spike.infrastructure.file_store import (
    load_tracks,
    save_tracks,
    track_from_serialized,
    tracks_to_jsonable,
)
from yandex_spike.infrastructure.spotify.mapper import track_from_spotify_search
from yandex_spike.infrastructure.yandex.mapper import (
    playlist_from_yandex_snapshot,
    track_from_yandex_snapshot,
)


class NormalizationTests(unittest.TestCase):
    def test_yo_and_case(self) -> None:
        result = normalize_title("Ёлка — Прованс")
        self.assertEqual(result.text, "елка прованс")

    def test_feat_and_brackets_stripped_from_text(self) -> None:
        result = normalize_title("Song Name (feat. Someone) [Remastered 2011]")
        self.assertEqual(result.text, "song name")
        self.assertIn("remastered", result.version_tags)

    def test_remaster_forms_collapse_to_same_text(self) -> None:
        original = normalize_title("Song Name")
        bracket = normalize_title("Song Name (Remastered 2011)")
        dashed = normalize_title("Song Name - 2011 Remaster")
        short = normalize_title("Song Name (Remaster)")
        self.assertEqual(original.text, "song name")
        self.assertEqual(bracket.text, original.text)
        self.assertEqual(dashed.text, original.text)
        self.assertEqual(short.text, original.text)
        self.assertIn("remastered", bracket.version_tags)
        self.assertIn("remaster", dashed.version_tags)

    def test_dash_does_not_drop_elka_provanse(self) -> None:
        result = normalize_title("Ёлка — Прованс")
        self.assertEqual(result.text, "елка прованс")

    def test_year_title_kept_without_version_tag(self) -> None:
        result = normalize_title("1999")
        self.assertEqual(result.text, "1999")
        self.assertEqual(result.version_tags, ())

    def test_live_not_inside_olivia(self) -> None:
        result = normalize_title("Olivia")
        self.assertEqual(result.text, "olivia")
        self.assertEqual(result.version_tags, ())

    def test_artist_punct(self) -> None:
        self.assertEqual(normalize_artist("Би-2"), "би 2")

    def test_yandex_mapper(self) -> None:
        track = track_from_yandex_snapshot(
            {
                "sourceId": "1",
                "title": "Lullaby (Remastered)",
                "artists": [{"id": 2, "name": "The Cure"}],
                "durationMs": 1000,
            }
        )
        self.assertEqual(track.normalized_title, "lullaby")
        self.assertEqual(track.artists[0].normalized_name, "the cure")
        self.assertEqual(track.provider_ids, (("yandex", "1"),))

    def test_spotify_mapper_isrc(self) -> None:
        track = track_from_spotify_search(
            {
                "id": "abc",
                "name": "Lullaby - Remastered",
                "artists": [{"id": "x", "name": "The Cure"}],
                "duration_ms": 246000,
                "external_ids": {"isrc": "GBUM71000213"},
            }
        )
        self.assertEqual(track.isrc, "GBUM71000213")
        self.assertIn("remastered", track.version_tags)
        self.assertEqual(track.normalized_title, "lullaby")

    def test_roundtrip_serializer(self) -> None:
        track = track_from_yandex_snapshot(
            {
                "sourceId": "1",
                "title": "Lullaby (Remastered)",
                "artists": [{"id": 2, "name": "The Cure"}],
                "durationMs": 1000,
            }
        )
        restored = track_from_serialized(tracks_to_jsonable([track])[0])
        self.assertEqual(restored.id, track.id)
        self.assertEqual(restored.normalized_title, track.normalized_title)
        self.assertEqual(restored.artists[0].normalized_name, "the cure")
        self.assertIsNone(restored.raw)

    def test_file_store_roundtrip(self) -> None:
        track = track_from_yandex_snapshot(
            {"sourceId": "9", "title": "Hello", "artists": [{"name": "Adele"}]}
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracks.json"
            save_tracks(path, [track])
            loaded = load_tracks(path)
        self.assertEqual(loaded[0].provider_ids, (("yandex", "9"),))

    def test_playlist_mapper(self) -> None:
        playlist = playlist_from_yandex_snapshot({"kind": 1063, "title": "test"})
        self.assertEqual(playlist.id, "yandex:1063")
        self.assertEqual(playlist.track_ids, ())


if __name__ == "__main__":
    unittest.main()
