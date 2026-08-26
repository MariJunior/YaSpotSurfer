"""Общий доступ к bot_data из хендлеров."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from yandex_spike.application.ports import UserAccountStore


def user_store(context: ContextTypes.DEFAULT_TYPE) -> UserAccountStore:
    store = context.application.bot_data.get("user_store")
    if store is None:
        raise RuntimeError("user_store is not configured")
    return store


def telegram_user_id(update: Update) -> int | None:
    user = update.effective_user
    if user is None:
        return None
    return user.id
