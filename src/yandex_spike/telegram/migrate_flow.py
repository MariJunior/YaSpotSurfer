""" /migrate: выбор dest + запись + подтверждение «СОХРАНИТЬ» для Liked Songs. """

from __future__ import annotations

import asyncio
import logging
import time

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.bot_migrate import (
    MigrateError,
    MigrateResult,
    migrate_liked_from_plan,
)
from yandex_spike.telegram.copy import (
    MIGRATE_ALREADY_RUNNING,
    MIGRATE_CHOOSE,
    MIGRATE_LIBRARY_CONFIRM,
    MIGRATE_LIBRARY_CONFIRM_WORD,
    MIGRATE_PROGRESS_PREFIX,
    MIGRATE_START_LIBRARY,
    MIGRATE_START_SANDBOX,
    migrate_done_text,
    migrate_failed_text,
)
from yandex_spike.telegram.deps import telegram_user_data_root, telegram_user_id, user_store
from yandex_spike.telegram.jobs import KIND_MIGRATE, end_job, try_begin_job
from yandex_spike.telegram.keyboards import migrate_choose_keyboard


logger = logging.getLogger(__name__)

_AWAITING_LIBRARY = "awaiting_migrate_library_confirm"
_PROGRESS_MIN_INTERVAL_SEC = 2.0
_HEARTBEAT_SEC = 90.0


def is_awaiting_migrate_library(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get(_AWAITING_LIBRARY))


def cancel_migrate_library_await(context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not is_awaiting_migrate_library(context):
        return False
    context.user_data[_AWAITING_LIBRARY] = False
    return True


async def start_migrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать выбор: sandbox vs library."""
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return

    telegram_id = telegram_user_id(update)
    origin = update.effective_message
    if telegram_id is None or origin is None:
        return

    if update.callback_query is not None:
        await update.callback_query.answer()

    context.user_data[_AWAITING_LIBRARY] = False
    await origin.reply_text(MIGRATE_CHOOSE, reply_markup=migrate_choose_keyboard())


async def cmd_migrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_migrate(update, context)


async def start_migrate_sandbox(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await _run_migrate_job(update, context, dest="playlist")


async def start_migrate_library_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return
    origin = update.effective_message
    if origin is None:
        return
    if update.callback_query is not None:
        await update.callback_query.answer()
    context.user_data[_AWAITING_LIBRARY] = True
    await origin.reply_text(MIGRATE_LIBRARY_CONFIRM)


async def migrate_receive_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """True, если сообщение съели (подтверждение или отказ)."""
    if not is_awaiting_migrate_library(context):
        return False
    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None or not message.text:
        return False

    text = message.text.strip()
    if text != MIGRATE_LIBRARY_CONFIRM_WORD:
        await message.reply_text(
            f"Нужно ровно: {MIGRATE_LIBRARY_CONFIRM_WORD}\n"
            "→ или /cancel"
        )
        return True

    context.user_data[_AWAITING_LIBRARY] = False
    await _run_migrate_job(update, context, dest="library")
    return True


async def _run_migrate_job(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    dest: str,
) -> None:
    telegram_id = telegram_user_id(update)
    origin = update.effective_message
    if telegram_id is None or origin is None:
        return

    if update.callback_query is not None:
        await update.callback_query.answer()

    job = try_begin_job(context, telegram_id, KIND_MIGRATE)
    if job is None:
        await origin.reply_text(MIGRATE_ALREADY_RUNNING)
        return

    start_text = MIGRATE_START_LIBRARY if dest == "library" else MIGRATE_START_SANDBOX
    status = await origin.reply_text(start_text)
    try:
        result = await _run_with_progress(context, telegram_id, dest, status, job)
        await status.edit_text(
            migrate_done_text(
                dest=result.dest,
                track_count=result.track_count,
                saved=result.saved,
                already=result.already,
                skipped=result.skipped,
                cancelled=result.cancelled,
                playlist_name=result.playlist_name,
            )
        )
    except MigrateError as exc:
        await status.edit_text(migrate_failed_text(str(exc)))
    except Exception:
        logger.exception("migrate failed for telegram_id=%s dest=%s", telegram_id, dest)
        await status.edit_text(
            migrate_failed_text("Не удалось записать. Попробуй /migrate ещё раз.")
        )
    finally:
        end_job(context, telegram_id)


async def _run_with_progress(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    dest: str,
    status: Message,
    job,
) -> MigrateResult:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[int, int] | None] = asyncio.Queue()

    def on_progress(done: int, total: int) -> None:
        job.done = done
        job.total = total
        loop.call_soon_threadsafe(queue.put_nowait, (done, total))

    async def updater() -> None:
        last_edit_at = 0.0
        pending: tuple[int, int] | None = None
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SEC)
            except asyncio.TimeoutError:
                if job.total > 0:
                    try:
                        await status.edit_text(
                            f"{MIGRATE_PROGRESS_PREFIX}{job.done}/{job.total}\n"
                            "⏳ Ещё пишу…\n"
                            "→ /status · /cancel"
                        )
                    except Exception:
                        logger.debug("migrate heartbeat skipped", exc_info=True)
                continue
            if item is None:
                break
            pending = item
            while not queue.empty():
                nxt = queue.get_nowait()
                if nxt is None:
                    return
                pending = nxt
            now = time.monotonic()
            wait = _PROGRESS_MIN_INTERVAL_SEC - (now - last_edit_at)
            if wait > 0:
                await asyncio.sleep(wait)
            done, total = pending
            try:
                await status.edit_text(f"{MIGRATE_PROGRESS_PREFIX}{done}/{total}")
                last_edit_at = time.monotonic()
                pending = None
            except Exception:
                logger.debug("migrate progress skipped", exc_info=True)

    updater_task = asyncio.create_task(updater())
    try:
        return await asyncio.to_thread(
            migrate_liked_from_plan,
            user_store(context),
            telegram_id,
            dest=dest,  # type: ignore[arg-type]
            data_root=telegram_user_data_root(context),
            resume=True,
            progress=on_progress,
            should_stop=job.cancel.is_set,
        )
    finally:
        await queue.put(None)
        await updater_task
