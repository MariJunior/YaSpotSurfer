from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Protocol

from yandex_spike.application.spotify_uri import to_track_uri

AUTO_STATUSES = frozenset({"exact", "high-confidence"})
DONE_WRITES = frozenset({"saved", "already"})


class LibraryWriter(Protocol):
    def contains(self, uri: str) -> bool:
        ...

    def save(self, uri: str) -> None:
        ...


def migrate_liked_tracks(
    match_rows: list[dict[str, Any]],
    writer: LibraryWriter,
    *,
    write_state: dict[str, dict[str, Any]] | None = None,
    migration_id: str,
) -> dict[str, Any]:
    """Пишет только auto-match. review/not-found не трогает. Повтор — contains."""
    done = dict(write_state or {})
    rows: list[dict[str, Any]] = []

    for match in match_rows:
        source_id = match["source_id"]
        previous = done.get(source_id)
        if previous and previous.get("write_status") in DONE_WRITES:
            rows.append(previous)
            continue

        status = match.get("status")
        selected = match.get("selected")
        if status not in AUTO_STATUSES or not selected:
            record = {
                "source_id": source_id,
                "title": match.get("title"),
                "match_status": status,
                "spotify_uri": None,
                "write_status": "skipped",
            }
            done[source_id] = record
            rows.append(record)
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

    counts: Counter[str] = Counter(row["write_status"] for row in rows)
    return {
        "migration_id": migration_id,
        "wrote_to_spotify": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "track_count": len(rows),
        "counts": dict(counts),
        "write_state": done,
        "results": rows,
    }
