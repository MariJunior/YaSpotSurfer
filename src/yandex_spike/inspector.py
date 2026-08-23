from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from yandex_music import Client, Track

from .yandex import DATA_DIR, TOKEN_FILE_MUSIC, load_token

RAW_DIR = DATA_DIR / "raw"
SNAPSHOT_FILE = DATA_DIR / "library-snapshot.json"
# API принимает пачку track-ids одним POST; дробим, чтобы не упереться в лимит тела.
TRACK_BATCH_SIZE = 100
SAMPLE_PLAYLIST_COUNT = 2
BATCH_PAUSE_SEC = 0.15


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def connect_music_client() -> Client:
    token_data = load_token(TOKEN_FILE_MUSIC)
    if token_data is None or not token_data.get("access_token"):
        raise RuntimeError(
            f"Нет Music token в {TOKEN_FILE_MUSIC}. "
            "Сначала: uv run yandex-spike auth-implicit"
        )

    client = Client(token_data["access_token"])
    client.init()
    return client


def _find_isrc_values(payload: Any, found: list[str] | None = None) -> list[str]:
    """Ищет ключи *isrc* в сыром JSON: в модели Track поля isrc нет."""
    if found is None:
        found = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            if "isrc" in str(key).lower() and value:
                found.append(str(value))
            _find_isrc_values(value, found)
    elif isinstance(payload, list):
        for item in payload:
            _find_isrc_values(item, found)

    return found


def _normalize_track(track: Track) -> dict[str, Any]:
    album = track.albums[0] if track.albums else None
    raw = track.to_dict()
    isrc_values = _find_isrc_values(raw)

    return {
        "source": "yandex",
        "sourceId": str(track.id),
        "title": track.title,
        "version": track.version,
        "durationMs": track.duration_ms,
        "available": track.available,
        "artists": [
            {"id": artist.id, "name": artist.name}
            for artist in (track.artists or [])
        ],
        "album": (
            {
                "id": album.id,
                "title": album.title,
                "year": getattr(album, "year", None),
            }
            if album
            else None
        ),
        "isrc": isrc_values[0] if isrc_values else None,
    }


def _fetch_tracks_batched(client: Client, track_ids: list[str]) -> list[Track]:
    tracks: list[Track] = []
    total = len(track_ids)

    for start in range(0, total, TRACK_BATCH_SIZE):
        chunk = track_ids[start : start + TRACK_BATCH_SIZE]
        tracks.extend(client.tracks(chunk))
        done = min(start + TRACK_BATCH_SIZE, total)
        print(f"   треки {done}/{total}")
        if done < total:
            time.sleep(BATCH_PAUSE_SEC)

    return tracks


def _playlist_header(playlist: Any) -> dict[str, Any]:
    return {
        "uid": playlist.uid,
        "kind": playlist.kind,
        "title": playlist.title,
        "track_count": playlist.track_count,
        "playlist_uuid": getattr(playlist, "playlist_uuid", None),
    }


def fetch_playlist_with_tracks(
    kind: int,
    *,
    client: Client | None = None,
    uid: int | None = None,
    track_limit: int | None = None,
) -> dict[str, Any]:
    """Полные треки одного плейлиста Яндекса. Не выгружает все 51."""
    music_client = client or connect_music_client()
    # Второй аргумент — owner id; без него live тоже работал, но дока marshalx так надёжнее.
    full = (
        music_client.users_playlists(kind, uid)
        if uid is not None
        else music_client.users_playlists(kind)
    )
    if isinstance(full, list):
        full = full[0] if full else None
    if full is None:
        raise RuntimeError(f"Яндекс не вернул плейлист kind={kind}")

    shorts = list(full.tracks or [])
    if track_limit is not None:
        shorts = shorts[:track_limit]
    track_ids = [
        item.track_id for item in shorts if getattr(item, "track_id", None)
    ]
    full_tracks = (
        _fetch_tracks_batched(music_client, track_ids) if track_ids else []
    )

    raw_name = f"playlist-{full.uid}-{full.kind}.json"
    _write_json(
        RAW_DIR / raw_name,
        {
            "playlist": full.to_dict(),
            "tracks": [track.to_dict() for track in full_tracks],
        },
    )
    return {
        **_playlist_header(full),
        "tracks": [_normalize_track(track) for track in full_tracks],
    }


def inspect_library() -> dict[str, Any]:
    print("Подключаюсь к Music API...")
    client = connect_music_client()
    account = client.me.account if client.me and client.me.account else None

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    account_payload = {
        "uid": account.uid if account else None,
        "login": account.login if account else None,
        "display_name": account.display_name if account else None,
    }
    _write_json(RAW_DIR / "account.json", account_payload)

    print("Любимые треки (короткий список)...")
    liked_short = client.users_likes_tracks()
    short_ids = list(liked_short.tracks_ids) if liked_short else []
    _write_json(
        RAW_DIR / "liked-tracks-short.json",
        liked_short.to_dict() if liked_short else {},
    )

    print(f"Полные метаданные лайков: {len(short_ids)}")
    liked_tracks = _fetch_tracks_batched(client, short_ids) if short_ids else []
    liked_raw = [track.to_dict() for track in liked_tracks]
    _write_json(RAW_DIR / "liked-tracks.json", liked_raw)

    print("Плейлисты...")
    playlists = client.users_playlists_list() or []
    _write_json(
        RAW_DIR / "playlists.json",
        [playlist.to_dict() for playlist in playlists],
    )

    # Берём самые маленькие непустые — полный dump большого плейлиста не нужен для A1.
    sample_candidates = [
        playlist
        for playlist in playlists
        if (playlist.track_count or 0) > 0 and playlist.kind is not None
    ]
    sample_candidates.sort(key=lambda playlist: playlist.track_count or 0)
    sample_playlists = sample_candidates[:SAMPLE_PLAYLIST_COUNT]

    sample_normalized: list[dict[str, Any]] = []
    for playlist in sample_playlists:
        print(
            f"Треки плейлиста «{playlist.title}» "
            f"({playlist.track_count})..."
        )
        full = client.users_playlists(playlist.kind)
        if full is None:
            continue

        shorts = full.tracks or []
        track_ids = [item.track_id for item in shorts]
        full_tracks = _fetch_tracks_batched(client, track_ids) if track_ids else []

        raw_name = f"playlist-{playlist.uid}-{playlist.kind}.json"
        _write_json(
            RAW_DIR / raw_name,
            {
                "playlist": full.to_dict(),
                "tracks": [track.to_dict() for track in full_tracks],
            },
        )
        sample_normalized.append(
            {
                **_playlist_header(playlist),
                "tracks": [_normalize_track(track) for track in full_tracks],
            }
        )

    print("Любимые исполнители и альбомы...")
    liked_artists = client.users_likes_artists() or []
    liked_albums = client.users_likes_albums() or []
    _write_json(
        RAW_DIR / "liked-artists.json",
        [item.to_dict() for item in liked_artists],
    )
    _write_json(
        RAW_DIR / "liked-albums.json",
        [item.to_dict() for item in liked_albums],
    )

    normalized_liked = [_normalize_track(track) for track in liked_tracks]
    isrc_present = sum(1 for track in normalized_liked if track["isrc"])
    isrc_keys = _find_isrc_values(liked_raw)

    snapshot = {
        "account": {
            "uid": account_payload["uid"],
            "display_name": account_payload["display_name"],
        },
        "liked_tracks_count": len(normalized_liked),
        "liked_artists_count": len(liked_artists),
        "liked_albums_count": len(liked_albums),
        "playlists_count": len(playlists),
        "playlists": [_playlist_header(playlist) for playlist in playlists],
        "sample_playlists": sample_normalized,
        "liked_tracks": normalized_liked,
        "isrc": {
            "in_track_model": False,
            "values_found_in_liked_raw": len(isrc_keys),
            "liked_tracks_with_isrc": isrc_present,
            "note": (
                "В yandex-music 3.0.0 у Track нет поля isrc. "
                "Счётчик — рекурсивный поиск ключей *isrc* в to_dict()."
            ),
        },
    }
    _write_json(SNAPSHOT_FILE, snapshot)
    return snapshot
