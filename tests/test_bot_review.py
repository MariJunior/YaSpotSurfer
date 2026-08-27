from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from yandex_spike.application.bot_review import (
    BotReviewError,
    decide_review,
    peek_next_review,
)
from yandex_spike.application.review import accept_candidate, list_open_reviews
from yandex_spike.telegram.copy import review_card_text


class OpenReviewQueueTests(unittest.TestCase):
    def test_open_excludes_decided_and_orders_deferred(self) -> None:
        processed = {
            "yandex:2": {
                "source_id": "yandex:2",
                "status": "review",
                "candidates": [{"id": "s2", "title": "B"}],
            },
            "yandex:1": {
                "source_id": "yandex:1",
                "status": "review",
                "candidates": [{"id": "s1", "title": "A"}],
            },
            "yandex:3": {
                "source_id": "yandex:3",
                "status": "review",
                "decision": "skip",
                "candidates": [],
            },
            "yandex:9": {"source_id": "yandex:9", "status": "exact"},
        }
        open_rows = list_open_reviews(processed, defer_ids={"yandex:1"})
        self.assertEqual([row["source_id"] for row in open_rows], ["yandex:2", "yandex:1"])

    def test_accept_candidate_sets_selected(self) -> None:
        processed = {
            "yandex:1": {
                "source_id": "yandex:1",
                "status": "review",
                "selected": None,
                "candidates": [
                    {"id": "sp:a", "title": "A", "artists": ["X"], "score": 0.8},
                    {"id": "sp:b", "title": "B", "artists": ["Y"], "score": 0.79},
                ],
            }
        }
        updated = accept_candidate(processed, "yandex:1", 1)
        self.assertEqual(updated["decision"], "accept")
        self.assertEqual(updated["selected"]["id"], "sp:b")
        self.assertEqual(updated["score"], 0.79)


class BotReviewUseCaseTests(unittest.TestCase):
    def _write_state(self, root: Path, telegram_id: int, processed: dict) -> None:
        user_dir = root / str(telegram_id)
        user_dir.mkdir(parents=True)
        (user_dir / "dry-run-state.json").write_text(
            json.dumps({"processed": processed}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_peek_and_accept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_state(
                root,
                7,
                {
                    "yandex:1": {
                        "source_id": "yandex:1",
                        "title": "Lullaby",
                        "artists": ["The Cure"],
                        "status": "review",
                        "selected": None,
                        "candidates": [
                            {
                                "id": "sp:1",
                                "title": "Lullaby",
                                "artists": ["The Cure"],
                                "score": 0.96,
                            },
                            {
                                "id": "sp:2",
                                "title": "Lullaby (Live)",
                                "artists": ["The Cure"],
                                "score": 0.61,
                            },
                        ],
                    }
                },
            )
            card = peek_next_review(7, data_root=root)
            assert card is not None
            self.assertEqual(card.source_id, "yandex:1")
            self.assertEqual(card.open_remaining, 1)
            result = decide_review(
                7,
                "yandex:1",
                action="accept",
                candidate_index=0,
                data_root=root,
            )
            self.assertEqual(result.open_remaining, 0)
            self.assertEqual(result.chosen_title, "Lullaby")
            self.assertIsNone(peek_next_review(7, data_root=root))

    def test_requires_plan_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BotReviewError):
                peek_next_review(1, data_root=Path(tmp))


class ReviewCopyTests(unittest.TestCase):
    def test_card_lists_candidates(self) -> None:
        text = review_card_text(
            title="Lullaby",
            artists=("The Cure",),
            candidates=(
                {"title": "Lullaby", "artists": ["The Cure"], "score": 0.96},
                {"title": "Lullaby (Live)", "artists": ["The Cure"], "score": 0.61},
            ),
            open_remaining=3,
        )
        self.assertIn("Яндекс: The Cure — Lullaby", text)
        self.assertIn("1. The Cure — Lullaby  (0.96)", text)
        self.assertIn("осталось 3", text)


if __name__ == "__main__":
    unittest.main()
