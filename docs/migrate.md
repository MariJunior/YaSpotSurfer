# Migrate liked tracks

Пишет в Spotify **только** `exact` и `high-confidence` из dry-run, плюс `review` с `decision=accept`. `skip` / без решения / `not-found` — `skipped`.

Сверка: [Save Items](https://developer.spotify.com/documentation/web-api/reference/save-library-items), [Check Saved Items](https://developer.spotify.com/documentation/web-api/reference/check-library-contains). Dev Mode 2026: `PUT/GET /me/library`, `uris` query, не `/me/tracks`. По одному URI: `requests` кодирует запятую как `%2C`.

## CLI

Сначала dry-run на тот же `--limit`:

```bash
uv run yandex-spike migrate-dry-run --limit 20
uv run yandex-spike migrate --limit 20
uv run yandex-spike migrate --limit 20 --resume
```

С A7 `migrate` по умолчанию пишет в плейлист `YaSpotSurfer sandbox`. Лайки: `--dest library`.

Повтор: contains / треки уже в плейлисте → `already`. Checkpoint: `.data/migrate-state-{dest}.json`.

## Telegram-бот (`/migrate`)

1. Нужен готовый `/plan` (файл `dry-run-state` у пользователя). **Новых search нет** — не жжём дневную квоту Dev Mode.
2. Выбор:
   - **Проверочный плейлист** `YaSpotSurfer sandbox` — сразу.
   - **«Любимое»** — только после сообщения ровно `СОХРАНИТЬ` (отмена `/cancel`).
3. Прогресс + `/cancel` с checkpoint в `.data/bot-users/<id>/migrate-state-{playlist|library}.json`.

## Отчёт

- CLI: `.data/migrate-report-{dest}.json` — `saved` / `already` / `skipped`
- CLI: `.data/migrate-state-{dest}.json` — `migration_id` + checkpoint
- Бот: те же имена файлов в каталоге пользователя
