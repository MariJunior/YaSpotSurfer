"""Подпись OAuth state: telegram_id нельзя подделать без ключа шифрования."""

from __future__ import annotations

import time

from yandex_spike.infrastructure.token_cipher import TokenCipher

# Сколько секунд живёт ссылка «Подключить Spotify».
DEFAULT_TTL_SEC = 600


def make_oauth_state(
    cipher: TokenCipher,
    telegram_id: int,
    *,
    ttl_sec: int = DEFAULT_TTL_SEC,
    now: int | None = None,
) -> str:
    """Шифруем tid:exp — Fernet уже url-safe, подходит в query state."""
    expires_at = (now if now is not None else int(time.time())) + ttl_sec
    return cipher.encrypt(f"{telegram_id}:{expires_at}")


def parse_oauth_state(
    cipher: TokenCipher,
    state: str,
    *,
    now: int | None = None,
) -> int | None:
    """None — подделка, просрочка или битый формат."""
    plain = cipher.decrypt(state)
    if plain is None:
        return None
    try:
        tid_raw, exp_raw = plain.split(":", 1)
        telegram_id = int(tid_raw)
        expires_at = int(exp_raw)
    except ValueError:
        return None
    if (now if now is not None else int(time.time())) > expires_at:
        return None
    return telegram_id
