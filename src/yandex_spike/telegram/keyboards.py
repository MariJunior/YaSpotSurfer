"""Inline-клавиатуры. Импортирует PTB — не тянуть в unit-тесты copy."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from yandex_spike.telegram.copy import (
    CALLBACK_CONNECT_SPOTIFY,
    CALLBACK_CONNECT_YANDEX,
    CALLBACK_HELP,
    CALLBACK_PLAN,
    CALLBACK_REVIEW,
    CALLBACK_SCAN,
    CALLBACK_STATUS,
)


def start_keyboard() -> InlineKeyboardMarkup:
    """Меню /start: connect / scan / plan / review / help."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎵 Подключить Яндекс", callback_data=CALLBACK_CONNECT_YANDEX),
                InlineKeyboardButton("🎧 Подключить Spotify", callback_data=CALLBACK_CONNECT_SPOTIFY),
            ],
            [InlineKeyboardButton("📥 Собрать список треков", callback_data=CALLBACK_SCAN)],
            [
                InlineKeyboardButton("🔎 Подобрать лайки", callback_data=CALLBACK_PLAN),
                InlineKeyboardButton("🟡 Спорные", callback_data=CALLBACK_REVIEW),
            ],
            [InlineKeyboardButton("📖 Помощь", callback_data=CALLBACK_HELP)],
        ]
    )


def after_scan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔎 Подобрать лайки в Spotify", callback_data=CALLBACK_PLAN)],
            [InlineKeyboardButton("⏳ Что сейчас происходит", callback_data=CALLBACK_STATUS)],
        ]
    )


def after_plan_keyboard(*, has_review: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_review:
        rows.append(
            [InlineKeyboardButton("🟡 Разобрать спорные", callback_data=CALLBACK_REVIEW)]
        )
    rows.append(
        [InlineKeyboardButton("⏳ Что сейчас происходит", callback_data=CALLBACK_STATUS)]
    )
    return InlineKeyboardMarkup(rows)


def spotify_auth_keyboard(authorize_url: str) -> InlineKeyboardMarkup:
    """Кнопка-ссылка: Telegram сам откроет браузер."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎧 Открыть Spotify", url=authorize_url)]]
    )


def yandex_auth_keyboard(authorize_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎵 Открыть Яндекс", url=authorize_url)]]
    )
