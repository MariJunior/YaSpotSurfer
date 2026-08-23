from __future__ import annotations

import unittest

from yandex_spike.application.migrate import migrate_liked_tracks
from yandex_spike.application.spotify_uri import to_track_uri


class FakeWriter:
    def __init__(self, already: set[str] | None = None) -> None:
        self.already = set(already or [])
        self.saved: list[str] = []
        self.contains_calls: list[str] = []

    def contains(self, uri: str) -> bool:
        self.contains_calls.append(uri)
        return uri in self.already

    def save(self, uri: str) -> None:
        self.saved.append(uri)
        self.already.add(uri)


class MigrateTests(unittest.TestCase):
    def test_to_track_uri(self) -> None:
        self.assertEqual(
            to_track_uri("spotify:0ZYdUkAQmKHsaKRmq8tWSE"),
            "spotify:track:0ZYdUkAQmKHsaKRmq8tWSE",
        )
        self.assertEqual(
            to_track_uri("spotify:track:abc"),
            "spotify:track:abc",
        )

    def test_writes_only_auto_matches(self) -> None:
        writer = FakeWriter()
        rows = [
            {
                "source_id": "yandex:1",
                "title": "A",
                "status": "exact",
                "selected": {"id": "spotify:aaa", "title": "A"},
            },
            {
                "source_id": "yandex:2",
                "title": "B",
                "status": "review",
                "selected": {"id": "spotify:bbb", "title": "B"},
            },
            {
                "source_id": "yandex:3",
                "title": "C",
                "status": "high-confidence",
                "selected": {"id": "spotify:ccc", "title": "C"},
            },
        ]
        report = migrate_liked_tracks(rows, writer, migration_id="mig-1")
        self.assertEqual(writer.saved, ["spotify:track:aaa", "spotify:track:ccc"])
        self.assertEqual(report["counts"]["saved"], 2)
        self.assertEqual(report["counts"]["skipped"], 1)

    def test_already_liked_is_idempotent(self) -> None:
        writer = FakeWriter(already={"spotify:track:aaa"})
        rows = [
            {
                "source_id": "yandex:1",
                "title": "A",
                "status": "exact",
                "selected": {"id": "spotify:aaa", "title": "A"},
            }
        ]
        report = migrate_liked_tracks(rows, writer, migration_id="mig-1")
        self.assertEqual(writer.saved, [])
        self.assertEqual(report["results"][0]["write_status"], "already")

    def test_resume_skips_contains(self) -> None:
        writer = FakeWriter()
        cached = {
            "yandex:1": {
                "source_id": "yandex:1",
                "write_status": "saved",
                "spotify_uri": "spotify:track:aaa",
            }
        }
        rows = [
            {
                "source_id": "yandex:1",
                "title": "A",
                "status": "exact",
                "selected": {"id": "spotify:aaa", "title": "A"},
            }
        ]
        report = migrate_liked_tracks(
            rows, writer, write_state=cached, migration_id="mig-1"
        )
        self.assertEqual(writer.contains_calls, [])
        self.assertEqual(writer.saved, [])
        self.assertEqual(report["results"][0]["write_status"], "saved")

    def test_review_accept_writes_and_skip_does_not(self) -> None:
        writer = FakeWriter()
        rows = [
            {
                "source_id": "yandex:2",
                "title": "B",
                "status": "review",
                "decision": "accept",
                "selected": {"id": "spotify:bbb", "title": "B"},
            },
            {
                "source_id": "yandex:9",
                "title": "Skip me",
                "status": "exact",
                "decision": "skip",
                "selected": {"id": "spotify:zzz", "title": "Z"},
            },
        ]
        report = migrate_liked_tracks(rows, writer, migration_id="mig-2")
        self.assertEqual(writer.saved, ["spotify:track:bbb"])
        self.assertEqual(report["counts"]["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
