"""Read-адаптер Яндекс Музыки: snapshot библиотеки и треки плейлистов.

Не ходит в domain matching и не пишет в Spotify. HTTP — только read.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from yandex_music import Client, Track

from yandex_spike.infrastructure.yandex.network import call_yandex
from yandex_spike.yandex import DATA_DIR, TOKEN_FILE_MUSIC, load_token

RAW_DIR = DATA_DIR / "raw"
SNAPSHOT_FILE = DATA_DIR / "library-snapshot.json"
TRACK_BATCH_SIZE = 100
SAMPLE_PLAYLIST_COUNT = 2
BATCH_PAUSE_SEC = 0.15
# yandex-music DefaultTimeout = 5с; через VPN TLS handshake часто не успевает.
YANDEX_TIMEOUT_SEC = 20


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def connect_music_client() -> Client:
    """Official-like Music token + init(). Свой OAuth app (403) сюда не класть."""
    token_data = load_token(TOKEN_FILE_MUSIC)
    if token_data is None or not token_data.get("access_token"):
        raise RuntimeError(
            f"Нет Music token в {TOKEN_FILE_MUSIC}. "
            "Сначала: uv run yandex-spike auth-implicit"
        )

    client = Client(token_data["access_token"])
    client.request.set_timeout(YANDEX_TIMEOUT_SEC)
    call_yandex("account/status", client.init)
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
    """Плоский JSON для mapper → domain.Track. ISRC в модели Track нет."""
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


def _normalize_track_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Как `_normalize_track`, но из `Track.to_dict()` / TrackShort в raw-кэше.

    TrackShort кладёт полную модель во вложенный ключ ``track``.
    """
    if "title" not in raw and isinstance(raw.get("track"), dict):
        raw = raw["track"]
    albums = raw.get("albums") or []
    album = albums[0] if albums else None
    artists = raw.get("artists") or []
    isrc_values = _find_isrc_values(raw)
    track_id = raw.get("id")
    if track_id is None:
        track_id = raw.get("track_id") or raw.get("sourceId")
    return {
        "source": "yandex",
        "sourceId": str(track_id or ""),
        "title": raw.get("title"),
        "version": raw.get("version"),
        "durationMs": raw.get("duration_ms") if "duration_ms" in raw else raw.get("durationMs"),
        "available": raw.get("available"),
        "artists": [
            {"id": artist.get("id"), "name": artist.get("name")}
            for artist in artists
            if isinstance(artist, dict)
        ],
        "album": (
            {
                "id": album.get("id"),
                "title": album.get("title"),
                "year": album.get("year"),
            }
            if isinstance(album, dict)
            else None
        ),
        "isrc": isrc_values[0] if isrc_values else None,
    }


def _playlist_raw_path(kind: int, uid: int | None) -> Path | None:
    if uid is not None:
        path = RAW_DIR / f"playlist-{uid}-{kind}.json"
        if path.exists():
            return path
    matches = list(RAW_DIR.glob(f"playlist-*-{kind}.json"))
    if not matches:
        return None
    matches.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0]


def load_cached_playlist(
    kind: int,
    *,
    uid: int | None = None,
    track_limit: int | None = None,
) -> dict[str, Any] | None:
    """Уже скачанный raw — без нового запроса к Яндексу (VPN его часто роняет)."""
    path = _playlist_raw_path(kind, uid)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_tracks = payload.get("tracks") or []
    if not raw_tracks:
        return None
    if track_limit is not None:
        raw_tracks = raw_tracks[:track_limit]
    playlist = payload.get("playlist") or {}
    return {
        "uid": playlist.get("uid") if playlist.get("uid") is not None else uid,
        "kind": playlist.get("kind") if playlist.get("kind") is not None else kind,
        "title": playlist.get("title"),
        "track_count": playlist.get("track_count"),
        "playlist_uuid": playlist.get("playlist_uuid"),
        "tracks": [_normalize_track_dict(item) for item in raw_tracks],
        "from_cache": True,
    }


def _fetch_tracks_batched(client: Client, track_ids: list[str]) -> list[Track]:
    """POST /tracks пачками: одно тело на много id, чтобы не упереться в лимит."""
    tracks: list[Track] = []
    total = len(track_ids)

    for start in range(0, total, TRACK_BATCH_SIZE):
        chunk = track_ids[start : start + TRACK_BATCH_SIZE]
        tracks.extend(call_yandex("tracks", client.tracks, chunk))
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
    """Один плейлист с полными треками. Не выгружает все 51.

    ``users_playlists(kind, uid)`` — uid владельца по доке marshalx; без него
    live тоже работал, но с uid стабильнее.
    """
    cached = load_cached_playlist(kind, uid=uid, track_limit=track_limit)
    if cached:
        print(f"   кэш {RAW_DIR.name}/playlist-*-{kind}.json, Яндекс не зовём")
        return cached

    music_client = client or connect_music_client()
    if uid is not None:
        full = call_yandex(
            f"playlist kind={kind}",
            music_client.users_playlists,
            kind,
            uid,
        )
    else:
        full = call_yandex(
            f"playlist kind={kind}",
            music_client.users_playlists,
            kind,
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
    """Полный snapshot лайков + заголовки всех плейлистов.

    Полные треки — только у двух самых коротких непустых плейлистов:
    большой dump не нужен для matching CLI, его добирает
    ``fetch_playlist_with_tracks``.
    """
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
