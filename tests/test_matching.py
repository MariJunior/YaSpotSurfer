from __future__ import annotations

import json
import unittest
from pathlib import Path

from yandex_spike.domain.matching import (
    MatchConfig,
    match_track,
    score_candidate,
)
from yandex_spike.domain.transliteration import transliterate
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "matching_cases.json"
AUTO_STATUSES = {"exact", "high-confidence"}


def _track(payload: dict):
    return track_from_yandex_snapshot(payload)


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = {
            item["id"]: item
            for item in json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]
        }

    def _run_case(self, case_id: str):
        case = self.cases[case_id]
        source = _track(case["source"])
        candidates = [_track(item) for item in case["candidates"]]
        return match_track(source, candidates), case

    def test_fixture_statuses(self) -> None:
        for case_id, case in self.cases.items():
            result, _ = self._run_case(case_id)
            if case.get("forbid_auto"):
                self.assertNotIn(
                    result.status,
                    AUTO_STATUSES,
                    msg=f"{case_id} не должен быть auto, status={result.status}",
                )
            expected = case.get("expect_status")
            if expected:
                self.assertEqual(result.status, expected, msg=case_id)
            selected_id = case.get("expect_selected")
            if selected_id and result.selected:
                self.assertTrue(
                    result.selected.track.id.endswith(selected_id),
                    msg=f"{case_id} selected {result.selected.track.id}",
                )

    def test_wrong_auto_is_regression(self) -> None:
        for case_id, case in self.cases.items():
            if not case.get("forbid_auto"):
                continue
            result, _ = self._run_case(case_id)
            self.assertIsNone(
                result.selected if result.status in AUTO_STATUSES else None,
                msg=f"wrong match: {case_id}",
            )
            self.assertNotIn(result.status, AUTO_STATUSES, msg=case_id)

    def test_yandex_version_field_becomes_tag(self) -> None:
        track = _track(
            {
                "sourceId": "2773110",
                "title": "Time",
                "version": "2011 - Remaster",
                "artists": [{"name": "Pink Floyd"}],
            }
        )
        self.assertEqual(track.normalized_title, "time")
        self.assertIn("remaster", track.version_tags)

    def test_artist_order_does_not_break_exact(self) -> None:
        result, _ = self._run_case("feat-same-recording")
        self.assertEqual(result.status, "exact")
        self.assertGreaterEqual(result.selected.reasons["artist"], 0.98)

    def test_transliteration_table(self) -> None:
        self.assertEqual(transliterate("я влюблен"), "ya vlyublen")
        self.assertEqual(transliterate("пекинский велосипед"), "pekinskiy velosiped")

    def test_score_is_reproducible(self) -> None:
        source = _track(self.cases["original-self"]["source"])
        candidate = _track(self.cases["original-self"]["candidates"][0])
        first = score_candidate(source, candidate)
        second = score_candidate(source, candidate, MatchConfig())
        self.assertEqual(first.score, second.score)
        self.assertEqual(first.reasons, second.reasons)

    def test_ambiguous_two_autos_go_to_review(self) -> None:
        source = _track(
            {
                "sourceId": "amb-src",
                "title": "Clone",
                "durationMs": 200000,
                "artists": [{"name": "Twin"}],
                "album": {"title": "A"},
            }
        )
        left = _track(
            {
                "sourceId": "amb-a",
                "title": "Clone",
                "durationMs": 200000,
                "artists": [{"name": "Twin"}],
                "album": {"title": "A"},
            }
        )
        right = _track(
            {
                "sourceId": "amb-b",
                "title": "Clone",
                "durationMs": 200000,
                "artists": [{"name": "Twin"}],
                "album": {"title": "A"},
            }
        )
        result = match_track(source, [left, right])
        self.assertEqual(result.status, "review")
        self.assertIsNone(result.selected)

    def test_same_isrc_is_not_ambiguous(self) -> None:
        result, _ = self._run_case("same-isrc-two-spotify-ids")
        self.assertEqual(result.status, "exact")
        self.assertIsNotNone(result.selected)
        self.assertEqual(len(result.candidates), 1)

    def test_missing_duration_reaches_auto_at_090(self) -> None:
        source = _track(
            {
                "sourceId": "hawaii-src",
                "title": "He Mele Lahui Hawaii",
                "artists": [{"name": "The Rose Ensemble"}],
            }
        )
        candidate = _track(
            {
                "sourceId": "hawaii-dst",
                "title": "He Mele Lahui Hawaii",
                "durationMs": 161346,
                "artists": [{"name": "The Rose Ensemble"}],
                "album": {"title": "Na Mele Hawaii"},
            }
        )
        result = match_track(source, [candidate])
        self.assertIsNotNone(result.selected)
        self.assertGreaterEqual(result.selected.score, 0.90)
        self.assertIn(result.status, AUTO_STATUSES)

    def test_version_cap_stays_below_auto(self) -> None:
        config = MatchConfig()
        self.assertLess(config.version_cap(), config.auto_threshold)
        self.assertEqual(config.auto_threshold, 0.90)

    def test_hard_duration_miss_is_not_auto(self) -> None:
        result, _ = self._run_case("different-duration")
        self.assertEqual(result.status, "review")
        self.assertLess(result.selected.score, MatchConfig().auto_threshold)

    def test_artist_drops_gruppa_prefix(self) -> None:
        source = _track(
            {
                "sourceId": "zod-src",
                "title": "Живём дальше!",
                "durationMs": 261870,
                "artists": [{"name": "Группа Зодчие"}],
                "album": {"title": "X"},
            }
        )
        candidate = _track(
            {
                "sourceId": "zod-dst",
                "title": "Живём дальше!",
                "durationMs": 261877,
                "artists": [{"name": "Зодчие"}],
                "album": {"title": "X"},
            }
        )
        scored = score_candidate(source, candidate)
        self.assertGreaterEqual(scored.reasons["artist"], 0.98)


if __name__ == "__main__":
    unittest.main()
