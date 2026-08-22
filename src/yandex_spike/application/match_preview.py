from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from yandex_spike.domain.entities import MatchResult, Track
from yandex_spike.domain.matching import MatchConfig, match_track
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot


def select_calibration_tracks(tracks: list[Track], limit: int = 250) -> list[Track]:
    """Смесь обычных и versioned треков из реального snapshot, не синтетика."""
    tagged = [track for track in tracks if track.version_tags]
    plain = [track for track in tracks if not track.version_tags]
    tagged_quota = min(len(tagged), max(80, limit // 5))
    remaining = max(0, limit - tagged_quota)
    return [*tagged[:tagged_quota], *plain[:remaining]]


def _result_row(result: MatchResult) -> dict[str, Any]:
    selected = result.selected
    return {
        "source_id": result.source_track.id,
        "title": result.source_track.title,
        "status": result.status,
        "score": selected.score if selected else (result.candidates[0].score if result.candidates else None),
        "selected_id": selected.track.id if selected else None,
        "reasons": selected.reasons if selected else None,
    }


def preview_self_match(
    snapshot_path: Path,
    *,
    limit: int = 250,
    config: MatchConfig | None = None,
) -> dict[str, Any]:
    """Каждый трек ищем в том же каталоге. Write-запросов к API нет."""
    if not snapshot_path.exists():
        raise RuntimeError(
            f"Нет snapshot {snapshot_path}. Сначала: uv run yandex-spike inspect"
        )

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    tracks = [
        track_from_yandex_snapshot(item)
        for item in (payload.get("liked_tracks") or [])
    ]
    catalog = select_calibration_tracks(tracks, limit)
    config = config or MatchConfig()

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    wrong_auto: list[str] = []
    runner_up_auto: list[dict[str, Any]] = []

    for track in catalog:
        result = match_track(track, catalog, config)
        counts[result.status] += 1
        row = _result_row(result)
        rows.append(row)
        selected_id = row["selected_id"]
        if result.status in {"exact", "high-confidence"} and selected_id != track.id:
            wrong_auto.append(track.id)
        # Self всегда score 1.0. Второй кандидат ≥ 0.92 — возможный дубль или риск.
        others = [
            candidate
            for candidate in result.candidates
            if candidate.track.id != track.id
        ]
        if others and others[0].score >= config.auto_threshold:
            rival = others[0]
            runner_up_auto.append(
                {
                    "source_id": track.id,
                    "title": track.title,
                    "rival_id": rival.track.id,
                    "rival_title": rival.track.title,
                    "rival_score": rival.score,
                    "reasons": rival.reasons,
                }
            )

    return {
        "catalog_size": len(catalog),
        "tagged_in_catalog": sum(1 for track in catalog if track.version_tags),
        "counts": dict(counts),
        "wrong_auto": wrong_auto,
        "wrong_auto_count": len(wrong_auto),
        "runner_up_auto": runner_up_auto,
        "runner_up_auto_count": len(runner_up_auto),
        "results": rows,
    }
