"""Один активный тяжёлый job на пользователя (scan / plan)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from telegram.ext import ContextTypes

_JOBS_KEY = "active_jobs"

KIND_SCAN = "scan"
KIND_PLAN = "plan"
KIND_MIGRATE = "migrate"
KIND_PLAYLISTS = "playlists"


@dataclass
class ActiveJob:
    kind: str
    cancel: threading.Event = field(default_factory=threading.Event)
    done: int = 0
    total: int = 0
    # Текст про ожидание Spotify (rate limit) — для /status и heartbeat.
    note: str = ""

    @property
    def label_ru(self) -> str:
        if self.kind == KIND_SCAN:
            return "собираю список треков из Яндекса"
        if self.kind == KIND_PLAN:
            return "подбираю треки в Spotify"
        if self.kind == KIND_MIGRATE:
            return "записываю треки в Spotify"
        if self.kind == KIND_PLAYLISTS:
            return "копирую плейлисты в Spotify"
        return self.kind


def _jobs_map(context: ContextTypes.DEFAULT_TYPE) -> dict[int, ActiveJob]:
    jobs = context.application.bot_data.get(_JOBS_KEY)
    if jobs is None:
        jobs = {}
        context.application.bot_data[_JOBS_KEY] = jobs
    return jobs


def get_job(context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> ActiveJob | None:
    return _jobs_map(context).get(telegram_id)


def try_begin_job(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    kind: str,
) -> ActiveJob | None:
    """None — уже есть другой job у этого пользователя."""
    jobs = _jobs_map(context)
    if telegram_id in jobs:
        return None
    job = ActiveJob(kind=kind)
    jobs[telegram_id] = job
    return job


def end_job(context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> None:
    _jobs_map(context).pop(telegram_id, None)


def request_cancel(context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> ActiveJob | None:
    job = get_job(context, telegram_id)
    if job is None:
        return None
    job.cancel.set()
    return job
