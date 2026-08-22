from __future__ import annotations

import json
from pathlib import Path

from .yandex import authenticate, get_library_snapshot


DATA_DIR = Path(".data")
SNAPSHOT_FILE = DATA_DIR / "library-snapshot.json"


def main() -> None:
    print("🎧 Yandex → Spotify migration spike")
    print("━" * 40)
    print()

    client = authenticate()

    print()
    print("📡 Получаю данные библиотеки...")
    print()

    snapshot = get_library_snapshot(client)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    SNAPSHOT_FILE.write_text(
        json.dumps(
            snapshot,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    account = snapshot["account"]

    print("👤 Аккаунт")
    print(f"   Login: {account['login']}")
    print(f"   Name:  {account['display_name']}")
    print()

    print("🎵 Библиотека")
    print(f"   ❤️ Любимых треков: {snapshot['liked_tracks_count']}")
    print(f"   📚 Плейлистов:      {snapshot['playlists_count']}")
    print()

    print("📚 Плейлисты")
    print()

    for playlist in snapshot["playlists"]:
        print(
            f"   • {playlist['title']} "
            f"— {playlist['track_count']} треков"
        )

    print()
    print(f"💾 Snapshot сохранён в {SNAPSHOT_FILE}")