"""Запись уже сматченных треков. Не вызывает search."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from yandex_spike.application.ports import LibraryWriter
from yandex_spike.application.spotify_uri import to_track_uri

AUTO_STATUSES = frozenset({"exact", "high-confidence"})
DONE_WRITES = frozenset({"saved", "already"})

ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]


def is_writable(match: dict[str, Any]) -> bool:
    """Auto (exact / high-confidence) или ручной accept. skip всегда сильнее."""
    if match.get("decision") == "skip":
        return False
    if match.get("decision") == "accept" and match.get("selected"):
        return True
    return match.get("status") in AUTO_STATUSES and bool(match.get("selected"))


def write_matched_tracks(
    match_rows: list[dict[str, Any]],
    writer: LibraryWriter,
    *,
    write_state: dict[str, dict[str, Any]] | None = None,
    migration_id: str,
    on_progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> dict[str, Any]:
    """Пишет только writable-строки. Повтор: checkpoint, затем ``contains``."""
    done = write_state if write_state is not None else {}
    rows: list[dict[str, Any]] = []
    total = len(match_rows)
    cancelled = False

    for match in match_rows:
        if should_stop is not None and should_stop():
            cancelled = True
            break

        source_id = match["source_id"]
        previous = done.get(source_id)
        if previous and previous.get("write_status") in DONE_WRITES:
            rows.append(previous)
            if on_progress is not None:
                on_progress(len(rows), total)
            continue

        status = match.get("status")
        selected = match.get("selected")
        if not is_writable(match):
            record = {
                "source_id": source_id,
                "title": match.get("title"),
                "match_status": status,
                "spotify_uri": None,
                "write_status": "skipped",
            }
            done[source_id] = record
            rows.append(record)
            if on_progress is not None:
                on_progress(len(rows), total)
            continue

        uri = to_track_uri(selected["id"])
        if writer.contains(uri):
            record = {
                "source_id": source_id,
                "title": match.get("title"),
                "match_status": status,
                "spotify_uri": uri,
                "spotify_title": selected.get("title"),
                "write_status": "already",
            }
        else:
            writer.save(uri)
            record = {
                "source_id": source_id,
                "title": match.get("title"),
                "match_status": status,
                "spotify_uri": uri,
                "spotify_title": selected.get("title"),
                "write_status": "saved",
            }
        done[source_id] = record
        rows.append(record)
        if on_progress is not None:
            on_progress(len(rows), total)

    counts: Counter[str] = Counter(row["write_status"] for row in rows)
    return {
        "migration_id": migration_id,
        "wrote_to_spotify": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "track_count": len(rows),
        "cancelled": cancelled,
        "counts": dict(counts),
        "write_state": done,
        "results": rows,
    }
