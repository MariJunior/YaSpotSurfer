from __future__ import annotations

import json
from pathlib import Path

from yandex_spike.domain.entities import Track
from yandex_spike.infrastructure.yandex.mapper import track_from_yandex_snapshot


def preview_liked_tracks(snapshot_path: Path, limit: int = 20) -> list[Track]:
    """Читает inspect-snapshot и мапит лайки в domain.Track. Write-запросов нет."""
    if not snapshot_path.exists():
        raise RuntimeError(
            f"Нет snapshot {snapshot_path}. Сначала: uv run yandex-spike inspect"
        )

    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    items = data.get("liked_tracks") or []
    return [track_from_yandex_snapshot(item) for item in items[:limit]]
