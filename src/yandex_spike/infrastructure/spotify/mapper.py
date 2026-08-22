from __future__ import annotations

from typing import Any

from yandex_spike.domain.entities import AlbumRef, ArtistRef, Track
from yandex_spike.domain.normalization import normalize_artist, normalize_title


def track_from_spotify_search(payload: dict[str, Any]) -> Track:
    """Маппинг объекта search/track Spotify Web API → domain.Track."""
    title = payload.get("name") or ""
    normalized = normalize_title(title)
    artists = tuple(
        ArtistRef(
            name=artist.get("name") or "",
            normalized_name=normalize_artist(artist.get("name")),
            provider_id=artist.get("id"),
        )
        for artist in (payload.get("artists") or [])
    )
    album_payload = payload.get("album") or {}
    album_title = album_payload.get("name") or ""
    # release_date бывает YYYY, YYYY-MM, YYYY-MM-DD — год всегда в префиксе.
    year = None
    release = album_payload.get("release_date") or ""
    if len(release) >= 4 and release[:4].isdigit():
        year = int(release[:4])

    album = None
    if album_title or album_payload.get("id"):
        album = AlbumRef(
            title=album_title,
            normalized_title=normalize_title(album_title).text,
            year=year,
            provider_id=album_payload.get("id"),
        )

    source_id = payload.get("id") or ""
    # У Spotify ISRC есть; у Яндекса в A1 его не было. Matching начнёт не с ISRC.
    isrc = (payload.get("external_ids") or {}).get("isrc")
    return Track(
        id=f"spotify:{source_id}",
        title=title,
        normalized_title=normalized.text,
        artists=artists,
        album=album,
        duration_ms=payload.get("duration_ms"),
        version=None,
        version_tags=normalized.version_tags,
        isrc=isrc,
        available=payload.get("is_playable"),
        provider_ids=(("spotify", source_id),),
        raw=payload,
    )
