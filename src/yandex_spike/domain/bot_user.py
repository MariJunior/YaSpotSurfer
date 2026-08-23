"""Пользователь бота как арендатор. Секреты в эту сущность не кладём."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotUser:
    telegram_id: int
    yandex_connected: bool = False
    spotify_connected: bool = False
    spotify_display_name: str | None = None
