from __future__ import annotations

from typing import Any

from yandex_spike.domain.entities import AlbumRef, ArtistRef, Playlist, Track
from yandex_spike.domain.normalization import normalize_artist, normalize_title


def track_from_yandex_snapshot(payload: dict[str, Any]) -> Track:
    """Маппинг нормализованной записи inspect → domain.Track."""
    title = payload.get("title") or ""
    normalized = normalize_title(title)
    artists = tuple(
        ArtistRef(
            name=artist.get("name") or "",
            normalized_name=normalize_artist(artist.get("name")),
            provider_id=str(artist["id"]) if artist.get("id") is not None else None,
        )
        for artist in (payload.get("artists") or [])
    )
    album_payload = payload.get("album")
    album = None
    if album_payload:
        album_title = album_payload.get("title") or ""
        album = AlbumRef(
            title=album_title,
            normalized_title=normalize_title(album_title).text,
            year=album_payload.get("year"),
            provider_id=(
                str(album_payload["id"])
                if album_payload.get("id") is not None
                else None
            ),
        )

    # Live inspect: ISRC в модели Track нет, поле почти всегда None.
    source_id = str(payload.get("sourceId") or payload.get("id") or "")
    return Track(
        id=f"yandex:{source_id}",
        title=title,
        normalized_title=normalized.text,
        artists=artists,
        album=album,
        duration_ms=payload.get("durationMs"),
        version=payload.get("version"),
        version_tags=normalized.version_tags,
        isrc=payload.get("isrc"),
        available=payload.get("available"),
        provider_ids=(("yandex", source_id),),
        raw=payload,
    )


def playlist_from_yandex_snapshot(payload: dict[str, Any]) -> Playlist:
    """Заголовок плейлиста из inspect. Треки подтянет A4/A5, не A3."""
    kind = payload.get("kind")
    source_id = str(kind if kind is not None else payload.get("playlist_uuid") or "")
    return Playlist(
        id=f"yandex:{source_id}",
        title=payload.get("title") or "",
        track_ids=(),
        provider_ids=(("yandex", source_id),),
    )
