# Yandex library inspector (A1)

Команда:

```bash
uv run yandex-spike inspect
```

Нужен `.data/yandex-token-music.json` (`auth-implicit`). Own-app token не использовать.

## Что делает

Только read:

- current user (`client.me` после `init()`);
- liked tracks (сначала short list, затем полные метаданные пачками по 100);
- список плейлистов (`users_playlists_list`);
- полные треки **двух самых маленьких** непустых плейлистов;
- liked artists / albums.

Write-запросов к Яндексу нет. Токены не логируются.

## Куда пишет

```text
.data/library-snapshot.json
.data/raw/account.json
.data/raw/liked-tracks-short.json
.data/raw/liked-tracks.json
.data/raw/playlists.json
.data/raw/playlist-<uid>-<kind>.json
.data/raw/liked-artists.json
.data/raw/liked-albums.json
```

## Известные ловушки библиотеки (уже обойдены)

- `client.me` — атрибут, не метод;
- список плейлистов — `users_playlists_list()`, не `users_playlists()`;
- `users_playlists(kind)` — один плейлист.

## ISRC

В `yandex-music==3.0.0` у модели `Track` **нет поля `isrc`**. Inspector ищет ключи `*isrc*` рекурсивно в `to_dict()`. Итог смотреть в `library-snapshot.json` → `isrc`.
