"""Хендлеры: личка, SQLite, Spotify OAuth, меню. Яндекс — в yandex_flow."""

from __future__ import annotations

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.accounts import load_account, logout_account
from yandex_spike.application.spotify_connect import SpotifyConnectService, SpotifyOAuthError
from yandex_spike.telegram.copy import (
    CALLBACK_CONNECT_SPOTIFY,
    CALLBACK_CONNECT_YANDEX,
    CALLBACK_HELP,
    CALLBACK_SCAN,
    HELP_HINT,
    HELP_TEXT,
    LOGOUT_DONE,
    LOGOUT_NOTHING,
    NOT_READY_SCAN,
    SPOTIFY_CONNECT_INTRO,
    SPOTIFY_CONNECT_NOT_CONFIGURED,
    UNKNOWN_COMMAND,
    spotify_connect_failed_text,
    start_text,
)
from yandex_spike.telegram.deps import telegram_user_id, user_store
from yandex_spike.telegram.keyboards import spotify_auth_keyboard, start_keyboard
from yandex_spike.telegram.yandex_flow import start_yandex_connect, yandex_receive_url


def _spotify_connect(context: ContextTypes.DEFAULT_TYPE) -> SpotifyConnectService | None:
    return context.application.bot_data.get("spotify_connect")


async def _send_spotify_link(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
) -> None:
    service = _spotify_connect(context)
    if service is None:
        await message.reply_text(SPOTIFY_CONNECT_NOT_CONFIGURED)
        return
    try:
        link = service.begin(telegram_id)
    except SpotifyOAuthError as exc:
        await message.reply_text(spotify_connect_failed_text(str(exc)))
        return
    await message.reply_text(
        SPOTIFY_CONNECT_INTRO,
        reply_markup=spotify_auth_keyboard(link.authorize_url),
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None:
        return
    account = load_account(user_store(context), telegram_id)
    await message.reply_text(
        start_text(
            yandex_connected=account.yandex_connected,
            spotify_display_name=(
                account.spotify_display_name if account.spotify_connected else None
            ),
        ),
        reply_markup=start_keyboard(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(HELP_TEXT)


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None:
        return
    had = logout_account(user_store(context), telegram_id)
    await message.reply_text(LOGOUT_DONE if had else LOGOUT_NOTHING)


async def cmd_connect_spotify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None:
        return
    await _send_spotify_link(message, context, telegram_id)


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки /start."""
    query = update.callback_query
    if query is None or query.data is None:
        return
    chat = update.effective_chat
    if chat is None or chat.type != Chat.PRIVATE:
        return
    # Яндекс сам делает query.answer() внутри start_yandex_connect.
    if query.data == CALLBACK_CONNECT_YANDEX:
        await start_yandex_connect(update, context)
        return
    await query.answer()
    origin = query.message
    if not isinstance(origin, Message):
        return
    if query.data == CALLBACK_HELP:
        await origin.reply_text(HELP_TEXT)
        return
    if query.data == CALLBACK_CONNECT_SPOTIFY:
        telegram_id = telegram_user_id(update)
        if telegram_id is None:
            return
        await _send_spotify_link(origin, context, telegram_id)
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
    # Сначала paste URL для Яндекса, иначе — подсказка /help.
    if await yandex_receive_url(update, context):
        return
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(HELP_HINT)
