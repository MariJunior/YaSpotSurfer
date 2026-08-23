"""Хендлеры B1: личка, /start, /help, заглушки кнопок. Без HTTP к музыке."""

from __future__ import annotations

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.telegram.copy import (
    CALLBACK_CONNECT_SPOTIFY,
    CALLBACK_CONNECT_YANDEX,
    CALLBACK_HELP,
    CALLBACK_SCAN,
    HELP_HINT,
    HELP_TEXT,
    NOT_READY_CONNECT,
    NOT_READY_SCAN,
    UNKNOWN_COMMAND,
    start_text,
)
from yandex_spike.telegram.keyboards import start_keyboard


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context  # B1: нет user store, статус всегда «не подключена»
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(start_text(), reply_markup=start_keyboard())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(HELP_TEXT)


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки /start. Connect/scan не вызывают API — только честный stub."""
    del context
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    chat = update.effective_chat
    if chat is None or chat.type != Chat.PRIVATE:
        return
    # InaccessibleMessage не умеет reply_text — отвечаем только на живое Message.
    origin = query.message
    if not isinstance(origin, Message):
        return
    if query.data == CALLBACK_HELP:
        await origin.reply_text(HELP_TEXT)
        return
    if query.data in {CALLBACK_CONNECT_YANDEX, CALLBACK_CONNECT_SPOTIFY}:
        await origin.reply_text(NOT_READY_CONNECT)
        return
    if query.data == CALLBACK_SCAN:
        await origin.reply_text(NOT_READY_SCAN)


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(UNKNOWN_COMMAND)


async def on_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(HELP_HINT)
