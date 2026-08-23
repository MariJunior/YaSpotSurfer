from __future__ import annotations

import unittest

from yandex_music.exceptions import TimedOutError

from yandex_spike.inspector import _normalize_track_dict
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot
from yandex_spike.infrastructure.yandex.network import call_yandex


class YandexNetworkTests(unittest.TestCase):
    def test_retries_then_succeeds(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimedOutError()
            return "ok"

        self.assertEqual(call_yandex("tracks", flaky, sleep_fn=lambda _: None), "ok")
        self.assertEqual(calls["n"], 3)

    def test_gives_up_with_runtime_error(self) -> None:
        def always_fail() -> None:
            raise TimedOutError()

        with self.assertRaises(RuntimeError):
            call_yandex("tracks", always_fail, sleep_fn=lambda _: None)

    def test_raw_track_dict_maps_to_domain(self) -> None:
        snapshot = _normalize_track_dict(
            {
                "id": "57389579",
                "title": "He Mele",
                "duration_ms": 161340,
                "artists": [{"id": 1, "name": "The Rose Ensemble"}],
                "albums": [{"id": 2, "title": "Na Mele", "year": 2007}],
            }
        )
        track = track_from_yandex_snapshot(snapshot)
        self.assertEqual(track.id, "yandex:57389579")
        self.assertEqual(track.duration_ms, 161340)
        self.assertEqual(track.artists[0].name, "The Rose Ensemble")


if __name__ == "__main__":
    unittest.main()
