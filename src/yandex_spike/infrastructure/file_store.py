from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from yandex_spike.domain.entities import AlbumRef, ArtistRef, Playlist, Track


def tracks_to_jsonable(tracks: list[Track]) -> list[dict]:
    payload: list[dict] = []
    for track in tracks:
        item = asdict(track)
        # raw — провайдерский хвост, в matching и JSON-store не тащим.
        item.pop("raw", None)
        payload.append(item)
    return payload


def track_from_serialized(payload: dict) -> Track:
    artists = tuple(
        ArtistRef(
            name=item.get("name") or "",
            normalized_name=item.get("normalized_name") or "",
            provider_id=item.get("provider_id"),
        )
        for item in (payload.get("artists") or [])
    )
    album_payload = payload.get("album")
    album = None
    if album_payload:
        album = AlbumRef(
            title=album_payload.get("title") or "",
            normalized_title=album_payload.get("normalized_title") or "",
            year=album_payload.get("year"),
            provider_id=album_payload.get("provider_id"),
        )
    provider_ids = tuple(
        (str(pair[0]), str(pair[1]))
        for pair in (payload.get("provider_ids") or [])
        if len(pair) == 2
    )
    return Track(
        id=str(payload.get("id") or ""),
        title=payload.get("title") or "",
        normalized_title=payload.get("normalized_title") or "",
        artists=artists,
        album=album,
        duration_ms=payload.get("duration_ms"),
        version=payload.get("version"),
        version_tags=tuple(payload.get("version_tags") or ()),
        isrc=payload.get("isrc"),
        available=payload.get("available"),
        provider_ids=provider_ids,
        raw=None,
    )


def save_tracks(path: Path, tracks: list[Track]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(tracks_to_jsonable(tracks), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_tracks(path: Path) -> list[Track]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [track_from_serialized(item) for item in payload]


class FileMigrationStore:
    """Локальный JSON-checkpoint. БД появится в боте, не в CLI."""

    def __init__(self, tracks_path: Path) -> None:
        self._tracks_path = tracks_path

    def save_tracks(self, tracks: list[Track]) -> None:
        save_tracks(self._tracks_path, tracks)

    def load_tracks(self) -> list[Track]:
        return load_tracks(self._tracks_path)


def playlist_to_jsonable(playlist: Playlist) -> dict:
    return asdict(playlist)
