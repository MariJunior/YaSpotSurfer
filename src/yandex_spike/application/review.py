"""Очередь ручного review: accept пишет трек, skip — нет."""

from __future__ import annotations

from typing import Any


def list_review_queue(processed: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Открытый review и строки, по которым уже есть accept/skip."""
    return [
        row
        for row in processed.values()
        if row.get("status") == "review" or row.get("decision")
    ]


def list_open_reviews(
    processed: dict[str, dict[str, Any]],
    *,
    defer_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Только status=review без decision; отложенные — в конце."""
    deferred = defer_ids or set()
    open_rows = [
        row
        for row in processed.values()
        if row.get("status") == "review" and not row.get("decision")
    ]
    # Стабильный порядок по source_id — чтобы «Позже» не прыгало хаотично.
    open_rows.sort(key=lambda row: str(row.get("source_id") or ""))
    primary = [row for row in open_rows if row.get("source_id") not in deferred]
    later = [row for row in open_rows if row.get("source_id") in deferred]
    return [*primary, *later]


def apply_decision(
    processed: dict[str, dict[str, Any]],
    source_id: str,
    decision: str,
) -> dict[str, Any]:
    """Пишет ``accept`` / ``skip`` в строку dry-run. Меняет ``processed`` на месте."""
    if decision not in {"accept", "skip"}:
        raise ValueError("decision: accept или skip")
    row = processed.get(source_id)
    if row is None:
        raise KeyError(f"Нет dry-run строки {source_id}")
    if decision == "accept" and not row.get("selected"):
        raise RuntimeError(
            f"{source_id}: нечего принимать — selected пустой."
        )
    updated = dict(row)
    updated["decision"] = decision
    processed[source_id] = updated
    return updated


def accept_candidate(
    processed: dict[str, dict[str, Any]],
    source_id: str,
    candidate_index: int,
) -> dict[str, Any]:
    """Принять кандидата по индексу (бот: кнопки 1/2). Ставит selected + accept."""
    row = processed.get(source_id)
    if row is None:
        raise KeyError(f"Нет dry-run строки {source_id}")
    candidates = list(row.get("candidates") or [])
    if candidate_index < 0 or candidate_index >= len(candidates):
        raise RuntimeError(
            f"{source_id}: нет кандидата #{candidate_index + 1}."
        )
    cand = candidates[candidate_index]
    selected = {
        "id": cand.get("id"),
        "title": cand.get("title"),
        "artists": list(cand.get("artists") or []),
        "isrc": cand.get("isrc"),
    }
    if not selected["id"]:
        raise RuntimeError(f"{source_id}: у кандидата нет Spotify id.")
    updated = dict(row)
    updated["selected"] = selected
    updated["score"] = cand.get("score")
    updated["decision"] = "accept"
    processed[source_id] = updated
    return updated
