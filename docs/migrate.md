# Migrate liked tracks

Пишет в Spotify **только** `exact` и `high-confidence` из dry-run, плюс `review` с `decision=accept`. `skip` / без решения / `not-found` — `skipped`.

Сверка: [Save Items](https://developer.spotify.com/documentation/web-api/reference/save-library-items), [Check Saved Items](https://developer.spotify.com/documentation/web-api/reference/check-library-contains). Dev Mode 2026: `PUT/GET /me/library`, `uris` query. По одному URI.

## CLI

```bash
uv run yandex-spike migrate-dry-run --resume
uv run yandex-spike migrate --resume
uv run yandex-spike migrate --dest library --resume
```

По умолчанию пишется **вся** коллекция лайков из snapshot в плейлист `YaSpotSurfer sandbox`.  
«Любимое»: `--dest library`. Репетиция: `--limit 50`.

Повтор: contains / уже в плейлисте → `already`. Checkpoint: `.data/migrate-state-{dest}.json`.

Если во время добора search сработала квота — dry-run-state сохраняется; продолжай `migrate-dry-run --resume`, потом снова `migrate --resume`.

## Telegram-бот (`/migrate`)

1. Нужен `/plan` (dry-run-state). **Новых search нет** — не жжём квоту повторно.
2. Выбор: проверочный плейлист или «Любимое» (слово `СОХРАНИТЬ`).
3. Checkpoint: `.data/bot-users/<id>/migrate-state-{playlist|library}.json`.

## Отчёт

- CLI: `.data/migrate-report-{dest}.json` — `saved` / `already` / `skipped`
- CLI: `.data/migrate-state-{dest}.json` — `migration_id` + checkpoint
- Бот: те же имена в каталоге пользователя
