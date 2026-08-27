""" /scan: inspect Яндекса в фоне, прогресс правкой одного сообщения. """

from __future__ import annotations

import asyncio
import logging
import time

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.scan import ScanError, ScanResult, scan_user_library
from yandex_spike.telegram.copy import (
    SCAN_ALREADY_RUNNING,
    SCAN_NEED_YANDEX,
    SCAN_PROGRESS_PREFIX,
    SCAN_START,
    scan_done_text,
    scan_failed_text,
)
from yandex_spike.telegram.deps import telegram_user_data_root, telegram_user_id, user_store
from yandex_spike.telegram.jobs import KIND_SCAN, end_job, try_begin_job
from yandex_spike.telegram.keyboards import after_scan_keyboard

logger = logging.getLogger(__name__)

_PROGRESS_MIN_INTERVAL_SEC = 1.5


async def start_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Точка входа: команда /scan или кнопка меню."""
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return

    telegram_id = telegram_user_id(update)
    origin = update.effective_message
    if telegram_id is None or origin is None:
        return

    if update.callback_query is not None:
        await update.callback_query.answer()

    job = try_begin_job(context, telegram_id, KIND_SCAN)
    if job is None:
        await origin.reply_text(SCAN_ALREADY_RUNNING)
        return

    token = user_store(context).read_yandex_token(telegram_id)
    if not token:
        end_job(context, telegram_id)
        await origin.reply_text(SCAN_NEED_YANDEX)
        return

    status = await origin.reply_text(SCAN_START)
    try:
        result = await _run_scan_with_progress(context, telegram_id, status, job.cancel)
        await status.edit_text(
            scan_done_text(
                liked_tracks=result.liked_tracks_count,
                playlists=result.playlists_count,
                liked_with_isrc=result.liked_tracks_with_isrc,
            ),
            reply_markup=after_scan_keyboard(),
        )
    except ScanError as exc:
        await status.edit_text(scan_failed_text(str(exc)))
    except Exception:
        logger.exception("scan failed for telegram_id=%s", telegram_id)
        await status.edit_text(
            scan_failed_text(
                "Не удалось собрать список треков. Попробуй /scan ещё раз чуть позже."
            )
        )
    finally:
        end_job(context, telegram_id)


async def _run_scan_with_progress(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    status: Message,
    cancel_event,
) -> ScanResult:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_progress(text: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, f"{SCAN_PROGRESS_PREFIX}{text}")

    async def updater() -> None:
        last_edit_at = 0.0
        pending: str | None = None
        while True:
            item = await queue.get()
            if item is None:
                if pending is not None:
                    try:
                        await status.edit_text(pending)
                    except Exception:
                        logger.debug("final progress edit skipped", exc_info=True)
                break
            pending = item
            while not queue.empty():
                nxt = queue.get_nowait()
                if nxt is None:
                    try:
                        await status.edit_text(pending)
                    except Exception:
                        logger.debug("final progress edit skipped", exc_info=True)
                    return
                pending = nxt
            now = time.monotonic()
            wait = _PROGRESS_MIN_INTERVAL_SEC - (now - last_edit_at)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                await status.edit_text(pending)
                last_edit_at = time.monotonic()
                pending = None
            except Exception:
                logger.debug("progress edit skipped", exc_info=True)

    updater_task = asyncio.create_task(updater())
    try:
        return await asyncio.to_thread(
            scan_user_library,
            user_store(context),
            telegram_id,
            data_root=telegram_user_data_root(context),
            progress=on_progress,
            should_stop=cancel_event.is_set,
        )
    finally:
        await queue.put(None)
        await updater_task


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_scan(update, context)
