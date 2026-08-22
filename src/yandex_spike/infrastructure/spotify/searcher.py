from __future__ import annotations

import time

from yandex_spike.application.search_query import (
    build_fallback_query,
    build_search_query,
)
from yandex_spike.domain.entities import Track
from yandex_spike.infrastructure.spotify.mapper import track_from_spotify_search
from yandex_spike.spotify import _api


class SpotifySearcher:
    """GET /search. Write-методов нет — dry-run не может случайно записать."""

    def __init__(self, access_token: str, *, pause_sec: float = 0.25) -> None:
        self._access_token = access_token
        self._pause_sec = pause_sec

    def search_track(self, track: Track) -> list[Track]:
        primary = self._search(build_search_query(track))
        if primary:
            return primary
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
        )
        if self._pause_sec:
            time.sleep(self._pause_sec)
        if response.status_code != 200:
            excerpt = (response.text or "")[:160]
            raise RuntimeError(
                f"Spotify search HTTP {response.status_code}: {excerpt}"
            )
        items = response.json().get("tracks", {}).get("items") or []
        return [track_from_spotify_search(item) for item in items if item]
