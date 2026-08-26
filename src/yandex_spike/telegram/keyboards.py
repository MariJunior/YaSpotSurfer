"""Inline-клавиатуры. Импортирует PTB — не тянуть в unit-тесты copy."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from yandex_spike.telegram.copy import (
    CALLBACK_CONNECT_SPOTIFY,
    CALLBACK_CONNECT_YANDEX,
    CALLBACK_HELP,
    CALLBACK_SCAN,
)


def start_keyboard() -> InlineKeyboardMarkup:
    """Меню /start: connect / scan / help."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Подключить Яндекс", callback_data=CALLBACK_CONNECT_YANDEX),
                InlineKeyboardButton("Подключить Spotify", callback_data=CALLBACK_CONNECT_SPOTIFY),
            ],
            [InlineKeyboardButton("Собрать список треков", callback_data=CALLBACK_SCAN)],
            [InlineKeyboardButton("Помощь", callback_data=CALLBACK_HELP)],
        ]
    )


def spotify_auth_keyboard(authorize_url: str) -> InlineKeyboardMarkup:
    """Кнопка-ссылка: Telegram сам откроет браузер."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть Spotify", url=authorize_url)]]
    )
