""" /playlists: копирование коротких плейлистов Яндекса в Spotify. """

from __future__ import annotations

import asyncio
import logging

from telegram import Chat, Message, Update
from telegram.ext import ContextTypes

from yandex_spike.application.bot_playlists import (
    DEFAULT_PLAYLIST_LIMIT,
    DEFAULT_TRACK_LIMIT,
    PlaylistsError,
    PlaylistsResult,
    migrate_playlists_for_user,
)
from yandex_spike.telegram.copy import (
    PLAYLISTS_ALREADY_RUNNING,
    PLAYLISTS_START,
    playlists_done_text,
    playlists_failed_text,
)
from yandex_spike.telegram.deps import telegram_user_data_root, telegram_user_id, user_store
from yandex_spike.telegram.jobs import KIND_PLAYLISTS, end_job, try_begin_job


logger = logging.getLogger(__name__)


async def start_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is not None and chat.type != Chat.PRIVATE:
        return

    telegram_id = telegram_user_id(update)
    origin = update.effective_message
    if telegram_id is None or origin is None:
        return

    if update.callback_query is not None:
        await update.callback_query.answer()

    job = try_begin_job(context, telegram_id, KIND_PLAYLISTS)
    if job is None:
        await origin.reply_text(PLAYLISTS_ALREADY_RUNNING)
        return

    status = await origin.reply_text(PLAYLISTS_START)
    try:
        result = await _run_with_notes(context, telegram_id, status, job)
        await status.edit_text(
            playlists_done_text(
                playlist_count=result.playlist_count,
                entries=result.entries,
                cancelled=result.cancelled,
            )
        )
    except PlaylistsError as exc:
        await status.edit_text(playlists_failed_text(str(exc)))
    except Exception:
        logger.exception("playlists failed for telegram_id=%s", telegram_id)
        await status.edit_text(
            playlists_failed_text(
                "Не удалось скопировать плейлисты. Попробуй /playlists ещё раз."
            )
        )
    finally:
        end_job(context, telegram_id)


async def cmd_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_playlists(update, context)


async def _run_with_notes(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    status: Message,
    job,
) -> PlaylistsResult:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_progress(note: str) -> None:
        job.note = note
        loop.call_soon_threadsafe(queue.put_nowait, note)

    async def updater() -> None:
        while True:
            note = await queue.get()
            if note is None:
                break
            try:
                await status.edit_text(f"{PLAYLISTS_START}\n\n{note}\n→ /status · /cancel")
            except Exception:
                logger.debug("playlists progress skipped", exc_info=True)

    updater_task = asyncio.create_task(updater())
    try:
        return await asyncio.to_thread(
            migrate_playlists_for_user,
            user_store(context),
            telegram_id,
            data_root=telegram_user_data_root(context),
            limit=DEFAULT_PLAYLIST_LIMIT,
            track_limit=DEFAULT_TRACK_LIMIT,
            resume=True,
            progress=on_progress,
            should_stop=job.cancel.is_set,
        )
    finally:
        await queue.put(None)
        await updater_task
