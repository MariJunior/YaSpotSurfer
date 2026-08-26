# YaSpotSurfer

Миграция **личной** музыкальной библиотеки из Яндекс Музыки в Spotify.

Целевой UX — **Telegram-бот**. CLI — отладочный контур того же пайплайна (`scan` → match → `review` → write). Бот: B5 — `/scan` (снимок библиотеки Яндекса), дальше `/plan`.

Правило matching: **неверный auto-match хуже пропуска**. LLM для обычного matching не используется.

Живую медиатеку (~4000 лайков, 51 плейлист) CLI **не** переносит целиком. Репетиция — песочница Spotify и `--limit`. Боевой переезд — этап бота.

## Как это устроено

```text
CLI (main) / Telegram  →  application (сценарии + порты)  →  domain (Track, matching)
                              ↑
                      infrastructure (Yandex / Spotify / SQLite бота / .data JSON)
```

- **domain** — сущности, нормализация, matching. Без HTTP.
- **application** — dry-run, review, запись; порты `MusicCatalogSearcher` и `LibraryWriter`.
- **infrastructure** — адаптеры Яндекса и Spotify, JSON в `.data/`.
- **CLI** — аргументы, файлы, печать. OAuth пока в `yandex.py` / `spotify.py`.
- **Telegram** — личка; `/connect_yandex`, `/connect_spotify`, `/scan`, `/logout`.

Spotify Dev Mode (2026) и неофициальный Music API Яндекса живут только в адаптерах.

## Возможности сейчас (CLI, этап A)

- Авторизация Яндекса (рабочий путь: implicit, official-like client) и Spotify OAuth
- Snapshot библиотеки Яндекса (лайки, плейлисты, исполнители, альбомы)
- Детерминированный matching: auto ≥ 0.90, review ≥ 0.70; remaster/live и жёсткий промах длительности не уходят в auto
- Dry-run с checkpoint, очередь `review` (`accept` / `skip`), `--resume`
- Запись лайков в песочницу `YaSpotSurfer sandbox` (медиатека — только с `--dest library`)
- Копии коротких плейлистов Яндекса в `YaSpotSurfer: <имя>`
- Ретраи сети: Spotify и Яндекс; raw-кэш плейлистов, если VPN роняет `api.music.yandex.net`

## В разработке

**Этап B — Telegram-бот (Python).** Публичная бета без пейволла, тот же пайплайн что CLI. Донаты — идея на потом. ТЗ: [docs/telegram-bot.md](docs/telegram-bot.md). Сейчас B5: `/scan` пишет snapshot в `.data/bot-users/<telegram_id>/`; дальше `/plan`.

CLI остаётся отладочным контуром. TypeScript на этом этапе нет.

## Бэклог

Этап **C** (не начинаем, пока нет бота):

- Postgres при нагрузке (SQLite у бота уже есть)
- web dashboard (единственное место, где может появиться TypeScript)
- smart playlist sync, дедуп, «мёртвые» плейлисты

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Telegram: бот у [@BotFather](https://t.me/BotFather); в `.env` — `TELEGRAM_BOT_TOKEN`, `TOKEN_ENCRYPTION_KEY`, для Spotify ещё `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`
- Spotify app в [Developer Dashboard](https://developer.spotify.com/dashboard), Redirect URI: `http://127.0.0.1:8766/callback`
- Spotify Premium у владельца app (Dev Mode 2026)
- VPN часто нужен для Spotify («unavailable in this country»). Тот же VPN может ронять Яндекс — CLI ретраит и умеет читать кэш `.data/raw/`

## Быстрый старт

```bash
uv sync
# токен Яндекса (redirect с #access_token= — только в локальный терминал)
uv run yandex-spike auth-implicit
uv run yandex-spike probe

# Spotify: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET в .env
uv run yandex-spike spotify-spike

uv run yandex-spike scan
uv run yandex-spike migrate-dry-run --limit 20
uv run yandex-spike review
uv run yandex-spike migrate --limit 20

# Telegram (B3): TELEGRAM_BOT_TOKEN, TOKEN_ENCRYPTION_KEY,
# SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (redirect http://127.0.0.1:8766/callback)
# Не запускай одновременно CLI spotify-spike — тот же порт callback.
uv run yaspotsurfer-bot
```

`scan` = `inspect`: `.data/library-snapshot.json`. Токены в лог не печатаются.

## Команды

### Авторизация и диагностика

| Команда | Что делает |
|---------|------------|
| `probe` | Проверяет Yandex tokens на `/account/status`, без секретов в логе |
| `auth-implicit` | Music-совместимый token через браузер |
| `auth-app` | Свой OAuth app: token есть, Music API даёт 403 |
| `probe-id` | Яндекс ID (`login.yandex.ru/info`), не Музыка |
| `spotify-spike` | OAuth Spotify, search, тестовый плейлист, cleanup |

### Библиотека и matching

| Команда | Что делает |
|---------|------------|
| `scan` / `inspect` | Snapshot лайков и плейлистов |
| `normalize-preview` | 20 лайков → нормализация (без API) |
| `match-preview` | Offline self-match по snapshot |
| `migrate-dry-run` / `migrate --dry-run` | Search + match, без записи |
| `review` | Очередь; `--accept` / `--skip` `yandex:ID` |

### Telegram-бот

| Команда | Что делает |
|---------|------------|
| `uv run yaspotsurfer-bot` | `/start`, `/help`, `/connect_yandex`, `/connect_spotify`, `/scan`, `/logout` |

### Запись в Spotify

| Команда | Что делает |
|---------|------------|
| `migrate` | Auto-match (+ accepted). По умолчанию песочница, не Liked Songs |
| `migrate-playlists` | Короткие плейлисты Яндекса → отдельные Spotify playlist |

Полезные флаги: `--limit`, `--resume`, `--dest playlist` / `--dest library`, `--playlist-id`, `--kind`, `--track-limit`, `--dry-run`.

Репетиция больше 20 (не вся библиотека):

```bash
uv run yandex-spike migrate --limit 50 --resume
uv run yandex-spike migrate-playlists --limit 3 --track-limit 10 --resume
```

Тесты:

```bash
uv run python -m unittest tests.test_normalization tests.test_matching tests.test_dry_run tests.test_migrate tests.test_playlists tests.test_review tests.test_yandex_network tests.test_telegram_copy tests.test_bot_users tests.test_spotify_connect tests.test_yandex_connect
```

`tests/__init__.py` обязателен: иначе unittest подхватывает `tests` из `yandex-music`.

## Куда смотреть дальше

| Тема | Документ |
|------|----------|
| Песочница vs лайки, VPN | [docs/a7-cli.md](docs/a7-cli.md) |
| Matching и пороги | [docs/matching.md](docs/matching.md) |
| Домен и слои | [docs/domain.md](docs/domain.md) |
| Telegram-бот (ТЗ) | [docs/telegram-bot.md](docs/telegram-bot.md) |
| Яндекс auth | [docs/yandex-auth.md](docs/yandex-auth.md) |
| Spotify spike | [docs/spotify-spike.md](docs/spotify-spike.md) |

## Секреты

Не коммитьте `.env` и `.data/` (токены, snapshot). Они в `.gitignore`. Redirect URL с `#access_token=` — только в локальный терминал, не в чат.
