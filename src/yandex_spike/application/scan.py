"""Скан библиотеки Яндекса для пользователя бота (per-user snapshot)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from yandex_spike.application.ports import UserAccountStore
from yandex_spike.infrastructure.yandex.library import LibraryCancelled, inspect_library
from yandex_spike.yandex import DATA_DIR

ProgressFn = Callable[[str], None]
StopFn = Callable[[], bool]

# Snapshot каждого telegram_id отдельно — не пересекается с CLI `.data/library-snapshot.json`.
BOT_USERS_DATA_DIR = DATA_DIR / "bot-users"


class ScanError(RuntimeError):
    """Понятная ошибка для чата: нет Яндекса, сеть, сбой inspect."""


@dataclass(frozen=True)
class ScanResult:
    telegram_id: int
    liked_tracks_count: int
    playlists_count: int
    liked_tracks_with_isrc: int
    snapshot_path: Path


def user_library_dir(telegram_id: int, *, root: Path | None = None) -> Path:
    base = root or BOT_USERS_DATA_DIR
    return base / str(telegram_id)


def user_snapshot_path(telegram_id: int, *, root: Path | None = None) -> Path:
    return user_library_dir(telegram_id, root=root) / "library-snapshot.json"


def clear_user_library_data(telegram_id: int, *, root: Path | None = None) -> None:
    """После /logout не оставляем чужой/старый snapshot на диске."""
    path = user_library_dir(telegram_id, root=root)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def scan_user_library(
    store: UserAccountStore,
    telegram_id: int,
    *,
    data_root: Path | None = None,
    progress: ProgressFn | None = None,
    should_stop: StopFn | None = None,
) -> ScanResult:
    """Читает токен из store, пишет snapshot в `.data/bot-users/<id>/`."""
    token = store.read_yandex_token(telegram_id)
    if not token:
        raise ScanError(
            "Сначала подключи Яндекс Музыку: /connect_yandex "
            "или кнопка «Подключить Яндекс»."
        )

    lib_dir = user_library_dir(telegram_id, root=data_root)
    raw_dir = lib_dir / "raw"
    snapshot_path = lib_dir / "library-snapshot.json"
    lib_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot = inspect_library(
            access_token=token,
            snapshot_path=snapshot_path,
            raw_dir=raw_dir,
            progress=progress,
            should_stop=should_stop,
        )
    except LibraryCancelled as exc:
        raise ScanError(
            "Сбор списка остановлен. Можно запустить /scan снова."
        ) from exc
    except ScanError:
        raise
    except Exception as exc:  # noqa: BLE001 — в чат без traceback
        message = str(exc)
        if "VPN" in message or "api.music.yandex.net" in message or "таймаут" in message.lower():
            raise ScanError(
                "Не удалось дочитать Яндекс Музыку. "
                "Проверь split tunnel (oauth.yandex.ru, music.yandex.ru, "
                "api.music.yandex.net мимо VPN) и нажми /scan ещё раз."
            ) from exc
        raise ScanError(
            "Не удалось собрать список треков. Попробуй /scan ещё раз чуть позже."
        ) from exc

    isrc = snapshot.get("isrc") or {}
    return ScanResult(
        telegram_id=telegram_id,
        liked_tracks_count=int(snapshot.get("liked_tracks_count") or 0),
        playlists_count=int(snapshot.get("playlists_count") or 0),
        liked_tracks_with_isrc=int(isrc.get("liked_tracks_with_isrc") or 0),
        snapshot_path=snapshot_path,
    )
