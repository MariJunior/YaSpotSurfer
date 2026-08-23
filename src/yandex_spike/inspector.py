"""Совместимый импорт: логика в ``infrastructure.yandex.library``."""

from yandex_spike.infrastructure.yandex.library import (
    RAW_DIR,
    SNAPSHOT_FILE,
    connect_music_client,
    fetch_playlist_with_tracks,
    inspect_library,
    load_cached_playlist,
)
from yandex_spike.infrastructure.yandex.library import (
    _normalize_track_dict,
)

__all__ = [
    "RAW_DIR",
    "SNAPSHOT_FILE",
    "connect_music_client",
    "fetch_playlist_with_tracks",
    "inspect_library",
    "load_cached_playlist",
    "_normalize_track_dict",
]
