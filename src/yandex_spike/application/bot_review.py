""" /review: спорные совпадения из dry-run-state пользователя бота. """

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yandex_spike.application.plan import plan_report_path, plan_state_path
from yandex_spike.application.review import (
    accept_candidate,
    apply_decision,
    list_open_reviews,
)


class BotReviewError(RuntimeError):
    """Понятная ошибка для чата."""


@dataclass(frozen=True)
class ReviewCard:
    source_id: str
    title: str
    artists: tuple[str, ...]
    candidates: tuple[dict[str, Any], ...]
    open_remaining: int


@dataclass(frozen=True)
class ReviewDecisionResult:
    source_id: str
    action: str
    open_remaining: int
    chosen_title: str | None = None


def _load_processed(telegram_id: int, *, root: Path | None) -> dict[str, Any]:
    path = plan_state_path(telegram_id, root=root)
    if not path.exists():
        raise BotReviewError(
            "Сначала /plan — нужен подбор лайков в Spotify.\n"
            "Без него разбирать нечего."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BotReviewError(
            "Файл подбора повреждён. Запусти /plan ещё раз."
        ) from exc
    return dict(payload.get("processed") or {})


def _write_processed(
    telegram_id: int,
    processed: dict[str, Any],
    *,
    root: Path | None,
) -> None:
    path = plan_state_path(telegram_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"processed": processed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Обновляем сводку отчёта, если она уже есть (для /status).
    report_path = plan_report_path(telegram_id, root=root)
    if not report_path.exists():
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    open_n = len(list_open_reviews(processed))
    accepted = sum(1 for row in processed.values() if row.get("decision") == "accept")
    skipped = sum(1 for row in processed.values() if row.get("decision") == "skip")
    report["review_open"] = open_n
    report["review_accepted"] = accepted
    report["review_skipped"] = skipped
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _artists_tuple(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("artists") or []
    return tuple(str(name) for name in raw)


def _card_from_row(row: dict[str, Any], *, open_remaining: int) -> ReviewCard:
    candidates = list(row.get("candidates") or [])[:2]
    return ReviewCard(
        source_id=str(row["source_id"]),
        title=str(row.get("title") or "—"),
        artists=_artists_tuple(row),
        candidates=tuple(candidates),
        open_remaining=open_remaining,
    )


def peek_next_review(
    telegram_id: int,
    *,
    data_root: Path | None = None,
    defer_ids: set[str] | None = None,
) -> ReviewCard | None:
    processed = _load_processed(telegram_id, root=data_root)
    open_rows = list_open_reviews(processed, defer_ids=defer_ids)
    if not open_rows:
        return None
    return _card_from_row(open_rows[0], open_remaining=len(open_rows))


def count_open_reviews(
    telegram_id: int,
    *,
    data_root: Path | None = None,
) -> int:
    try:
        processed = _load_processed(telegram_id, root=data_root)
    except BotReviewError:
        return 0
    return len(list_open_reviews(processed))


def decide_review(
    telegram_id: int,
    source_id: str,
    *,
    action: str,
    candidate_index: int | None = None,
    data_root: Path | None = None,
) -> ReviewDecisionResult:
    """action: accept | skip. Для accept без selected нужен candidate_index."""
    processed = _load_processed(telegram_id, root=data_root)
    if source_id not in processed:
        raise BotReviewError("Этот трек уже не в очереди. Нажми /review.")

    chosen_title: str | None = None
    if action == "skip":
        apply_decision(processed, source_id, "skip")
    elif action == "accept":
        row = processed[source_id]
        if candidate_index is not None:
            updated = accept_candidate(processed, source_id, candidate_index)
        elif row.get("selected"):
            updated = apply_decision(processed, source_id, "accept")
        elif row.get("candidates"):
            # Один кандидат без selected (редкий кейс) — берём первый.
            updated = accept_candidate(processed, source_id, 0)
        else:
            raise BotReviewError("Нечего принимать — кандидатов нет. Пропусти трек.")
        chosen_title = (updated.get("selected") or {}).get("title")
    else:
        raise BotReviewError(f"Неизвестное действие: {action}")

    _write_processed(telegram_id, processed, root=data_root)
    remaining = len(list_open_reviews(processed))
    return ReviewDecisionResult(
        source_id=source_id,
        action=action,
        open_remaining=remaining,
        chosen_title=chosen_title,
    )
