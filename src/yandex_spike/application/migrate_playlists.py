"""Песочница плейлистов Яндекса: имя Spotify и выбор коротких kind."""

from __future__ import annotations

from typing import Any

PLAYLIST_SANDBOX_PREFIX = "YaSpotSurfer: "


def sandbox_playlist_name(yandex_title: str) -> str:
    """``YaSpotSurfer: <имя>``, чтобы не смешать с будущим боевым плейлистом в боте."""
    title = (yandex_title or "").strip() or "untitled"
    return f"{PLAYLIST_SANDBOX_PREFIX}{title}"


def select_playlist_headers(
    headers: list[dict[str, Any]],
    *,
    limit: int | None = 1,
    kind: int | None = None,
) -> list[dict[str, Any]]:
    """Самые маленькие непустые, либо ровно один --kind.

    ``limit=None`` — все непустые (боевой перенос). Иначе — первые N по размеру.
    """
    if limit is not None and limit < 1:
        raise ValueError("limit должен быть >= 1")

    nonempty = [
        header
        for header in headers
        if (header.get("track_count") or 0) > 0 and header.get("kind") is not None
    ]

    if kind is not None:
        matched = [header for header in nonempty if header.get("kind") == kind]
        if not matched:
            known = ", ".join(
                f"{header.get('kind')}:{header.get('title')}"
                for header in headers[:12]
            )
            raise RuntimeError(
                f"В snapshot нет непустого плейлиста kind={kind}. "
                f"Примеры: {known}"
            )
        return matched[:1]

    nonempty.sort(
        key=lambda header: (
            int(header.get("track_count") or 0),
            int(header.get("kind") or 0),
        )
    )
    if limit is None:
        return nonempty
    return nonempty[:limit]


def playlist_migration_entry(
    *,
    yandex_kind: int,
    yandex_title: str,
    spotify_playlist_id: str | None,
    spotify_playlist_name: str,
    migrate_report: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Публичная строка отчёта без write_state."""
    return {
        "yandex_kind": yandex_kind,
        "yandex_title": yandex_title,
        "spotify_playlist_id": spotify_playlist_id,
        "spotify_playlist_name": spotify_playlist_name,
        "dry_run": dry_run,
        "track_count": migrate_report.get("track_count"),
        "counts": migrate_report.get("counts") or {},
        "results": migrate_report.get("results") or [],
    }


def merge_playlist_reports(
    previous: dict[str, Any] | None,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Не затирает прошлые kind: 105 и 1063 живут в одном файле."""
    by_kind: dict[int, dict[str, Any]] = {}
    for item in (previous or {}).get("playlists") or []:
        kind = item.get("yandex_kind")
        if kind is not None:
            by_kind[int(kind)] = item
    for entry in entries:
        by_kind[int(entry["yandex_kind"])] = entry
    playlists = list(by_kind.values())
    return {
        "wrote_to_spotify": any(not item.get("dry_run") for item in playlists),
        "dest": "yandex-playlists",
        "playlist_count": len(playlists),
        "playlists": playlists,
    }
