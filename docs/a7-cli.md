# A7 CLI и как тестировать, не ломая медиатеку

## TypeScript — на каком этапе?

**Ни на A, ни на B.** Бот (этап B) тоже Python: те же use cases, что CLI. TypeScript из черновика ТЗ §7 («в перспективе») не планируем, пока не появится отдельный web dashboard в **C**. Переписывать matching на TS не нужно.

## Где живая медиатека, где песочница

20 лайков уже в Spotify — это смоук A6, не финальный переезд.

| Этап | Куда пишем | Зачем |
|------|------------|--------|
| A7 сейчас | плейлист `YaSpotSurfer sandbox` (`--dest playlist`) | гонять matching, review, resume |
| A7 явно | `--dest library` | только если снова нужны лайки |
| B бот | твоя реальная медиатека | окончательная синхронизация |

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
```

`scan` = `inspect` (snapshot). `migrate` без `--dest` пишет в **песочницу**, не в Liked Songs.

Плейлисты Яндекса → отдельные Spotify playlist — следующий кусок A7. Сейчас песочница принимает те же 20 auto-match лайков.

## Как проверить A7

1. `migrate --limit 20` — в Spotify появится (или дополнится) `YaSpotSurfer sandbox`.
   Если create даёт 403 «unavailable in this country»: создай плейлист вручную в приложении
   (то же имя) или `migrate --playlist-id <id>`. Лайки при этом не пишутся.
2. Повтор `--resume` → `already`.
3. `review` — очередь; accept/skip меняют dry-run-state, следующий migrate уважает решение.
4. Песочницу можно удалить руками. Лайки A6 не откатываем автоматически.
