"""Общий доступ к bot_data из хендлеров."""

from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from yandex_spike.application.ports import UserAccountStore
from yandex_spike.application.scan import BOT_USERS_DATA_DIR


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


def telegram_user_data_root(context: ContextTypes.DEFAULT_TYPE) -> Path:
    """Корень per-user snapshot: `.data/bot-users` (или override в bot_data)."""
    root = context.application.bot_data.get("bot_users_data_dir")
    if root is None:
        return BOT_USERS_DATA_DIR
    return Path(root)
