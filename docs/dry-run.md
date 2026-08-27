# Dry-run

`migrate --dry-run`: поиск в Spotify + matching, **без записи** в библиотеку.

Сверка search: [Search for Item](https://developer.spotify.com/documentation/web-api/reference/search). Dev Mode 2026: `limit` максимум 10. `market=from_token`.

## Лимиты Spotify (важно)

Два разных «429»:

| Сигнал | Что значит | Поведение YaSpotSurfer |
|--------|------------|-------------------------|
| Краткий 429 + `Retry-After` секунды/минуты | Обычный rate limit | Ждём и продолжаем тот же прогон (`persist_rate_limit`) |
| `reason: QUOTA_EXCEEDED` или `Retry-After` **на часы** | Дневная квота приложения в **Dev Mode** | Останавливаем прогон, сохраняем checkpoint, просим вернуться позже |

Эмпирика на нашем app (2026): за сутки обычно успевает **~650** `GET /search` до `QUOTA_EXCEEDED` (порядок величины, не контракт API). Extended Quota Mode у Spotify с мая 2025 фактически для организаций с большой аудиторией — для любительского бота **не рассчитываем**.

Практика для большой библиотеки (~4000 лайков):

1. `/plan` (бот) или `migrate-dry-run --resume` (CLI) пачками.
2. После квоты — пауза по `Retry-After` (часто ~12–20 ч).
3. Снова `/plan` / `--resume` — с сохранённого checkpoint.

«200» в логе long-polling бота — ответы **Telegram**, не Spotify.

## Команда

Нужны `.data/library-snapshot.json` и Spotify token (`spotify-spike` уже получал).

```bash
uv run yandex-spike migrate-dry-run
uv run yandex-spike migrate-dry-run --limit 20
uv run yandex-spike migrate-dry-run --limit 40 --resume
```

По умолчанию **20** лайков. Репетиция: `--limit 50`. Вся библиотека (~4000 search) — бот, **несколькими сутками** из‑за квоты Dev Mode.

Write-методов порт `MusicCatalogSearcher` не содержит. `wrote_to_spotify` в отчёте всегда `false`.

## Отчёт

- `.data/dry-run-report.json` — статусы и кандидаты
- `.data/dry-run-state.json` — checkpoint для `--resume`

Статусы движка: `exact` / `high-confidence` / `review` / `not-found`.

`tz_counts` как в ТЗ: `exact` = exact+high-confidence, `review`, `not_found`.

`migrate` пишет только `exact` и `high-confidence` (плюс `review --accept`). `review` без решения — очередь, не автозапись.
