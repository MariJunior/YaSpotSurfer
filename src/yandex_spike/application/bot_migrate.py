""" /migrate: запись лайков из dry-run-state пользователя (без нового search). """

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from yandex_spike.application.migrate import write_matched_tracks
from yandex_spike.application.plan import plan_state_path
from yandex_spike.application.ports import UserAccountStore
from yandex_spike.application.scan import user_library_dir
from yandex_spike.application.spotify_access import (
    SpotifyAccessError,
    resolve_spotify_access,
)
from yandex_spike.infrastructure.spotify.library import SpotifyLibraryWriter
from yandex_spike.infrastructure.spotify.playlists import (
    SANDBOX_PLAYLIST_NAME,
    PlaylistTrackSink,
    SpotifyPlaylistClient,
)

Dest = Literal["playlist", "library"]
ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]


class MigrateError(RuntimeError):
    """Понятная ошибка для чата."""


@dataclass(frozen=True)
class MigrateResult:
    telegram_id: int
    dest: Dest
    track_count: int
    saved: int
    already: int
    skipped: int
    cancelled: bool
    playlist_name: str | None
    state_path: Path
    report_path: Path


def migrate_state_path(
    telegram_id: int,
    dest: Dest,
    *,
    root: Path | None = None,
) -> Path:
    return user_library_dir(telegram_id, root=root) / f"migrate-state-{dest}.json"


def migrate_report_path(
    telegram_id: int,
    dest: Dest,
    *,
    root: Path | None = None,
) -> Path:
    return user_library_dir(telegram_id, root=root) / f"migrate-report-{dest}.json"


def _load_processed(telegram_id: int, *, root: Path | None) -> dict[str, Any]:
    path = plan_state_path(telegram_id, root=root)
    if not path.exists():
        raise MigrateError(
            "Сначала /plan — нужен подбор треков в Spotify.\n"
            "Без него записывать нечего."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrateError(
            "Файл подбора повреждён. Запусти /plan ещё раз."
        ) from exc
    processed = dict(payload.get("processed") or {})
    if not processed:
        raise MigrateError("Подбор пустой. Сначала /plan.")
    return processed


def _match_rows(processed: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(processed.values())
    rows.sort(key=lambda row: str(row.get("source_id") or ""))
    return rows


def migrate_liked_from_plan(
    store: UserAccountStore,
    telegram_id: int,
    *,
    dest: Dest,
    data_root: Path | None = None,
    resume: bool = True,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> MigrateResult:
    """Пишет из checkpoint /plan. Новых Spotify search не делает (квота Dev Mode)."""
    processed = _load_processed(telegram_id, root=data_root)
    match_rows = _match_rows(processed)

    try:
        access_token = resolve_spotify_access(store, telegram_id)
    except SpotifyAccessError as exc:
        raise MigrateError(str(exc)) from exc

    state_file = migrate_state_path(telegram_id, dest, root=data_root)
    report_file = migrate_report_path(telegram_id, dest, root=data_root)
    write_state: dict[str, Any] = {}
    migration_id = str(uuid.uuid4())
    if resume and state_file.exists():
        try:
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            write_state = dict(saved.get("write_state") or {})
            migration_id = str(saved.get("migration_id") or migration_id)
        except (OSError, json.JSONDecodeError):
            write_state = {}

    playlist_name: str | None = None
    if dest == "library":
        writer: SpotifyLibraryWriter | PlaylistTrackSink = SpotifyLibraryWriter(
            access_token
        )
    else:
        playlist_name = SANDBOX_PLAYLIST_NAME
        client = SpotifyPlaylistClient(access_token)
        try:
            playlist_id = client.find_or_create(playlist_name)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "403" in message or "unavailable" in message.lower():
                raise MigrateError(
                    "Spotify не дал создать проверочный плейлист "
                    "(часто VPN/страна).\n"
                    f"Создай вручную приватный «{SANDBOX_PLAYLIST_NAME}» "
                    "и нажми /migrate снова."
                ) from exc
            raise MigrateError(
                "Не удалось подготовить проверочный плейлист. Попробуй /migrate ещё раз."
            ) from exc
        writer = PlaylistTrackSink(client, playlist_id)

    # Checkpoint каждые 25 строк — resume после /cancel или обрыва.
    ticks = {"n": 0}

    def wrapped_progress(done: int, total: int) -> None:
        ticks["n"] += 1
        if ticks["n"] % 25 == 0:
            _write_state(state_file, migration_id, write_state)
        if progress is not None:
            progress(done, total)

    try:
        report = write_matched_tracks(
            match_rows,
            writer,
            write_state=write_state,
            migration_id=migration_id,
            on_progress=wrapped_progress,
            should_stop=should_stop,
        )
    except Exception as exc:  # noqa: BLE001
        _write_state(state_file, migration_id, write_state)
        message = str(exc)
        if "HTTP 401" in message or "HTTP 403" in message:
            raise MigrateError(
                "Spotify не принял запись (сеть, VPN или сессия).\n"
                "Проверь VPN и при необходимости /connect_spotify, потом /migrate."
            ) from exc
        raise MigrateError(
            "Не удалось записать треки в Spotify. Попробуй /migrate ещё раз."
        ) from exc

    _write_state(state_file, report["migration_id"], report["write_state"])

    public = {key: value for key, value in report.items() if key != "write_state"}
    public["dest"] = dest
    if playlist_name:
        public["playlist_name"] = playlist_name
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(public, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = report["counts"]
    return MigrateResult(
        telegram_id=telegram_id,
        dest=dest,
        track_count=int(report["track_count"]),
        saved=int(counts.get("saved", 0)),
        already=int(counts.get("already", 0)),
        skipped=int(counts.get("skipped", 0)),
        cancelled=bool(report.get("cancelled")),
        playlist_name=playlist_name,
        state_path=state_file,
        report_path=report_file,
    )


def _write_state(path: Path, migration_id: str, write_state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"migration_id": migration_id, "write_state": write_state},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
