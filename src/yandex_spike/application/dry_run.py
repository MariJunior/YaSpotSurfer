"""Search + match без записи в Spotify. Кэш dry-run пересчитывает status при смене порога."""

from __future__ import annotations

from collections.abc import Callable
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from yandex_spike.application.ports import MusicCatalogSearcher
from yandex_spike.application.search_query import build_search_query
from yandex_spike.domain.entities import MatchResult, Track
from yandex_spike.domain.matching import MatchConfig, match_track


ProgressFn = Callable[[int, int, dict[str, Any]], None]


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


def reclassify_match_row(
    row: dict[str, Any],
    config: MatchConfig | None = None,
) -> dict[str, Any]:
    """Пересчитывает status по текущему порогу без нового search. decision важнее."""
    config = config or MatchConfig()
    if row.get("decision"):
        return dict(row)

    candidates = list(row.get("candidates") or [])
    score = row.get("score")
    if score is None and candidates:
        score = candidates[0].get("score")
    selected = row.get("selected")
    updated = dict(row)
    if score is None:
        updated["status"] = "not-found"
        return updated

    score = float(score)
    second_score = candidates[1].get("score") if len(candidates) >= 2 else None
    second_id = candidates[1].get("id") if len(candidates) >= 2 else None
    first_id = candidates[0].get("id") if candidates else None
    if (
        second_score is not None
        and first_id
        and second_id
        and first_id != second_id
        and score >= config.auto_threshold
        and float(second_score) >= config.auto_threshold
        and (score - float(second_score)) < config.ambiguous_delta
    ):
        updated["status"] = "review"
        return updated

    if score < config.review_threshold:
        updated["status"] = "not-found"
        return updated
    if not selected:
        updated["status"] = "review"
        return updated
    if score < config.auto_threshold:
        updated["status"] = "review"
        return updated

    reasons = (candidates[0].get("reasons") if candidates else None) or {}
    exact = reasons.get("isrc") == 1.0 or (
        reasons.get("title", 0) >= 0.999
        and reasons.get("artist", 0) >= 0.98
        and reasons.get("duration", 0) >= 0.95
        and reasons.get("version", 0) == 1.0
    )
    updated["status"] = "exact" if exact else "high-confidence"
    updated["score"] = score
    return updated


def run_dry_run(
    tracks: list[Track],
    searcher: MusicCatalogSearcher,
    *,
    processed: dict[str, dict[str, Any]] | None = None,
    config: MatchConfig | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Search + match. Никаких save/create — порт searcher их не содержит."""
    config = config or MatchConfig()
    done = dict(processed or {})
    rows: list[dict[str, Any]] = []
    total = len(tracks)

    for track in tracks:
        existing = done.get(track.id)
        if existing:
            row = reclassify_match_row(existing, config)
            done[track.id] = row
        else:
            query = build_search_query(track)
            candidates = searcher.search_track(track)
            result = match_track(track, candidates, config)
            row = serialize_match(track, result, query)
            done[track.id] = row
        rows.append(row)
        if on_progress:
            on_progress(len(rows), total, row)

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
