# Dry-run

`migrate --dry-run` / `migrate-dry-run`: поиск в Spotify + matching, **без записи** в библиотеку.

Сверка search: [Search for Item](https://developer.spotify.com/documentation/web-api/reference/search). Dev Mode 2026: `limit` максимум 10. `market=from_token`.

## Лимиты Spotify (важно)

Два разных «429»:

| Сигнал | Что значит | Поведение YaSpotSurfer |
|--------|------------|-------------------------|
| Краткий 429 + `Retry-After` секунды/минуты | Обычный rate limit | Ждём и продолжаем (`persist_rate_limit`) |
| `reason: QUOTA_EXCEEDED` или `Retry-After` **на часы** | Дневная квота приложения в **Dev Mode** | Стоп, checkpoint, подсказка `--resume` / снова `/plan` |

Эмпирика (2026): ~**650** `GET /search`/сутки до `QUOTA_EXCEEDED`. Extended Quota для хобби почти недоступна.

Практика для большой библиотеки:

1. CLI: `migrate-dry-run --resume` или бот: `/plan` пачками.
2. Пауза по `Retry-After` (часто ~12–20 ч).
3. Снова с `--resume` / `/plan`.

«200» в логе long-polling бота — ответы **Telegram**, не Spotify.

## Команда

Нужны `.data/library-snapshot.json` и Spotify token (`spotify-spike`).

```bash
# Вся коллекция лайков
uv run yandex-spike migrate-dry-run --resume

# Кусок для репетиции
uv run yandex-spike migrate-dry-run --limit 50 --resume
```

По умолчанию — **все** лайки из snapshot. Write-методов у порта `MusicCatalogSearcher` нет. `wrote_to_spotify` в отчёте всегда `false`.

## Отчёт

- `.data/dry-run-report.json` — статусы и кандидаты
- `.data/dry-run-state.json` — checkpoint для `--resume`

Статусы: `exact` / `high-confidence` / `review` / `not-found`.

`tz_counts`: `exact` = exact+high-confidence, `review`, `not_found`.

`migrate` пишет только `exact` и `high-confidence` (плюс `review --accept`).
