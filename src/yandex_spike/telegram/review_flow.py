""" /review: карточка спорного трека + inline-кнопки. """

from __future__ import annotations

import logging
import secrets

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.bot_review import (
    BotReviewError,
    ReviewCard,
    count_open_reviews,
    decide_review,
    peek_next_review,
)
from yandex_spike.telegram.copy import (
    REVIEW_EMPTY,
    REVIEW_NEED_PLAN,
    REVIEW_STALE,
    review_accepted_flash,
    review_card_text,
    review_done_text,
    review_failed_text,
)
from yandex_spike.telegram.deps import telegram_user_data_root, telegram_user_id, user_store


logger = logging.getLogger(__name__)

_DEFER_KEY = "review_defer_ids"


def _defer_ids(context: ContextTypes.DEFAULT_TYPE) -> set[str]:
    raw = context.user_data.get(_DEFER_KEY) or []
    return set(raw)


def _set_defer_ids(context: ContextTypes.DEFAULT_TYPE, ids: set[str]) -> None:
    context.user_data[_DEFER_KEY] = sorted(ids)


def review_keyboard(token: str, candidate_count: int) -> InlineKeyboardMarkup:
    """callback_data: rv:{action}:{token} — action 0/1/s/l."""
    rows: list[list[InlineKeyboardButton]] = []
    pick_row: list[InlineKeyboardButton] = []
    for index in range(min(candidate_count, 2)):
        pick_row.append(
            InlineKeyboardButton(
                str(index + 1),
                callback_data=f"rv:{index}:{token}",
            )
        )
    if pick_row:
        rows.append(pick_row)
    rows.append(
        [
            InlineKeyboardButton("Пропуск", callback_data=f"rv:s:{token}"),
            InlineKeyboardButton("Позже", callback_data=f"rv:l:{token}"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _issue_token(context: ContextTypes.DEFAULT_TYPE, telegram_id: int, source_id: str) -> str:
    token = secrets.token_hex(4)
    store = user_store(context)
    store.put_review_token(token, telegram_id, source_id)
    return token


async def _send_card(
    *,
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    card: ReviewCard,
    edit: bool,
) -> None:
    token = _issue_token(context, telegram_id, card.source_id)
    text = review_card_text(
        title=card.title,
        artists=card.artists,
        candidates=list(card.candidates),
        open_remaining=card.open_remaining,
    )
    markup = review_keyboard(token, len(card.candidates))
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return

    telegram_id = telegram_user_id(update)
    origin = update.effective_message
    if telegram_id is None or origin is None:
        return

    if update.callback_query is not None:
        await update.callback_query.answer()

    data_root = telegram_user_data_root(context)
    try:
        card = peek_next_review(
            telegram_id,
            data_root=data_root,
            defer_ids=_defer_ids(context),
        )
    except BotReviewError as exc:
        await origin.reply_text(review_failed_text(str(exc)))
        return

    if card is None:
        # Если всё только в «Позже» — начинаем круг заново.
        if _defer_ids(context):
            _set_defer_ids(context, set())
            card = peek_next_review(telegram_id, data_root=data_root, defer_ids=set())
        if card is None:
            open_n = count_open_reviews(telegram_id, data_root=data_root)
            text = REVIEW_EMPTY if open_n == 0 else REVIEW_NEED_PLAN
            await origin.reply_text(text)
            return

    await _send_card(
        message=origin,
        context=context,
        telegram_id=telegram_id,
        card=card,
        edit=False,
    )


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_review(update, context)


async def on_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    chat = update.effective_chat
    if chat is None or chat.type != Chat.PRIVATE:
        return

    telegram_id = telegram_user_id(update)
    message = query.message
    if telegram_id is None or not isinstance(message, Message):
        await query.answer()
        return

    parts = query.data.split(":")
    # rv:{action}:{token}
    if len(parts) != 3 or parts[0] != "rv":
        await query.answer()
        return
    action_code, token = parts[1], parts[2]

    resolved = user_store(context).get_review_token(token)
    if resolved is None or resolved[0] != telegram_id:
        await query.answer(REVIEW_STALE, show_alert=True)
        return
    _, source_id = resolved

    data_root = telegram_user_data_root(context)

    if action_code == "l":
        # «Позже» — без decision, показать следующий.
        deferred = _defer_ids(context)
        deferred.add(source_id)
        _set_defer_ids(context, deferred)
        await query.answer("Отложено")
        card = peek_next_review(
            telegram_id,
            data_root=data_root,
            defer_ids=deferred,
        )
        if card is None:
            _set_defer_ids(context, set())
            card = peek_next_review(telegram_id, data_root=data_root, defer_ids=set())
        if card is None:
            await message.edit_text(REVIEW_EMPTY)
            return
        await _send_card(
            message=message,
            context=context,
            telegram_id=telegram_id,
            card=card,
            edit=True,
        )
        return

    try:
        if action_code == "s":
            result = decide_review(
                telegram_id,
                source_id,
                action="skip",
                data_root=data_root,
            )
            await query.answer("Пропущено")
            flash = None
        elif action_code in {"0", "1"}:
            result = decide_review(
                telegram_id,
                source_id,
                action="accept",
                candidate_index=int(action_code),
                data_root=data_root,
            )
            flash = review_accepted_flash(result.chosen_title)
            await query.answer(flash)
        else:
            await query.answer()
            return
    except BotReviewError as exc:
        await query.answer(str(exc)[:180], show_alert=True)
        return
    except Exception:
        logger.exception("review callback failed")
        await query.answer("Ошибка — попробуй /review", show_alert=True)
        return

    # После решения убираем из отложенных, если был.
    deferred = _defer_ids(context)
    if source_id in deferred:
        deferred.discard(source_id)
        _set_defer_ids(context, deferred)

    if result.open_remaining <= 0:
        await message.edit_text(review_done_text(accepted_hint=flash))
        user_store(context).clear_review_tokens(telegram_id)
        return

    card = peek_next_review(
        telegram_id,
        data_root=data_root,
        defer_ids=_defer_ids(context),
    )
    if card is None and _defer_ids(context):
        _set_defer_ids(context, set())
        card = peek_next_review(telegram_id, data_root=data_root, defer_ids=set())
    if card is None:
        await message.edit_text(review_done_text(accepted_hint=flash))
        return

    await _send_card(
        message=message,
        context=context,
        telegram_id=telegram_id,
        card=card,
        edit=True,
    )
