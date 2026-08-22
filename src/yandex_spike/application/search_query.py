from __future__ import annotations

from yandex_spike.domain.entities import Track


def _sanitize(value: str) -> str:
    return value.replace('"', " ").replace(":", " ").strip()


def build_search_query(track: Track) -> str:
    """Spotify field filters. limit search ≤ 10 — Dev Mode после Feb 2026."""
    title = _sanitize(track.title or track.normalized_title)
    artist = _sanitize(track.artists[0].name if track.artists else "")
    parts: list[str] = []
    if title:
        parts.append(f'track:"{title}"')
    if artist:
        parts.append(f'artist:"{artist}"')
    return " ".join(parts) or track.normalized_title


def build_fallback_query(track: Track) -> str:
    """Без field filters, если точный track: artist: ничего не нашёл."""
    title = _sanitize(track.title or track.normalized_title)
    artist = _sanitize(track.artists[0].name if track.artists else "")
    return " ".join(part for part in (title, artist) if part)
