from __future__ import annotations

from collections.abc import Callable
import time

from yandex_spike.application.search_query import (
    build_fallback_query,
    build_search_query,
)
from yandex_spike.domain.entities import Track
from yandex_spike.infrastructure.spotify.mapper import track_from_spotify_search
from yandex_spike.spotify import _api, _sleep_interruptible


class SpotifySearcher:
    """GET /search. Write-методов нет — dry-run не может случайно записать.

    Краткий 429: ``persist_rate_limit`` ждёт и продолжает.
    ``QUOTA_EXCEEDED`` / Retry-After на часы поднимает ``SpotifyQuotaExceeded`` выше.
    После короткого 429 пропускаем fallback-search и чуть увеличиваем паузу.
    """

    def __init__(
        self,
        access_token: str,
        *,
        pause_sec: float = 1.25,
        should_stop: Callable[[], bool] | None = None,
        on_wait: Callable[[str], None] | None = None,
    ) -> None:
        self._access_token = access_token
        # База ~1.25с: при ~650/сутки длинный прогон всё равно упирается в квоту, не в секунды.
        self._pause_sec = pause_sec
        self._min_pause = pause_sec
        self._should_stop = should_stop
        self._on_wait = on_wait
        # После 429 не делаем второй (fallback) search — экономим квоту.
        self._skip_fallback_until = 0.0
        self._searches_ok = 0

    def search_track(self, track: Track) -> list[Track]:
        primary = self._search(build_search_query(track))
        if primary:
            return primary
        if time.monotonic() < self._skip_fallback_until:
            return []
        fallback = build_fallback_query(track)
        if fallback:
            return self._search(fallback)
        return []

    def _search(self, query: str) -> list[Track]:
        response = _api(
            "GET",
            "/search",
            self._access_token,
            params={
                "q": query,
                "type": "track",
                "limit": 10,
                "market": "from_token",
            },
            should_stop=self._should_stop,
            on_wait=self._on_rate_wait,
            persist_rate_limit=True,
        )

        if response.status_code != 200:
            excerpt = (response.text or "")[:160]
            raise RuntimeError(
                f"Spotify search HTTP {response.status_code}: {excerpt}"
            )

        self._searches_ok += 1
        # Каждые 100 успешных — чуть отпускаем паузу к базе (не ниже min).
        if self._searches_ok % 100 == 0 and self._pause_sec > self._min_pause:
            self._pause_sec = max(self._min_pause, self._pause_sec * 0.9)

        if self._pause_sec > 0:
            _sleep_interruptible(
                self._pause_sec,
                should_stop=self._should_stop,
                on_tick=None,
                chunk_sec=min(1.0, self._pause_sec),
            )

        items = response.json().get("tracks", {}).get("items") or []
        return [track_from_spotify_search(item) for item in items if item]

    def _on_rate_wait(self, text: str) -> None:
        # 10 минут без fallback после любого 429-ожидания.
        self._skip_fallback_until = time.monotonic() + 600
        # Держим медленный темп до конца прогона (потолок 5с между треками).
        self._pause_sec = min(5.0, max(self._pause_sec * 1.4, 2.0))
        if self._on_wait is not None:
            self._on_wait(text)
