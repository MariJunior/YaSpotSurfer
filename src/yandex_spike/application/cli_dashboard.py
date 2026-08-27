"""Снимок статуса CLI для TUI/меню: auth, snapshot, dry-run, migrate.

Читает только локальные файлы в ``.data`` — без сетевых запросов.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yandex_spike.application.review import list_open_reviews
from yandex_spike.infrastructure.yandex.library import SNAPSHOT_FILE
from yandex_spike.spotify import TOKEN_FILE as SPOTIFY_TOKEN_FILE
from yandex_spike.yandex import TOKEN_FILE_MUSIC

# Эмпирика Dev Mode (см. docs/dry-run.md / telegram copy).
SPOTIFY_DAILY_SEARCH_SOFT_CAP = 650

DATA_DIR = Path(".data")
DRY_RUN_STATE = DATA_DIR / "dry-run-state.json"
MIGRATE_STATE_PLAYLIST = DATA_DIR / "migrate-state-playlist.json"
MIGRATE_STATE_LIBRARY = DATA_DIR / "migrate-state-library.json"


@dataclass(frozen=True)
class ProgressBarSpec:
    """Один прогресс-бар на дашборде."""

    key: str
    label: str
    done: int
    total: int | None  # None → indeterminate / неизвестно


@dataclass(frozen=True)
class CommandItem:
    """Пункт левого бара."""

    command: str
    title: str
    enabled: bool
    reason: str = ""


@dataclass
class CliDashboard:
    """Всё, что нужно TUI для отрисовки статусов и меню."""

    yandex_token: bool
    spotify_token: bool
    snapshot_exists: bool
    likes_total: int
    playlists_total: int
    dry_done: int
    dry_by_status: dict[str, int] = field(default_factory=dict)
    review_open: int = 0
    migrate_playlist_done: int = 0
    migrate_library_done: int = 0
    stage_hint: str = ""
    commands: tuple[CommandItem, ...] = ()
    bars: tuple[ProgressBarSpec, ...] = ()


def _token_present(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("access_token"))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _count_statuses(processed: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in processed.values():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _processed_len(path: Path) -> int:
    payload = _load_json(path)
    processed = payload.get("processed")
    return len(processed) if isinstance(processed, dict) else 0


def _stage_hint(
    *,
    yandex: bool,
    spotify: bool,
    snapshot: bool,
    likes: int,
    dry_done: int,
    review_open: int,
    migrate_pl: int,
) -> str:
    if not yandex:
        return "Этап: войти в Яндекс (auth-implicit)"
    if not spotify:
        return "Этап: войти в Spotify (spotify-spike)"
    if not snapshot:
        return "Этап: снять библиотеку (scan)"
    if dry_done < likes:
        return "Этап: подбор в Spotify (migrate-dry-run --resume)"
    if review_open > 0:
        return f"Этап: разобрать review ({review_open} открытых)"
    if migrate_pl <= 0:
        return "Этап: запись в песочницу (migrate), затем Любимое / плейлисты"
    return "Этап: добить плейлисты или --dest library после проверки"


def _commands_for(
    *,
    yandex: bool,
    spotify: bool,
    snapshot: bool,
    dry_done: int,
) -> tuple[CommandItem, ...]:
    """Команды левого бара: основные шаги + always-on help/refresh."""

    def item(
        command: str,
        title: str,
        enabled: bool,
        reason: str = "",
    ) -> CommandItem:
        return CommandItem(command, title, enabled, reason)

    return (
        item("help", "Справка", True),
        item(
            "auth-implicit",
            "Яндекс: войти",
            True,
            "" if not yandex else "токен уже есть — можно перелогиниться",
        ),
        item(
            "probe",
            "Яндекс: проверка",
            yandex,
            "" if yandex else "нужен auth-implicit",
        ),
        item(
            "spotify-spike",
            "Spotify: войти",
            True,
            "" if not spotify else "токен уже есть",
        ),
        item(
            "scan",
            "Снимок библиотеки",
            yandex,
            "" if yandex else "нужен Яндекс",
        ),
        item(
            "migrate-dry-run",
            "Подбор (dry-run)",
            yandex and spotify and snapshot,
            ""
            if yandex and spotify and snapshot
            else "нужны Яндекс + Spotify + scan",
        ),
        item(
            "review",
            "Спорные (review)",
            dry_done > 0,
            "" if dry_done > 0 else "сначала dry-run",
        ),
        item(
            "migrate",
            "Запись лайков → песочница",
            dry_done > 0 and spotify,
            "" if dry_done > 0 else "сначала dry-run",
        ),
        item(
            "migrate-playlists",
            "Копия плейлистов",
            yandex and spotify and snapshot,
            ""
            if yandex and spotify and snapshot
            else "нужны Яндекс + Spotify + scan",
        ),
        item("refresh", "Обновить статусы", True),
        item("quit", "Выход", True),
    )


def load_cli_dashboard(
    *,
    data_dir: Path | None = None,
    yandex_token_path: Path | None = None,
    spotify_token_path: Path | None = None,
    snapshot_path: Path | None = None,
) -> CliDashboard:
    """Собрать дашборд из файлов (по умолчанию — ``.data`` проекта)."""
    root = data_dir or DATA_DIR
    yandex_path = yandex_token_path or TOKEN_FILE_MUSIC
    spotify_path = spotify_token_path or SPOTIFY_TOKEN_FILE
    snap_path = snapshot_path or SNAPSHOT_FILE

    yandex_ok = _token_present(yandex_path)
    spotify_ok = _token_present(spotify_path)

    snapshot = _load_json(snap_path)
    snapshot_exists = snap_path.exists() and bool(snapshot)
    likes = int(snapshot.get("liked_tracks_count") or 0)
    if likes <= 0 and isinstance(snapshot.get("liked_tracks"), list):
        likes = len(snapshot["liked_tracks"])
    playlists = int(snapshot.get("playlists_count") or 0)
    if playlists <= 0 and isinstance(snapshot.get("playlists"), list):
        playlists = len(snapshot["playlists"])

    dry_path = root / "dry-run-state.json"
    dry_payload = _load_json(dry_path)
    processed = dry_payload.get("processed") or {}
    if not isinstance(processed, dict):
        processed = {}
    dry_done = len(processed)
    by_status = _count_statuses(processed)
    review_open = len(list_open_reviews(processed))

    migrate_pl = _processed_len(root / "migrate-state-playlist.json")
    migrate_lib = _processed_len(root / "migrate-state-library.json")

    hint = _stage_hint(
        yandex=yandex_ok,
        spotify=spotify_ok,
        snapshot=snapshot_exists,
        likes=likes,
        dry_done=dry_done,
        review_open=review_open,
        migrate_pl=migrate_pl,
    )
    commands = _commands_for(
        yandex=yandex_ok,
        spotify=spotify_ok,
        snapshot=snapshot_exists,
        dry_done=dry_done,
    )

    # Прогресс dry-run относительно всей коллекции лайков.
    dry_total = likes if likes > 0 else None
    # Soft-cap — ориентир «сколько search ещё влезает сегодня», не жёсткий лимит API.
    remaining_cap = max(0, SPOTIFY_DAILY_SEARCH_SOFT_CAP - dry_done)

    # Review: «закрыто / всего когда-либо в review» (open + уже с decision).
    review_decided = sum(
        1
        for row in processed.values()
        if isinstance(row, dict) and row.get("decision")
    )
    review_total = review_open + review_decided

    bars = (
        ProgressBarSpec(
            "dry",
            f"Dry-run / лайки ({dry_done}/{likes or '?'})",
            dry_done,
            dry_total,
        ),
        ProgressBarSpec(
            "quota",
            f"Ориентир квоты search (~{SPOTIFY_DAILY_SEARCH_SOFT_CAP}/сутки)",
            min(dry_done, SPOTIFY_DAILY_SEARCH_SOFT_CAP),
            SPOTIFY_DAILY_SEARCH_SOFT_CAP,
        ),
        ProgressBarSpec(
            "review",
            f"Review решено {review_decided}/{review_total or 0} (открыто {review_open})",
            review_decided,
            review_total if review_total > 0 else None,
        ),
        ProgressBarSpec(
            "migrate_pl",
            f"Запись в песочницу ({migrate_pl})",
            migrate_pl,
            dry_done if dry_done > 0 else None,
        ),
        ProgressBarSpec(
            "migrate_lib",
            f"Запись в Любимое ({migrate_lib})",
            migrate_lib,
            dry_done if dry_done > 0 else None,
        ),
    )

    # remaining_cap оставляем в stage hint при приближении к капу.
    if dry_done > 0 and remaining_cap < 50 and dry_done < likes:
        hint = f"{hint} · квота search почти на исходе (~{remaining_cap} осталось)"

    return CliDashboard(
        yandex_token=yandex_ok,
        spotify_token=spotify_ok,
        snapshot_exists=snapshot_exists,
        likes_total=likes,
        playlists_total=playlists,
        dry_done=dry_done,
        dry_by_status=by_status,
        review_open=review_open,
        migrate_playlist_done=migrate_pl,
        migrate_library_done=migrate_lib,
        stage_hint=hint,
        commands=commands,
        bars=bars,
    )
