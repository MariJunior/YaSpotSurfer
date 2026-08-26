"""Подключение Яндекса: ссылка → флаг «ждём URL» → удаление сообщения с ключом.

Без ConversationHandler: кнопка меню + вставка текста не уживаются с per_message
без предупреждения PTB (см. FAQ per_* settings).
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.yandex_connect import (
    YandexConnectError,
    begin_yandex_connect,
    complete_yandex_connect,
)
from yandex_spike.telegram.copy import (
    YANDEX_CONNECT_CANCELLED,
    YANDEX_CONNECT_INTRO,
    YANDEX_CONNECTED,
    yandex_connect_failed_text,
)
from yandex_spike.telegram.deps import telegram_user_id, user_store
from yandex_spike.telegram.keyboards import yandex_auth_keyboard

logger = logging.getLogger(__name__)

# Флаг в context.user_data: пользователь должен прислать redirect URL.
_AWAITING_YANDEX_URL = "awaiting_yandex_url"


def is_awaiting_yandex_url(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get(_AWAITING_YANDEX_URL))


def _set_awaiting(context: ContextTypes.DEFAULT_TYPE, value: bool) -> None:
    if value:
        context.user_data[_AWAITING_YANDEX_URL] = True
    else:
        context.user_data.pop(_AWAITING_YANDEX_URL, None)


async def _reply_origin(update: Update, text: str, **kwargs) -> None:
    if update.callback_query is not None:
        origin = update.callback_query.message
        if isinstance(origin, Message):
            await origin.reply_text(text, **kwargs)
            return
    message = update.effective_message
    if message is not None:
        await message.reply_text(text, **kwargs)


async def start_yandex_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return
    if update.callback_query is not None:
        await update.callback_query.answer()
    link = begin_yandex_connect()
    _set_awaiting(context, True)
    await _reply_origin(
        update,
        YANDEX_CONNECT_INTRO,
        reply_markup=yandex_auth_keyboard(link.authorize_url),
    )


async def cmd_connect_yandex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_yandex_connect(update, context)


async def yandex_receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает paste URL. True — сообщение съели (не слать HELP_HINT)."""
    if not is_awaiting_yandex_url(context):
        return False

    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None or not message.text:
        return True

    pasted = message.text
    chat_id = message.chat_id

    # Сразу убираем ключ из чата — до долгой сетевой проверки.
    try:
        await message.delete()
    except Exception:
        logger.info("Could not delete Yandex URL message for chat_id=%s", chat_id)

    await context.bot.send_message(
        chat_id=chat_id,
        text="Проверяю доступ к Яндекс Музыке…",
    )

    error_text: str | None = None
    try:
        # HTTP в отдельном потоке: не блокируем polling бота на таймаутах сети.
        await asyncio.to_thread(
            complete_yandex_connect,
            user_store(context),
            telegram_id,
            pasted,
        )
    except YandexConnectError as exc:
        error_text = yandex_connect_failed_text(str(exc))
    except Exception:
        logger.exception("Yandex connect failed")
        error_text = yandex_connect_failed_text(
            "Что-то пошло не так при сохранении. Попробуй /connect_yandex ещё раз."
        )

    if error_text is not None:
        # Остаёмся в режиме ожидания — можно прислать URL ещё раз.
        await context.bot.send_message(chat_id=chat_id, text=error_text)
        return True

    _set_awaiting(context, False)
    await context.bot.send_message(chat_id=chat_id, text=YANDEX_CONNECTED)
    return True


async def cmd_cancel_yandex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not is_awaiting_yandex_url(context):
        if message is not None:
            await message.reply_text("Сейчас нечего отменять.")
        return
    _set_awaiting(context, False)
    if message is not None:
        await message.reply_text(YANDEX_CONNECT_CANCELLED)
