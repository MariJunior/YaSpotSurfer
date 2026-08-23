# Migrate liked tracks (A6)

Пишет в Spotify **только** `exact` и `high-confidence` из dry-run. `review` / `not-found` пропускаются.

Сверка: [Save Items](https://developer.spotify.com/documentation/web-api/reference/save-library-items), [Check Saved Items](https://developer.spotify.com/documentation/web-api/reference/check-library-contains). Dev Mode 2026: `PUT/GET /me/library`, `uris` query, не `/me/tracks`. По одному URI: `requests` кодирует запятую как `%2C`.

## Команда

Сначала dry-run на тот же `--limit`:

```bash
uv run yandex-spike migrate-dry-run --limit 20
uv run yandex-spike migrate --limit 20
uv run yandex-spike migrate --limit 20 --resume
```

Это **реальная запись лайков** в аккаунт. Повторный запуск: `GET /me/library/contains` → `already`, повторный PUT не нужен. `--resume` также пропускает id из `.data/migrate-state.json`.

Не гоняет всю библиотеку. Плейлисты, артисты, альбомы — следующий шаг (A7), не этот CLI.

## Отчёт

- `.data/migrate-report.json` — `saved` / `already` / `skipped`
- `.data/migrate-state.json` — `migration_id` + checkpoint
