from __future__ import annotations

import time

from yandex_spike.spotify import _api

SANDBOX_PLAYLIST_NAME = "YaSpotSurfer sandbox"


class SpotifyPlaylistClient:
    """Плейлист-песочница: find-or-create + add items. Не трогает Liked Songs."""

    def __init__(self, access_token: str, *, pause_sec: float = 0.2) -> None:
        self._access_token = access_token
        self._pause_sec = pause_sec

    def find_or_create(self, name: str) -> str:
        existing = self._find_id_by_name(name)
        if existing:
            return existing
        response = _api(
            "POST",
            "/me/playlists",
            self._access_token,
            json_body={
                "name": name,
                "public": False,
                "description": "YaSpotSurfer rehearsal playlist. Safe to delete.",
            },
        )
        if self._pause_sec:
            time.sleep(self._pause_sec)
        if response.status_code not in (200, 201):
            excerpt = (response.text or "")[:160]
            if response.status_code == 403:
                raise RuntimeError(
                    "Spotify не дал создать плейлист (часто: страна/VPN, "
                    "«unavailable in this country»). Создай в приложении Spotify "
                    f"приватный плейлист «{name}» и повтори migrate — найдём по имени. "
                    "Или: --playlist-id <id из URL open.spotify.com/playlist/…>. "
                    f"HTTP 403: {excerpt}"
                )
            raise RuntimeError(
                f"Spotify create playlist HTTP {response.status_code}: {excerpt}"
            )
        return response.json()["id"]

    def item_uris(self, playlist_id: str) -> set[str]:
        uris: set[str] = set()
        offset = 0
        page_size = 10
        while True:
            response = _api(
                "GET",
                f"/playlists/{playlist_id}/items",
                self._access_token,
                params={"limit": page_size, "offset": offset},
            )
            if self._pause_sec:
                time.sleep(self._pause_sec)
            if response.status_code != 200:
                excerpt = (response.text or "")[:160]
                raise RuntimeError(
                    f"Spotify playlist items HTTP {response.status_code}: {excerpt}"
                )
            items = response.json().get("items") or []
            for item in items:
                track = item.get("track") or {}
                uri = track.get("uri")
                if uri:
                    uris.add(uri)
            offset += len(items)
            if not items or offset > 2000:
                break
        return uris

    def add_item(self, playlist_id: str, uri: str) -> None:
        response = _api(
            "POST",
            f"/playlists/{playlist_id}/items",
            self._access_token,
            json_body={"uris": [uri]},
        )
        if self._pause_sec:
            time.sleep(self._pause_sec)
        if response.status_code not in (200, 201):
            excerpt = (response.text or "")[:160]
            raise RuntimeError(
                f"Spotify add item HTTP {response.status_code}: {excerpt}"
            )

    def _find_id_by_name(self, name: str) -> str | None:
        offset = 0
        page_size = 10
        while offset <= 200:
            response = _api(
                "GET",
                "/me/playlists",
                self._access_token,
                params={"limit": page_size, "offset": offset},
            )
            if self._pause_sec:
                time.sleep(self._pause_sec)
            if response.status_code != 200:
                break
            payload = response.json()
            items = payload.get("items") or []
            for item in items:
                if item.get("name") == name:
                    return item.get("id")
            offset += len(items)
            total = payload.get("total")
            if not items or (total is not None and offset >= total):
                break
        return None


class PlaylistTrackSink:
    """Тот же контракт, что Liked Songs writer, но пишет в один плейлист."""

    def __init__(self, client: SpotifyPlaylistClient, playlist_id: str) -> None:
        self._client = client
        self._playlist_id = playlist_id
        self._uris: set[str] | None = None

    def contains(self, uri: str) -> bool:
        if self._uris is None:
            self._uris = self._client.item_uris(self._playlist_id)
        return uri in self._uris

    def save(self, uri: str) -> None:
        self._client.add_item(self._playlist_id, uri)
        if self._uris is None:
            self._uris = set()
        self._uris.add(uri)
