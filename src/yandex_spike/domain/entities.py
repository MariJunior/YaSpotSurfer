"""Доменные сущности. Без импортов yandex_music / requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ArtistRef:
    name: str
    normalized_name: str
    provider_id: str | None = None


@dataclass(frozen=True)
class AlbumRef:
    title: str
    normalized_title: str
    year: int | None = None
    provider_id: str | None = None


@dataclass(frozen=True)
class Track:
    """Провайдер-независимый трек.

    ``id`` — ``yandex:{sourceId}`` или ``spotify:{id}``.
    ``raw`` в matching и JSON-store не участвует.
    """

    id: str
    title: str
    normalized_title: str
    artists: tuple[ArtistRef, ...]
    album: AlbumRef | None = None
    duration_ms: int | None = None
    version: str | None = None
    version_tags: tuple[str, ...] = ()
    isrc: str | None = None
    available: bool | None = None
    provider_ids: tuple[tuple[str, str], ...] = ()
    raw: object | None = None


@dataclass(frozen=True)
class Playlist:
    id: str
    title: str
    track_ids: tuple[str, ...]
    provider_ids: tuple[tuple[str, str], ...] = ()


MatchStatus = Literal[
    "exact",
    "high-confidence",
    "review",
    "not-found",
    "skipped",
]


@dataclass(frozen=True)
class MatchCandidate:
    track: Track
    score: float
    reasons: dict[str, float]


@dataclass(frozen=True)
class MatchResult:
    source_track: Track
    candidates: tuple[MatchCandidate, ...]
    selected: MatchCandidate | None
    status: MatchStatus
