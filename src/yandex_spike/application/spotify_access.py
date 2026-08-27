"""Свежий Spotify access token для пользователя бота (refresh → SQLite)."""

from __future__ import annotations

from yandex_spike.application.ports import UserAccountStore
from yandex_spike.spotify import _refresh_access_token


class SpotifyAccessError(RuntimeError):
    """Нет токена или refresh не удался — в чат без traceback."""


def resolve_spotify_access(store: UserAccountStore, telegram_id: int) -> str:
    """Обновляет access через refresh_token, если есть; иначе отдаёт сохранённый."""
    access, refresh = store.read_spotify_tokens(telegram_id)
    if not access and not refresh:
        raise SpotifyAccessError(
            "Сначала подключи Spotify: /connect_spotify "
            "или кнопка «Подключить Spotify»."
        )

    account = store.get(telegram_id)
    display_name = account.spotify_display_name if account.spotify_connected else None

    if refresh:
        try:
            data = _refresh_access_token(refresh)
            new_access = str(data["access_token"])
            new_refresh = str(data.get("refresh_token") or refresh)
            store.save_spotify_tokens(
                telegram_id,
                new_access,
                new_refresh,
                display_name,
            )
            return new_access
        except Exception as exc:
            if access:
                # Старый access ещё может жить — пробуем им.
                return access
            raise SpotifyAccessError(
                "Сессия Spotify истекла. Подключи аккаунт снова: /connect_spotify"
            ) from exc

    assert access is not None
    return access
