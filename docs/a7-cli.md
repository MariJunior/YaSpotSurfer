# CLI и как тестировать, не ломая медиатеку

## TypeScript — на каком этапе?

**Ни на A, ни на B.** Бот (этап B) тоже Python: те же use cases, что CLI. TypeScript из черновика ТЗ §7 («в перспективе») не планируем, пока не появится отдельный web dashboard в **C**. Переписывать matching на TS не нужно.

## Где живая медиатека, где песочница

20 лайков уже в Spotify — ранний смоук записи, не финальный переезд.

| Этап | Куда пишем | Зачем |
|------|------------|--------|
| CLI, лайки | плейлист `YaSpotSurfer sandbox` (`--dest playlist`) | matching, review, resume |
| CLI, плейлисты | `YaSpotSurfer: <имя Яндекса>` (`migrate-playlists`) | копия короткого плейлиста, не лайки |
| CLI явно | `--dest library` | только если снова нужны лайки |
| Бот | реальная медиатека | окончательная синхронизация |

Всю библиотеку (~4000 лайков, 51 плейлист) **не** гоняем в CLI как «боевой переезд». CLI должен уметь тот же пайплайн, что бот, на маленьком `--limit`.

## Команды

```bash
uv run yandex-spike scan
uv run yandex-spike migrate-dry-run --limit 20
uv run yandex-spike review
uv run yandex-spike review --accept yandex:152459181
uv run yandex-spike review --skip yandex:SOME_ID
uv run yandex-spike migrate --limit 20
uv run yandex-spike migrate --limit 20 --playlist-id PLAYLIST_ID
uv run yandex-spike migrate --limit 20 --dest library
uv run yandex-spike migrate --dry-run --limit 50
uv run yandex-spike migrate --limit 50
uv run yandex-spike migrate-playlists --limit 1
uv run yandex-spike migrate-playlists --kind 1063 --track-limit 10
uv run yandex-spike migrate-playlists --limit 3 --dry-run
```

`scan` = `inspect` (snapshot). `migrate` без `--dest` пишет в **песочницу**, не в Liked Songs. `migrate --dry-run` = `migrate-dry-run`. Если dry-run-state ещё нет на этот `--limit`, `migrate` сам доищет недостающие треки.

`migrate-playlists` берёт самые короткие непустые плейлисты Яндекса (или один `--kind` из snapshot) и пишет каждый в **свой** Spotify playlist `YaSpotSurfer: <имя>`. Лайки не трогает. `--limit` здесь — число плейлистов, `--track-limit` (по умолчанию 10) режет гигантов. `--dry-run` только search. Отчёт `.data/migrate-report-playlists.json` **мержит** по kind, не затирает прошлые плейлисты.

Matching кэшируется в `.data/dry-run-state.json`. Смена auto-порога пересчитывает status в кэше (например 0.905 → auto). `review` увидит оставшиеся спорные.

Репетиция больше 20, не вся медиатека:

```bash
uv run yandex-spike migrate-dry-run --limit 50 --resume
uv run yandex-spike review
uv run yandex-spike migrate --limit 50 --resume
uv run yandex-spike migrate-playlists --limit 3 --track-limit 10
```

Если create даёт 403 «unavailable in this country» — VPN (после Грузии Spotify с российского IP часто так отвечает) или создай плейлист руками с тем же именем.

VPN при этом может ронять **Яндекс** (`TimedOutError`, 5с по умолчанию). CLI ретраит, ждёт 20с, и если плейлист уже в `.data/raw/playlist-*-{kind}.json` — не ходит в Яндекс повторно. Один упавший плейлист не валит всю пачку `--limit 3`.

## Как проверить A7

1. `migrate --limit 20` — в Spotify появится (или дополнится) `YaSpotSurfer sandbox`.
   Если create даёт 403 «unavailable in this country»: создай плейлист вручную в приложении
   (то же имя) или `migrate --playlist-id <id>`. Лайки при этом не пишутся.
2. Повтор `--resume` → `already`.
3. `review` — очередь; accept/skip меняют dry-run-state, следующий migrate уважает решение.
4. `migrate-playlists --limit 1` — в Spotify появится `YaSpotSurfer: <имя самого короткого>`.
   Повтор с `--resume` → `already`. Песочницу плейлиста можно удалить руками.
5. Репетиция: `migrate --limit 50` в песочницу лайков (не `--dest library`). Не 3996 и не все 51.
6. Песочницу лайков (`YaSpotSurfer sandbox`) тоже можно удалить руками. Ранние тестовые лайки в медиатеке автоматически не откатываем.
