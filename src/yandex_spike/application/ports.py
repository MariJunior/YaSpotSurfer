"""Порты application-слоя. Реализации — в infrastructure, не наоборот."""

from __future__ import annotations

from typing import Protocol

from yandex_spike.domain.bot_user import BotUser
from yandex_spike.domain.entities import Track


class MusicCatalogSearcher(Protocol):
    """Поиск кандидатов. Dry-run не должен видеть write-методы."""

    def search_track(self, track: Track) -> list[Track]:
        ...


class LibraryWriter(Protocol):
    """Запись одного URI: Liked Songs или items плейлиста — один контракт."""

    def contains(self, uri: str) -> bool:
        ...

    def save(self, uri: str) -> None:
        ...


# Имена, которыми пользуется CLI: не переименовывать импорты в dry-run/migrate.
MusicCatalogSearcher = MusicCatalogSearcher
LibraryWriter = LibraryWriter


class UserAccountStore(Protocol):
    """Один человек = telegram_id. Секреты шифрует реализация, не хендлер."""

    def get(self, telegram_id: int) -> BotUser:
        """Нет строки в БД — «ничего не подключено», без создания записи."""
        ...

    def ensure(self, telegram_id: int) -> BotUser:
        """Создаёт пустую запись при первом /start."""
        ...

    def save_yandex_token(self, telegram_id: int, access_token: str) -> None:
        """Для B4; в B2 нужен, чтобы проверить шифрование тестом."""
        ...

    def save_spotify_tokens(
        self,
        telegram_id: int,
        access_token: str,
        refresh_token: str | None,
        display_name: str | None,
    ) -> None:
        """Для B3; хендлеры B2 это не вызывают."""
        ...

    def logout(self, telegram_id: int) -> bool:
        """Стирает ключи и имя Spotify. True, если что-то было сохранено."""
        ...

    def read_yandex_token(self, telegram_id: int) -> str | None:
        """Plaintext только внутри процесса; в логи не писать."""
        ...

    def read_spotify_tokens(self, telegram_id: int) -> tuple[str | None, str | None]:
        """(access, refresh). None, если нет или blob не читается."""
        ...
