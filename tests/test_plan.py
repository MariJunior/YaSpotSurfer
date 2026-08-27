from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from yandex_spike.application.dry_run import run_dry_run
from yandex_spike.application.plan import PlanError, PlanQuotaExceededError, plan_liked_tracks
from yandex_spike.domain.entities import Track
from yandex_spike.telegram.copy import plan_done_text, plan_quota_exceeded_text


def _track(i: int) -> Track:
    return Track(
        id=f"yandex:{i}",
        title=f"Song {i}",
        normalized_title=f"song {i}",
        artists=(),
        duration_ms=180000,
    )


class DryRunCancelTests(unittest.TestCase):
    def test_should_stop_sets_cancelled_and_keeps_processed(self) -> None:
        searcher = MagicMock()
        searcher.search_track.return_value = []
        calls = {"n": 0}

        def stop() -> bool:
            calls["n"] += 1
            return calls["n"] > 2

        report = run_dry_run(
            [_track(1), _track(2), _track(3), _track(4)],
            searcher,
            should_stop=stop,
        )
        self.assertTrue(report["cancelled"])
        self.assertEqual(report["track_count"], 2)
        self.assertEqual(len(report["processed"]), 2)


class PlanUseCaseTests(unittest.TestCase):
    def test_requires_snapshot(self) -> None:
        store = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PlanError) as ctx:
                plan_liked_tracks(store, 1, data_root=Path(tmp))
            self.assertIn("/scan", str(ctx.exception))

    @patch("yandex_spike.application.plan.SpotifySearcher")
    @patch("yandex_spike.application.plan.resolve_spotify_access")
    @patch("yandex_spike.application.plan.run_dry_run")
    def test_plan_writes_report(
        self,
        dry_mock,
        access_mock,
        searcher_cls,
    ) -> None:
        del searcher_cls
        access_mock.return_value = "tok"
        dry_mock.return_value = {
            "track_count": 3,
            "cancelled": False,
            "processed": {"yandex:1": {"status": "exact"}},
            "tz_counts": {"exact": 2, "review": 1, "not_found": 0},
            "counts": {},
            "results": [],
        }
        store = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "5"
            user_dir.mkdir()
            (user_dir / "library-snapshot.json").write_text(
                json.dumps(
                    {
                        "liked_tracks": [
                            {
                                "sourceId": "1",
                                "title": "A",
                                "artists": [{"name": "B"}],
                                "durationMs": 1000,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = plan_liked_tracks(store, 5, data_root=root, resume=False)
            self.assertEqual(result.auto_count, 2)
            self.assertEqual(result.review_count, 1)
            self.assertTrue(result.report_path.exists())
            self.assertTrue(result.state_path.exists())

    def test_plan_done_copy(self) -> None:
        text = plan_done_text(
            track_count=10,
            auto_count=7,
            review_count=2,
            not_found_count=1,
            cancelled=False,
            resumed=False,
        )
        self.assertIn("Уверенно", text)
        self.assertIn("7", text)

    def test_quota_exceeded_error_carries_done(self) -> None:
        err = PlanQuotaExceededError(done=650, retry_after_sec=64154)
        self.assertEqual(err.done, 650)
        self.assertIn("650", str(err))
        hours = max(1, (err.retry_after_sec + 3599) // 3600)
        text = plan_quota_exceeded_text(done=err.done, hours=hours)
        self.assertIn("650", text)
        self.assertIn("18", text)


class SpotifyPersistRateLimitTests(unittest.TestCase):
    @patch("yandex_spike.spotify.time.sleep", return_value=None)
    @patch("yandex_spike.spotify.requests.request")
    def test_persist_retries_short_429_until_200(self, request_mock, _sleep) -> None:
        from yandex_spike.spotify import _api

        limited = MagicMock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "20"}
        limited.text = '{"error":{"status":429,"message":"Too many requests"}}'
        ok = MagicMock()
        ok.status_code = 200
        request_mock.side_effect = [limited, ok]

        response = _api(
            "GET",
            "/search",
            "tok",
            params={"q": "x"},
            persist_rate_limit=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_mock.call_count, 2)

    @patch("yandex_spike.spotify.requests.request")
    def test_quota_exceeded_stops_instead_of_spinning(self, request_mock) -> None:
        from yandex_spike.spotify import SpotifyQuotaExceeded, _api

        limited = MagicMock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "64154"}
        limited.text = (
            '{"error":{"status":429,"message":"Too many requests",'
            '"reason":"QUOTA_EXCEEDED"}}'
        )
        request_mock.return_value = limited

        with self.assertRaises(SpotifyQuotaExceeded) as ctx:
            _api(
                "GET",
                "/search",
                "tok",
                params={"q": "x"},
                persist_rate_limit=True,
            )
        self.assertEqual(ctx.exception.retry_after_sec, 64154)
        self.assertEqual(request_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
