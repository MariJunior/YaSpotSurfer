"""Сценарии аккаунта бота. Без Telegram SDK и без знания Fernet."""

from __future__ import annotations

from yandex_spike.application.ports import UserAccountStore
from yandex_spike.domain.bot_user import BotUser


def load_account(store: UserAccountStore, telegram_id: int) -> BotUser:
    store.ensure(telegram_id)
    return store.get(telegram_id)


def logout_account(store: UserAccountStore, telegram_id: int) -> bool:
    return store.logout(telegram_id)
