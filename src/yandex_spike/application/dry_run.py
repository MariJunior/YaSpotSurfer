from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from yandex_spike.application.ports import MusicCatalogSearcher
from yandex_spike.application.search_query import build_search_query
from yandex_spike.domain.entities import MatchResult, Track
from yandex_spike.domain.matching import MatchConfig, match_track


def _candidate_row(result: MatchResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in result.candidates:
        rows.append(
            {
                "id": candidate.track.id,
                "title": candidate.track.title,
                "artists": [artist.name for artist in candidate.track.artists],
                "isrc": candidate.track.isrc,
                "duration_ms": candidate.track.duration_ms,
                "score": candidate.score,
                "reasons": candidate.reasons,
            }
        )
    return rows


def serialize_match(source: Track, result: MatchResult, query: str) -> dict[str, Any]:
    selected = result.selected
    return {
        "source_id": source.id,
        "title": source.title,
        "artists": [artist.name for artist in source.artists],
        "duration_ms": source.duration_ms,
        "version": source.version,
        "query": query,
        "status": result.status,
        "score": selected.score if selected else None,
        "selected": (
            {
                "id": selected.track.id,
                "title": selected.track.title,
                "artists": [artist.name for artist in selected.track.artists],
                "isrc": selected.track.isrc,
            }
            if selected
            else None
        ),
        "candidates": _candidate_row(result),
    }


def run_dry_run(
    tracks: list[Track],
    searcher: MusicCatalogSearcher,
    *,
    processed: dict[str, dict[str, Any]] | None = None,
    config: MatchConfig | None = None,
) -> dict[str, Any]:
    """Search + match. Никаких save/create — порт searcher их не содержит."""
    config = config or MatchConfig()
    done = dict(processed or {})
    rows: list[dict[str, Any]] = []

    for track in tracks:
        existing = done.get(track.id)
        if existing:
            rows.append(existing)
            continue
        query = build_search_query(track)
        candidates = searcher.search_track(track)
        result = match_track(track, candidates, config)
        row = serialize_match(track, result, query)
        done[track.id] = row
        rows.append(row)

    counts: Counter[str] = Counter(row["status"] for row in rows)
    tz_counts = {
        "exact": counts.get("exact", 0) + counts.get("high-confidence", 0),
        "review": counts.get("review", 0),
        "not_found": counts.get("not-found", 0),
    }
    return {
        "dry_run": True,
        "wrote_to_spotify": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "track_count": len(rows),
        "resumed": bool(processed),
        "counts": dict(counts),
        "tz_counts": tz_counts,
        "processed": done,
        "results": rows,
    }
