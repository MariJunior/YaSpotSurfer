""" /plan: dry-run matching лайков по per-user snapshot. """

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yandex_spike.application.dry_run import run_dry_run
from yandex_spike.application.ports import UserAccountStore
from yandex_spike.application.scan import user_library_dir, user_snapshot_path
from yandex_spike.application.spotify_access import (
    SpotifyAccessError,
    resolve_spotify_access,
)
from yandex_spike.infrastructure.spotify.searcher import SpotifySearcher
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot
from yandex_spike.spotify import SpotifyCancelled, SpotifyQuotaExceeded

ProgressFn = Callable[[int, int], None]
WaitFn = Callable[[str], None]
StopFn = Callable[[], bool]


class PlanError(RuntimeError):
    """Понятная ошибка для чата (текст оформляет presentation-слой)."""


class PlanQuotaExceededError(PlanError):
    """Дневная квота Spotify Dev Mode — прогресс уже сохранён."""

    def __init__(self, *, done: int, retry_after_sec: int) -> None:
        self.done = done
        self.retry_after_sec = retry_after_sec
        hours = max(1, (retry_after_sec + 3599) // 3600)
        # Короткий fallback, если caller не распознал тип.
        super().__init__(
            f"Квота Spotify исчерпана (~{hours} ч). Уже сохранено: {done}. Потом /plan."
        )


@dataclass(frozen=True)
class PlanResult:
    telegram_id: int
    track_count: int
    auto_count: int
    review_count: int
    not_found_count: int
    cancelled: bool
    resumed: bool
    state_path: Path
    report_path: Path


def plan_state_path(telegram_id: int, *, root: Path | None = None) -> Path:
    return user_library_dir(telegram_id, root=root) / "dry-run-state.json"


def plan_report_path(telegram_id: int, *, root: Path | None = None) -> Path:
    return user_library_dir(telegram_id, root=root) / "dry-run-report.json"


def load_plan_summary(telegram_id: int, *, root: Path | None = None) -> dict[str, Any] | None:
    path = plan_report_path(telegram_id, root=root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def checkpoint_track_count(telegram_id: int, *, root: Path | None = None) -> int:
    """Сколько треков уже в dry-run-state — для /status, если UI не обновлялся."""
    path = plan_state_path(telegram_id, root=root)
    if not path.exists():
        return 0
    try:
        processed = json.loads(path.read_text(encoding="utf-8")).get("processed") or {}
        return len(processed)
    except (OSError, json.JSONDecodeError):
        return 0


def plan_liked_tracks(
    store: UserAccountStore,
    telegram_id: int,
    *,
    data_root: Path | None = None,
    limit: int | None = None,
    resume: bool = True,
    progress: ProgressFn | None = None,
    on_wait: WaitFn | None = None,
    should_stop: StopFn | None = None,
) -> PlanResult:
    """Search+match лайков из snapshot. Write в Spotify нет."""
    snapshot_file = user_snapshot_path(telegram_id, root=data_root)
    if not snapshot_file.exists():
        raise PlanError(
            "Сначала собери список треков из Яндекса: /scan "
            "или кнопка «Собрать список треков»."
        )

    try:
        snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(
            "Снимок библиотеки повреждён. Запусти /scan ещё раз."
        ) from exc

    items = list(snapshot.get("liked_tracks") or [])
    if limit is not None:
        items = items[:limit]
    if not items:
        raise PlanError("В снимке нет лайков. После /scan здесь должны появиться треки.")

    tracks = [track_from_yandex_snapshot(item) for item in items]

    try:
        access_token = resolve_spotify_access(store, telegram_id)
    except SpotifyAccessError as exc:
        raise PlanError(str(exc)) from exc

    state_file = plan_state_path(telegram_id, root=data_root)
    report_file = plan_report_path(telegram_id, root=data_root)
    processed: dict[str, Any] = {}
    if resume and state_file.exists():
        try:
            processed = json.loads(state_file.read_text(encoding="utf-8")).get(
                "processed"
            ) or {}
        except (OSError, json.JSONDecodeError):
            processed = {}

    # Медленнее CLI: ~1.25с между search. На 429 searcher сам ждёт и продолжает.
    searcher = SpotifySearcher(
        access_token,
        pause_sec=1.25,
        should_stop=should_stop,
        on_wait=on_wait,
    )

    processed_ref: dict[str, Any] = dict(processed)
    # Сколько реально новых search с этого запуска — для checkpoint.
    new_searches = {"n": 0}
    initial_ids = set(processed.keys())

    def wrapped_progress(done: int, total: int, row: dict[str, Any]) -> None:
        source_id = row["source_id"]
        processed_ref[source_id] = row
        if source_id not in initial_ids:
            new_searches["n"] += 1
            # Checkpoint каждые 25 новых search — resume не переписывает 1 МБ зря.
            if new_searches["n"] % 25 == 0:
                _write_state(state_file, processed_ref)
        if done == total:
            _write_state(state_file, processed_ref)
        if progress is not None:
            progress(done, total)

    try:
        report = run_dry_run(
            tracks,
            searcher,
            processed=processed,
            on_progress=wrapped_progress,
            should_stop=should_stop,
        )
    except SpotifyCancelled as exc:
        _write_state(state_file, processed_ref)
        raise PlanError(
            "Остановлено. Прогресс сохранён — снова /plan продолжит с этого места."
        ) from exc
    except SpotifyQuotaExceeded as exc:
        _write_state(state_file, processed_ref)
        raise PlanQuotaExceededError(
            done=len(processed_ref),
            retry_after_sec=exc.retry_after_sec,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        _write_state(state_file, processed_ref)
        message = str(exc)
        if "HTTP 401" in message or "HTTP 403" in message:
            raise PlanError(
                "Spotify не принял запрос (сеть, VPN или сессия). "
                "Проверь VPN и при необходимости /connect_spotify, потом /plan снова."
            ) from exc
        raise PlanError(
            "Не удалось подобрать треки в Spotify. Попробуй /plan ещё раз."
        ) from exc

    processed_final = report["processed"]
    _write_state(state_file, processed_final)
    public_report = {key: value for key, value in report.items() if key != "processed"}
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(public_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    tz = report["tz_counts"]
    return PlanResult(
        telegram_id=telegram_id,
        track_count=int(report["track_count"]),
        auto_count=int(tz.get("exact", 0)),
        review_count=int(tz.get("review", 0)),
        not_found_count=int(tz.get("not_found", 0)),
        cancelled=bool(report.get("cancelled")),
        resumed=bool(processed),
        state_path=state_file,
        report_path=report_file,
    )


def _write_state(path: Path, processed: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"processed": processed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
