""" /plan, /status и общий /cancel (jobs + ввод Яндекса). """

from __future__ import annotations

import asyncio
import logging
import time

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.plan import (
    PlanError,
    PlanQuotaExceededError,
    PlanResult,
    checkpoint_track_count,
    load_plan_summary,
    plan_liked_tracks,
)
from yandex_spike.telegram.copy import (
    CANCEL_NOTHING,
    JOB_CANCEL_REQUESTED,
    PLAN_ALREADY_RUNNING,
    PLAN_PROGRESS_PREFIX,
    PLAN_START,
    STATUS_IDLE,
    YANDEX_CONNECT_CANCELLED,
    plan_done_text,
    plan_failed_text,
    plan_quota_exceeded_text,
    status_busy_text,
    status_last_plan_text,
)
from yandex_spike.telegram.deps import telegram_user_data_root, telegram_user_id, user_store
from yandex_spike.telegram.jobs import (
    KIND_PLAN,
    end_job,
    get_job,
    request_cancel,
    try_begin_job,
)
from yandex_spike.telegram.yandex_flow import cancel_yandex_await


logger = logging.getLogger(__name__)

_PROGRESS_MIN_INTERVAL_SEC = 2.0
_HEARTBEAT_SEC = 90.0


async def start_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return

    telegram_id = telegram_user_id(update)
    origin = update.effective_message
    if telegram_id is None or origin is None:
        return

    if update.callback_query is not None:
        await update.callback_query.answer()

    job = try_begin_job(context, telegram_id, KIND_PLAN)
    if job is None:
        await origin.reply_text(PLAN_ALREADY_RUNNING)
        return

    status = await origin.reply_text(PLAN_START)
    try:
        result = await _run_plan_with_progress(context, telegram_id, status, job)
        await status.edit_text(
            plan_done_text(
                track_count=result.track_count,
                auto_count=result.auto_count,
                review_count=result.review_count,
                not_found_count=result.not_found_count,
                cancelled=result.cancelled,
                resumed=result.resumed,
            )
        )
    except PlanQuotaExceededError as exc:
        hours = max(1, (exc.retry_after_sec + 3599) // 3600)
        await status.edit_text(
            plan_quota_exceeded_text(done=exc.done, hours=hours)
        )
    except PlanError as exc:
        await status.edit_text(plan_failed_text(str(exc)))
    except Exception:
        logger.exception("plan failed for telegram_id=%s", telegram_id)
        await status.edit_text(
            plan_failed_text("Не удалось подобрать треки. Попробуй /plan ещё раз.")
        )
    finally:
        end_job(context, telegram_id)


async def _run_plan_with_progress(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    status: Message,
    job,
) -> PlanResult:
    loop = asyncio.get_running_loop()
    # (done, total) или строка-заметка про ожидание Spotify.
    queue: asyncio.Queue[tuple[int, int] | str | None] = asyncio.Queue()

    def on_progress(done: int, total: int) -> None:
        job.done = done
        job.total = total
        job.note = ""
        loop.call_soon_threadsafe(queue.put_nowait, (done, total))

    def on_wait(text: str) -> None:
        job.note = text
        loop.call_soon_threadsafe(queue.put_nowait, text)

    async def updater() -> None:
        last_edit_at = 0.0
        pending_counts: tuple[int, int] | None = None
        pending_note: str | None = None
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SEC)
            except asyncio.TimeoutError:
                if job.total > 0:
                    note = job.note or (
                        "⏳ Ещё работаю — Spotify иногда просит подождать."
                    )
                    try:
                        await status.edit_text(
                            f"{PLAN_PROGRESS_PREFIX}{job.done}/{job.total}\n"
                            f"{note}\n"
                            "→ /status · /cancel"
                        )
                    except Exception:
                        logger.debug("plan heartbeat edit skipped", exc_info=True)
                continue
            if item is None:
                break
            if isinstance(item, str):
                pending_note = item
            else:
                pending_counts = item
                pending_note = None
            while not queue.empty():
                nxt = queue.get_nowait()
                if nxt is None:
                    return
                if isinstance(nxt, str):
                    pending_note = nxt
                else:
                    pending_counts = nxt
                    pending_note = None
            now = time.monotonic()
            wait = _PROGRESS_MIN_INTERVAL_SEC - (now - last_edit_at)
            if wait > 0:
                await asyncio.sleep(wait)
            done = pending_counts[0] if pending_counts else job.done
            total = pending_counts[1] if pending_counts else job.total
            note = pending_note or job.note
            text = f"{PLAN_PROGRESS_PREFIX}{done}/{total}"
            if note:
                text = f"{text}\n{note}"
            try:
                await status.edit_text(text)
                last_edit_at = time.monotonic()
                pending_counts = None
                pending_note = None
            except Exception:
                logger.debug("plan progress edit skipped", exc_info=True)

    updater_task = asyncio.create_task(updater())
    try:
        return await asyncio.to_thread(
            plan_liked_tracks,
            user_store(context),
            telegram_id,
            data_root=telegram_user_data_root(context),
            resume=True,
            progress=on_progress,
            on_wait=on_wait,
            should_stop=job.cancel.is_set,
        )
    finally:
        await queue.put(None)
        await updater_task


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_plan(update, context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None:
        return

    job = get_job(context, telegram_id)
    data_root = telegram_user_data_root(context)
    if job is not None:
        checkpoint = 0
        if job.kind == KIND_PLAN:
            checkpoint = checkpoint_track_count(telegram_id, root=data_root)
        await message.reply_text(
            status_busy_text(
                label=job.label_ru,
                done=job.done,
                total=job.total,
                checkpoint=checkpoint,
                note=job.note,
            )
        )
        return

    summary = load_plan_summary(telegram_id, root=data_root)
    if summary:
        tz = summary.get("tz_counts") or {}
        await message.reply_text(
            status_last_plan_text(
                track_count=int(summary.get("track_count") or 0),
                auto_count=int(tz.get("exact") or 0),
                review_count=int(tz.get("review") or 0),
                not_found_count=int(tz.get("not_found") or 0),
                cancelled=bool(summary.get("cancelled")),
            )
        )
        return

    await message.reply_text(STATUS_IDLE)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сначала ввод URL Яндекса, иначе активный job."""
    message = update.effective_message
    telegram_id = telegram_user_id(update)
    if message is None or telegram_id is None:
        return

    if cancel_yandex_await(context):
        await message.reply_text(YANDEX_CONNECT_CANCELLED)
        return

    job = request_cancel(context, telegram_id)
    if job is not None:
        await message.reply_text(JOB_CANCEL_REQUESTED)
        return

    await message.reply_text(CANCEL_NOTHING)
