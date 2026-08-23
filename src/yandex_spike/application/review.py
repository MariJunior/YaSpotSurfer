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
