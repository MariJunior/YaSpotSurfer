from __future__ import annotations

import time

from yandex_spike.spotify import _api


class SpotifyLibraryWriter:
    """PUT/GET /me/library. uris — query, по одному: запятая в requests ломается."""

    def __init__(self, access_token: str, *, pause_sec: float = 0.2) -> None:
        self._access_token = access_token
        self._pause_sec = pause_sec

    def contains(self, uri: str) -> bool:
        response = _api(
            "GET",
            "/me/library/contains",
            self._access_token,
            params={"uris": uri},
        )
        if self._pause_sec:
            time.sleep(self._pause_sec)
        if response.status_code != 200:
            excerpt = (response.text or "")[:160]
            raise RuntimeError(
                f"Spotify contains HTTP {response.status_code}: {excerpt}"
            )
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise RuntimeError("Spotify contains: ожидался массив bool")
        return bool(payload[0])

    def save(self, uri: str) -> None:
        response = _api(
            "PUT",
            "/me/library",
            self._access_token,
            params={"uris": uri},
        )
        if self._pause_sec:
            time.sleep(self._pause_sec)
        if response.status_code not in (200, 201):
            excerpt = (response.text or "")[:160]
            raise RuntimeError(
                f"Spotify save HTTP {response.status_code}: {excerpt}"
            )
