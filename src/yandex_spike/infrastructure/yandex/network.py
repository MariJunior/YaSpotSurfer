from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from yandex_music.exceptions import NetworkError, TimedOutError

T = TypeVar("T")

YANDEX_ATTEMPTS = 4


def call_yandex(
    label: str,
    fn: Callable[..., T],
    *args: object,
    attempts: int = YANDEX_ATTEMPTS,
    sleep_fn: Callable[[float], None] = time.sleep,
    **kwargs: object,
) -> T:
    """Ретрай TimedOut/Network как у Spotify _api. Библиотека сама не ретраит."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except (TimedOutError, NetworkError) as exc:
            last_error = exc
            print(
                f"Сеть: Яндекс {label} не достучался "
                f"(попытка {attempt}/{attempts})."
            )
            if attempt < attempts:
                sleep_fn(2 * attempt)
    raise RuntimeError(
        f"Не удалось достучаться до api.music.yandex.net ({label}). "
        "VPN часто роняет Яндекс, пока Spotify ещё жив. Повтори команду "
        "или на шаг выгрузки выключи VPN."
    ) from last_error
