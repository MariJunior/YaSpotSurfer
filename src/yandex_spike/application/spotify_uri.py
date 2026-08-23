from __future__ import annotations


def to_track_uri(provider_id: str) -> str:
    """domain id `spotify:{id}` → Web API `spotify:track:{id}`."""
    value = provider_id.strip()
    if value.startswith("spotify:track:"):
        return value
    if value.startswith("spotify:"):
        return f"spotify:track:{value.split(':', 1)[1]}"
    return f"spotify:track:{value}"
