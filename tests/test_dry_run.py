from __future__ import annotations

import unittest

from yandex_spike.application.dry_run import run_dry_run
from yandex_spike.application.search_query import (
    build_fallback_query,
    build_search_query,
)
from yandex_spike.infrastructure.spotify.mapper import track_from_spotify_search
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot


class FakeSearcher:
    def __init__(self, mapping: dict[str, list]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def search_track(self, track):
        self.calls.append(track.id)
        return list(self.mapping.get(track.id, []))


class DryRunTests(unittest.TestCase):
    def test_search_query_uses_field_filters(self) -> None:
        track = track_from_yandex_snapshot(
            {
                "sourceId": "1",
                "title": 'Lullaby: "mix"',
                "artists": [{"name": "The Cure"}],
            }
        )
        query = build_search_query(track)
        self.assertIn('track:"Lullaby   mix"', query)
        self.assertIn('artist:"The Cure"', query)
        self.assertEqual(build_fallback_query(track), "Lullaby   mix The Cure")

    def test_dry_run_does_not_write_and_counts_statuses(self) -> None:
        source = track_from_yandex_snapshot(
            {
                "sourceId": "self-1",
                "title": "Lullaby",
                "durationMs": 246000,
                "artists": [{"name": "The Cure"}],
                "album": {"title": "Disintegration"},
            }
        )
        hit = track_from_spotify_search(
            {
                "id": "0ZYdUkAQmKHsaKRmq8tWSE",
                "name": "Lullaby",
                "duration_ms": 246000,
                "artists": [{"name": "The Cure"}],
                "album": {"name": "Disintegration"},
                "external_ids": {"isrc": "GBUM71000213"},
            }
        )
        searcher = FakeSearcher({source.id: [hit]})
        report = run_dry_run([source], searcher)
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["wrote_to_spotify"])
        self.assertEqual(report["tz_counts"]["exact"], 1)
        self.assertEqual(report["results"][0]["status"], "exact")
        self.assertEqual(searcher.calls, [source.id])

    def test_resume_skips_search(self) -> None:
        source = track_from_yandex_snapshot(
            {"sourceId": "2", "title": "Hello", "artists": [{"name": "Adele"}]}
        )
        cached = {
            source.id: {
                "source_id": source.id,
                "title": "Hello",
                "status": "review",
                "score": 0.8,
                "selected": None,
                "candidates": [],
            }
        }
        searcher = FakeSearcher({})
        report = run_dry_run([source], searcher, processed=cached)
        self.assertEqual(searcher.calls, [])
        self.assertEqual(report["results"][0]["status"], "review")
        self.assertTrue(report["resumed"])

    def test_reclassify_cached_review_to_auto(self) -> None:
        source = track_from_yandex_snapshot(
            {
                "sourceId": "hawaii",
                "title": "He Mele",
                "artists": [{"name": "The Rose Ensemble"}],
            }
        )
        cached = {
            source.id: {
                "source_id": source.id,
                "title": "He Mele",
                "status": "review",
                "score": 0.905,
                "selected": {"id": "spotify:abc", "title": "He Mele"},
                "candidates": [
                    {
                        "id": "spotify:abc",
                        "score": 0.905,
                        "reasons": {
                            "title": 1.0,
                            "artist": 1.0,
                            "album": 0.7,
                            "duration": 0.5,
                            "version": 1.0,
                        },
                    }
                ],
            }
        }
        searcher = FakeSearcher({})
        report = run_dry_run([source], searcher, processed=cached)
        self.assertEqual(report["results"][0]["status"], "high-confidence")
        self.assertEqual(searcher.calls, [])

    def test_empty_search_is_not_found(self) -> None:
        source = track_from_yandex_snapshot(
            {"sourceId": "3", "title": "Unknown", "artists": [{"name": "Nobody"}]}
        )
        report = run_dry_run([source], FakeSearcher({}))
        self.assertEqual(report["results"][0]["status"], "not-found")
        self.assertEqual(report["tz_counts"]["not_found"], 1)


if __name__ == "__main__":
    unittest.main()
