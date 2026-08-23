from __future__ import annotations

from typing import Any

# Префикс, чтобы копии Яндекса не смешались с будущим боевым переносом в боте.
PLAYLIST_SANDBOX_PREFIX = "YaSpotSurfer: "


def sandbox_playlist_name(yandex_title: str) -> str:
    """Имя Spotify-песочницы для одного плейлиста Яндекса."""
    title = (yandex_title or "").strip() or "untitled"
    return f"{PLAYLIST_SANDBOX_PREFIX}{title}"


def select_playlist_headers(
    headers: list[dict[str, Any]],
    *,
    limit: int = 1,
    kind: int | None = None,
) -> list[dict[str, Any]]:
    """Самые маленькие непустые, либо ровно один --kind. Не вся библиотека."""
    if limit < 1:
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
    return nonempty[:limit]


def playlist_migration_entry(
    *,
    yandex_kind: int,
    yandex_title: str,
    spotify_playlist_id: str,
    spotify_playlist_name: str,
    migrate_report: dict[str, Any],
) -> dict[str, Any]:
    """Публичная строка отчёта без write_state."""
    return {
        "yandex_kind": yandex_kind,
        "yandex_title": yandex_title,
        "spotify_playlist_id": spotify_playlist_id,
        "spotify_playlist_name": spotify_playlist_name,
        "track_count": migrate_report.get("track_count"),
        "counts": migrate_report.get("counts") or {},
        "results": migrate_report.get("results") or [],
    }
