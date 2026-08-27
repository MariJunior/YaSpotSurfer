from __future__ import annotations

import unittest

from yandex_spike.application.review import (
    accept_candidate,
    apply_decision,
    list_open_reviews,
    list_review_queue,
)


class ReviewTests(unittest.TestCase):
    def test_accept_and_list(self) -> None:
        processed = {
            "yandex:1": {
                "source_id": "yandex:1",
                "status": "review",
                "selected": {"id": "spotify:x", "title": "X"},
            },
            "yandex:2": {"source_id": "yandex:2", "status": "exact", "selected": {}},
        }
        apply_decision(processed, "yandex:1", "accept")
        queue = list_review_queue(processed)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["decision"], "accept")
        self.assertEqual(list_open_reviews(processed), [])

    def test_accept_without_selected_fails(self) -> None:
        processed = {
            "yandex:1": {"source_id": "yandex:1", "status": "review", "selected": None}
        }
        with self.assertRaises(RuntimeError):
            apply_decision(processed, "yandex:1", "accept")

    def test_accept_candidate_index(self) -> None:
        processed = {
            "yandex:1": {
                "source_id": "yandex:1",
                "status": "review",
                "selected": None,
                "candidates": [
                    {"id": "a", "title": "A", "artists": []},
                    {"id": "b", "title": "B", "artists": []},
                ],
            }
        }
        accept_candidate(processed, "yandex:1", 1)
        self.assertEqual(processed["yandex:1"]["selected"]["id"], "b")


if __name__ == "__main__":
    unittest.main()
