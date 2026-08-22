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

## Live 2026-08-22

| Поле | Значение |
|------|----------|
| liked tracks | 3996 |
| liked artists | 217 |
| liked albums | 203 |
| playlists | 51 |
| ISRC в лайках | **0 / 3996** |

`inspect` отработал до конца. Sample-плейлисты — два самых коротких (по 1 треку), как и задумано.

## ISRC

В `yandex-music==3.0.0` у модели `Track` **нет поля `isrc`**.

Проверка первого raw-трека (только ключи, без названий): в `to_dict()` нет `isrc`; `meta_data` = null; в JSON трека подстроки `isrc` нет. Album даёт `year` / `release_date` / `labels`, не ISRC.

Для matching v1 **нельзя опираться на ISRC как на первый приоритет** по данным Яндекса. База: normalized artist + title + duration + album/version.

Итог смотреть в `library-snapshot.json` → `isrc`.
