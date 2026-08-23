"""Порты application-слоя. Реализации — в infrastructure, не наоборот."""

from __future__ import annotations

from typing import Protocol

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
