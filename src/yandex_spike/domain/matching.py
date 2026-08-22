from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

from .entities import MatchCandidate, MatchResult, Track
from .normalization import extract_version_tags
from .transliteration import transliterate


# remastered и remaster — одна версия записи, не original.
_TAG_ALIASES = {
    "remastered": "remaster",
}


@dataclass(frozen=True)
class MatchConfig:
    title_weight: float = 0.45
    artist_weight: float = 0.30
    album_weight: float = 0.15
    duration_weight: float = 0.10
    auto_threshold: float = 0.92
    review_threshold: float = 0.70
    duration_full_ms: int = 2000
    duration_zero_ms: int = 15000
    ambiguous_delta: float = 0.03
    # Несовместимые версии нельзя отправить в auto, даже при score 0.99.
    version_auto_cap: float = 0.919


def _ratio(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _text_similarity(left: str, right: str) -> float:
    direct = _ratio(left, right)
    folded = _ratio(transliterate(left), transliterate(right))
    return max(direct, folded)


def _canonical_tags(tags: Sequence[str]) -> frozenset[str]:
    return frozenset(_TAG_ALIASES.get(tag, tag) for tag in tags)


def effective_version_tags(track: Track) -> frozenset[str]:
    """Теги из title и из Yandex-поля version (часто только там remaster/live)."""
    merged = list(track.version_tags)
    if track.version:
        merged.extend(extract_version_tags(track.version))
    return _canonical_tags(merged)


def _normalize_isrc(value: str | None) -> str | None:
    if not value:
        return None
    compact = value.strip().upper()
    return compact or None


def artist_similarity(source: Track, candidate: Track) -> float:
    source_names = [artist.normalized_name for artist in source.artists if artist.normalized_name]
    candidate_names = [
        artist.normalized_name for artist in candidate.artists if artist.normalized_name
    ]
    if not source_names and not candidate_names:
        return 1.0
    if not source_names or not candidate_names:
        return 0.0

    # Порядок исполнителей не важен: жадно закрываем лучшие пары.
    used: set[int] = set()
    pair_scores: list[float] = []
    for name in source_names:
        best = 0.0
        best_index = -1
        for index, other in enumerate(candidate_names):
            if index in used:
                continue
            score = _text_similarity(name, other)
            if score > best:
                best = score
                best_index = index
        if best_index >= 0:
            used.add(best_index)
            pair_scores.append(best)

    average = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
    coverage = len(pair_scores) / max(len(source_names), len(candidate_names))
    return average * 0.7 + coverage * 0.3


def album_similarity(source: Track, candidate: Track) -> float:
    source_title = source.album.normalized_title if source.album else ""
    candidate_title = candidate.album.normalized_title if candidate.album else ""
    if not source_title or not candidate_title:
        # Нет альбома — нейтрально, не валим точный title+artist.
        return 0.7
    return _text_similarity(source_title, candidate_title)


def duration_similarity(
    source: Track,
    candidate: Track,
    config: MatchConfig,
) -> float:
    if source.duration_ms is None or candidate.duration_ms is None:
        return 0.5
    delta = abs(source.duration_ms - candidate.duration_ms)
    if delta <= config.duration_full_ms:
        return 1.0
    if delta >= config.duration_zero_ms:
        return 0.0
    span = config.duration_zero_ms - config.duration_full_ms
    return 1.0 - (delta - config.duration_full_ms) / span


def score_candidate(
    source: Track,
    candidate: Track,
    config: MatchConfig | None = None,
) -> MatchCandidate:
    config = config or MatchConfig()
    source_isrc = _normalize_isrc(source.isrc)
    candidate_isrc = _normalize_isrc(candidate.isrc)

    if source_isrc and candidate_isrc:
        if source_isrc == candidate_isrc:
            return MatchCandidate(
                track=candidate,
                score=1.0,
                reasons={"isrc": 1.0, "title": 1.0, "artist": 1.0, "album": 1.0, "duration": 1.0, "version": 1.0},
            )
        # Разный ISRC — это другая запись, не авто.
        return MatchCandidate(
            track=candidate,
            score=0.0,
            reasons={"isrc": 0.0, "title": 0.0, "artist": 0.0, "album": 0.0, "duration": 0.0, "version": 0.0},
        )

    title = _text_similarity(source.normalized_title, candidate.normalized_title)
    artist = artist_similarity(source, candidate)
    album = album_similarity(source, candidate)
    duration = duration_similarity(source, candidate, config)
    source_tags = effective_version_tags(source)
    candidate_tags = effective_version_tags(candidate)
    version_ok = source_tags == candidate_tags
    version = 1.0 if version_ok else 0.0

    score = (
        title * config.title_weight
        + artist * config.artist_weight
        + album * config.album_weight
        + duration * config.duration_weight
    )
    # wrong match > missing: remaster/live/remix не проходят auto-порог.
    if not version_ok:
        score = min(score, config.version_auto_cap)

    return MatchCandidate(
        track=candidate,
        score=round(score, 4),
        reasons={
            "title": round(title, 4),
            "artist": round(artist, 4),
            "album": round(album, 4),
            "duration": round(duration, 4),
            "version": version,
        },
    )


def _is_exact_shape(candidate: MatchCandidate) -> bool:
    reasons = candidate.reasons
    return (
        reasons.get("isrc") == 1.0
        or (
            reasons.get("title", 0) >= 0.999
            and reasons.get("artist", 0) >= 0.98
            and reasons.get("duration", 0) >= 0.95
            and reasons.get("version", 0) == 1.0
        )
    )


def match_track(
    source: Track,
    candidates: Sequence[Track],
    config: MatchConfig | None = None,
) -> MatchResult:
    config = config or MatchConfig()
    scored = [score_candidate(source, candidate, config) for candidate in candidates]
    scored.sort(key=lambda item: item.score, reverse=True)
    top = tuple(scored[:5])

    if not top or top[0].score < config.review_threshold:
        return MatchResult(
            source_track=source,
            candidates=top,
            selected=None,
            status="not-found",
        )

    best = top[0]
    second = top[1] if len(top) > 1 else None
    # Два почти равных auto — лучше review, чем угадать не тот кавер.
    if (
        second is not None
        and best.track.id != second.track.id
        and best.score >= config.auto_threshold
        and second.score >= config.auto_threshold
        and (best.score - second.score) < config.ambiguous_delta
    ):
        return MatchResult(
            source_track=source,
            candidates=top,
            selected=None,
            status="review",
        )

    if best.score >= config.auto_threshold:
        status = "exact" if _is_exact_shape(best) else "high-confidence"
        return MatchResult(
            source_track=source,
            candidates=top,
            selected=best,
            status=status,
        )

    return MatchResult(
        source_track=source,
        candidates=top,
        selected=best,
        status="review",
    )
