from __future__ import annotations

from typing import Protocol

from yandex_spike.domain.entities import ArtistRef, Playlist, Track


class MusicLibraryReader(Protocol):
    def get_liked_tracks(self) -> list[Track]:
        ...

    def get_playlists(self) -> list[Playlist]:
        ...

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        ...

    def get_liked_artists(self) -> list[ArtistRef]:
        ...


class MusicCatalogWriter(Protocol):
    def search_track(self, track: Track) -> list[Track]:
        ...

    def save_liked_tracks(self, tracks: list[Track]) -> None:
        ...

    def create_playlist(self, title: str, tracks: list[Track]) -> Playlist:
        ...


class MigrationStore(Protocol):
    def save_tracks(self, tracks: list[Track]) -> None:
        ...

    def load_tracks(self) -> list[Track]:
        ...
