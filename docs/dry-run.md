# Dry-run (A5)

`migrate --dry-run` из ТЗ: поиск в Spotify + matching, **без записи** в библиотеку.

Сверка search: [Search for Item](https://developer.spotify.com/documentation/web-api/reference/search). Dev Mode 2026: `limit` максимум 10. `market=from_token`. 429 ретраим по `Retry-After`.

## Команда

Нужны `.data/library-snapshot.json` и Spotify token (`spotify-spike` уже получал).

```bash
uv run yandex-spike migrate-dry-run
uv run yandex-spike migrate-dry-run --limit 20
uv run yandex-spike migrate-dry-run --limit 40 --resume
```

По умолчанию **20** лайков. Репетиция A7: `--limit 50`. Вся библиотека (~4000 search) — не CLI, а бот (B).

Write-методов порт `MusicCatalogSearcher` не содержит. `wrote_to_spotify` в отчёте всегда `false`.

## Отчёт

- `.data/dry-run-report.json` — статусы и кандидаты
- `.data/dry-run-state.json` — checkpoint для `--resume`

Статусы движка: `exact` / `high-confidence` / `review` / `not-found`.

`tz_counts` как в ТЗ A5: `exact` = exact+high-confidence, `review`, `not_found`.

A6 будет писать только `exact` и `high-confidence`. `review` — очередь, не автозапись.
