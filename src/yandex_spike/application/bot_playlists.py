""" /playlists: короткие плейлисты Яндекса → «YaSpotSurfer: <имя>» в Spotify. """

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yandex_spike.application.dry_run import run_dry_run
from yandex_spike.application.migrate import write_matched_tracks
from yandex_spike.application.migrate_playlists import (
    merge_playlist_reports,
    playlist_migration_entry,
    sandbox_playlist_name,
    select_playlist_headers,
)
from yandex_spike.application.plan import plan_state_path
from yandex_spike.application.ports import UserAccountStore
from yandex_spike.application.scan import user_library_dir, user_snapshot_path
from yandex_spike.application.spotify_access import (
    SpotifyAccessError,
    resolve_spotify_access,
)
from yandex_spike.infrastructure.spotify.playlists import (
    PlaylistTrackSink,
    SpotifyPlaylistClient,
)
from yandex_spike.infrastructure.spotify.searcher import SpotifySearcher
from yandex_spike.infrastructure.yandex.library import (
    connect_music_client,
    fetch_playlist_with_tracks,
    load_cached_playlist,
)
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot
from yandex_spike.spotify import SpotifyCancelled, SpotifyQuotaExceeded

ProgressFn = Callable[[str], None]
StopFn = Callable[[], bool]

# Репетиция как CLI: один короткий плейлист, не больше 10 треков.
DEFAULT_PLAYLIST_LIMIT = 1
DEFAULT_TRACK_LIMIT = 10


class PlaylistsError(RuntimeError):
    """Понятная ошибка для чата."""


@dataclass(frozen=True)
class PlaylistsResult:
    telegram_id: int
    playlist_count: int
    entries: tuple[dict[str, Any], ...]
    cancelled: bool
    report_path: Path


def playlists_report_path(telegram_id: int, *, root: Path | None = None) -> Path:
    return user_library_dir(telegram_id, root=root) / "migrate-report-playlists.json"


def migrate_playlists_for_user(
    store: UserAccountStore,
    telegram_id: int,
    *,
    data_root: Path | None = None,
    limit: int = DEFAULT_PLAYLIST_LIMIT,
    track_limit: int = DEFAULT_TRACK_LIMIT,
    resume: bool = True,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> PlaylistsResult:
    """Копирует короткие плейлисты. Search только для треков без строки в dry-run-state."""
    snapshot_file = user_snapshot_path(telegram_id, root=data_root)
    if not snapshot_file.exists():
        raise PlaylistsError(
            "Сначала /scan — нужен список плейлистов из Яндекса."
        )

    try:
        snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlaylistsError("Снимок библиотеки повреждён. Запусти /scan.") from exc

    try:
        selected = select_playlist_headers(
            snapshot.get("playlists") or [],
            limit=limit,
            kind=None,
        )
    except (RuntimeError, ValueError) as exc:
        raise PlaylistsError(str(exc)) from exc
    if not selected:
        raise PlaylistsError("В снимке нет непустых плейлистов.")

    yandex_token = store.read_yandex_token(telegram_id)
    if not yandex_token:
        raise PlaylistsError(
            "Сначала подключи Яндекс: /connect_yandex."
        )

    try:
        access_token = resolve_spotify_access(store, telegram_id)
    except SpotifyAccessError as exc:
        raise PlaylistsError(str(exc)) from exc

    lib_dir = user_library_dir(telegram_id, root=data_root)
    raw_dir = lib_dir / "raw"
    dry_path = plan_state_path(telegram_id, root=data_root)
    dry_payload: dict[str, Any] = {"processed": {}}
    if dry_path.exists():
        try:
            dry_payload = json.loads(dry_path.read_text(encoding="utf-8"))
            dry_payload.setdefault("processed", {})
        except (OSError, json.JSONDecodeError):
            dry_payload = {"processed": {}}

    searcher = SpotifySearcher(
        access_token,
        pause_sec=1.25,
        should_stop=should_stop,
    )
    spotify = SpotifyPlaylistClient(access_token)
    yandex_client = None
    entries: list[dict[str, Any]] = []
    cancelled = False

    def _note(text: str) -> None:
        if progress is not None:
            progress(text)

    for header in selected:
        if should_stop is not None and should_stop():
            cancelled = True
            break

        yandex_kind = int(header["kind"])
        title = header.get("title") or ""
        _note(f"📀 Плейлист «{title}» (до {track_limit} треков)…")

        try:
            if yandex_client is None and load_cached_playlist(
                yandex_kind,
                uid=header.get("uid"),
                track_limit=track_limit,
                raw_dir=raw_dir,
            ) is None:
                yandex_client = connect_music_client(
                    yandex_token,
                    progress=progress,
                )
            detail = fetch_playlist_with_tracks(
                yandex_kind,
                client=yandex_client,
                uid=header.get("uid"),
                track_limit=track_limit,
                raw_dir=raw_dir,
                progress=progress,
            )
        except Exception as exc:  # noqa: BLE001
            _note(f"⏭ Пропуск «{title}»: {exc}")
            continue

        tracks = [
            track_from_yandex_snapshot(item) for item in (detail.get("tracks") or [])
        ]
        if not tracks:
            continue

        try:
            dry_report = run_dry_run(
                tracks,
                searcher,
                processed=dict(dry_payload.get("processed") or {}),
                should_stop=should_stop,
            )
        except SpotifyCancelled as exc:
            cancelled = True
            _write_dry(dry_path, dry_payload)
            raise PlaylistsError(
                "Остановлено. Прогресс поиска сохранён — /playlists продолжит."
            ) from exc
        except SpotifyQuotaExceeded as exc:
            _write_dry(dry_path, dry_payload)
            hours = max(1, (exc.retry_after_sec + 3599) // 3600)
            raise PlaylistsError(
                "Квота Spotify на поиск исчерпана (Dev Mode).\n"
                f"Уже сохранённый подбор не потерян. Через ~{hours} ч "
                "снова /playlists или сначала добей /plan."
            ) from exc

        dry_payload["processed"] = dry_report["processed"]
        _write_dry(dry_path, dry_payload)
        if dry_report.get("cancelled"):
            cancelled = True
            break

        match_rows = [dry_report["processed"][track.id] for track in tracks]
        dest_name = sandbox_playlist_name(detail.get("title") or title)

        write_path = lib_dir / f"migrate-state-yandex-pl-{yandex_kind}.json"
        write_state: dict[str, Any] = {}
        migration_id = str(uuid.uuid4())
        if resume and write_path.exists():
            try:
                saved = json.loads(write_path.read_text(encoding="utf-8"))
                write_state = dict(saved.get("write_state") or {})
                migration_id = str(saved.get("migration_id") or migration_id)
            except (OSError, json.JSONDecodeError):
                write_state = {}

        try:
            playlist_id = spotify.find_or_create(dest_name)
        except Exception as exc:  # noqa: BLE001
            raise PlaylistsError(
                f"Не удалось создать плейлист «{dest_name}» в Spotify.\n"
                "Проверь VPN и попробуй /playlists снова."
            ) from exc

        _note(f"💾 Пишу в «{dest_name}»…")
        writer = PlaylistTrackSink(spotify, playlist_id)
        migrate_report = write_matched_tracks(
            match_rows,
            writer,
            write_state=write_state,
            migration_id=migration_id,
            should_stop=should_stop,
        )
        write_path.write_text(
            json.dumps(
                {
                    "migration_id": migrate_report["migration_id"],
                    "yandex_kind": yandex_kind,
                    "spotify_playlist_id": playlist_id,
                    "write_state": migrate_report["write_state"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        entry = playlist_migration_entry(
            yandex_kind=yandex_kind,
            yandex_title=detail.get("title") or title,
            spotify_playlist_id=playlist_id,
            spotify_playlist_name=dest_name,
            migrate_report=migrate_report,
        )
        entries.append(entry)
        if migrate_report.get("cancelled"):
            cancelled = True
            break

    previous = None
    report_path = playlists_report_path(telegram_id, root=data_root)
    if report_path.exists():
        try:
            previous = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None
    merged = merge_playlist_reports(previous, entries)
    merged["cancelled"] = cancelled
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not entries and not cancelled:
        raise PlaylistsError(
            "Не удалось скопировать ни одного плейлиста. "
            "Проверь Яндекс/VPN и /playlists снова."
        )

    return PlaylistsResult(
        telegram_id=telegram_id,
        playlist_count=len(entries),
        entries=tuple(entries),
        cancelled=cancelled,
        report_path=report_path,
    )


def _write_dry(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
