# YaSpotSurfer

Перенос **личной** музыкальной библиотеки из **Яндекс Музыки** в **Spotify**.

Два равноправных контура одного пайплайна:

| Контур | Для кого |
|--------|----------|
| **CLI** (`yandex-spike`) | Форк, свой компьютер, полный перенос; удобный **TUI** в терминале |
| **Telegram-бот** (`yaspotsurfer-bot`) | Тот же пайплайн в личке, удобный UX |

> **Правило matching:** неверный auto-match хуже пропуска.  
> Нейросети для обычного matching **не** используются.

---

## Что умеет

- Подключение Яндекс Музыки (неофициальный Music-совместимый token) и Spotify OAuth
- Снимок библиотеки: лайки, плейлисты, исполнители, альбомы
- Детерминированный matching: auto ≥ **0.90**, review ≥ **0.70** (remaster/live и сильный промах длительности не уходят в auto)
- Dry-run с checkpoint и `--resume` (в т.ч. после дневной квоты Spotify)
- Ручной review спорных (`accept` / `skip`)
- Запись лайков: по умолчанию в плейлист-песочницу `YaSpotSurfer sandbox`; в «Любимое» — только явно (`--dest library` / в боте слово `СОХРАНИТЬ`)
- Копии плейлистов Яндекса → отдельные Spotify playlist `YaSpotSurfer: <имя>`
- Ретраи сети; raw-кэш плейлистов Яндекса, если VPN роняет API
- **TUI в терминале** (Textual): сайдбар команд, статусы Yandex/Spotify, прогресс dry-run/квоты/записи, лог; OAuth Яндекса — через видимое поле ввода URL

---

## Ограничения (важно прочитать)

| Ограничение | Что это значит на практике |
|-------------|----------------------------|
| Нет official Yandex library API | Implicit OAuth «как у клиента Музыки»; перенос неофициальный, на свой страх и риск |
| Spotify **Dev Mode** | Свой app в Dashboard; чужой Spotify часто не пустят без Extended Quota |
| Дневная квота search | Эмпирика ~**650** `GET /search` в сутки → `QUOTA_EXCEEDED` на много часов. Большая библиотека = несколько дней + `--resume` / снова `/plan` |
| Search `limit` ≤ 10 | Медленный подбор; прогресс и checkpoint обязательны |
| VPN | Spotify из РФ часто недоступен без VPN; тот же VPN может ронять Яндекс → split tunnel для `oauth.yandex.ru`, `music.yandex.ru`, `api.music.yandex.net` |
| Premium | Запись в библиотеку Spotify может требовать Premium у владельца app |

Подробнее: [docs/dry-run.md](docs/dry-run.md), [docs/yandex-public-api.md](docs/yandex-public-api.md).

---

## Требования

- Python **3.12**
- [uv](https://docs.astral.sh/uv/)
- Аккаунт Яндекса с Музыкой
- Spotify app в [Developer Dashboard](https://developer.spotify.com/dashboard)  
  Redirect URI (по умолчанию): `http://127.0.0.1:8766/callback`
- В `.env`: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`  
  Для бота ещё: `TELEGRAM_BOT_TOKEN`, `TOKEN_ENCRYPTION_KEY` (см. `.env.example`)

```bash
uv sync
cp .env.example .env   # и заполни ключи
```

---

## Вариант A — CLI (полный перенос)

Подходит, если форкаешь репозиторий и гоняешь всё локально.

### Навигация и TUI

Без аргументов в обычном терминале открывается **интерактивный TUI** на [Textual](https://textual.textualize.io/):

- левый бар — команды текущего этапа (недоступные помечены);
- сверху — статусы **Yandex / Spotify / Snapshot** (OK или нет) и подсказка этапа;
- прогресс-бары dry-run, ориентира квоты search (~650/сутки), review и записи;
- лог выполнения справа; для Яндекс OAuth — **модалка с видимым Input** (не ввод вслепую).

```bash
uv sync                          # подтянет textual
uv run yandex-spike              # TUI (нужен интерактивный терминал)
uv run yandex-spike menu         # то же явно
uv run yandex-spike help         # полный список команд (/help тоже ок)
uv run yandex-spike menu-classic # простое меню по номерам, без Textual
uv run yandex-spike -h           # флаги argparse
```

Горячие клавиши в TUI: `q` — выход, `r` — обновить статусы, `?` — справка.

Долгие шаги из TUI идут с разумными дефолтами (`--resume`, migrate → песочница, без `--limit`). Запись в «Любимое» и точечный review — обычными командами CLI.

### 1. Авторизация

```bash
# Яндекс: откроется браузер → скопируй redirect с #access_token= в терминал
uv run yandex-spike auth-implicit
uv run yandex-spike probe

# Spotify: OAuth + короткий smoke (тот же порт callback, что у бота)
uv run yandex-spike spotify-spike
```

### 2. Снимок библиотеки

```bash
uv run yandex-spike scan
# → .data/library-snapshot.json
```

### 3. Подбор в Spotify (без записи)

```bash
# Вся коллекция лайков. При квоте — стоп + checkpoint
uv run yandex-spike migrate-dry-run --resume

# Репетиция на куске (опционально):
uv run yandex-spike migrate-dry-run --limit 50 --resume
```

### 4. Спорные

```bash
uv run yandex-spike review
uv run yandex-spike review --accept yandex:TRACK_ID
uv run yandex-spike review --skip yandex:TRACK_ID
```

### 5. Запись лайков

```bash
# Песочница (по умолчанию) — лайки Spotify не трогает
uv run yandex-spike migrate --resume

# Настоящие «Любимые» — только когда песочница проверена
uv run yandex-spike migrate --dest library --resume
```

### 6. Плейлисты

```bash
# Все непустые плейлисты → YaSpotSurfer: <имя> (сначала короткие)
uv run yandex-spike migrate-playlists --resume

# Осторожный прогон:
uv run yandex-spike migrate-playlists --limit 3 --track-limit 20 --resume
uv run yandex-spike migrate-playlists --kind 1063
```

Токены и snapshot не печатаются в лог. Секреты — только в `.env` / `.data/` (в `.gitignore`).

---

## Вариант B — Telegram-бот

Тот же пайплайн в личке. Спека: [docs/telegram-bot.md](docs/telegram-bot.md).

```bash
# Не запускай одновременно CLI spotify-spike — тот же порт callback
uv run yaspotsurfer-bot
```

| Команда | Смысл |
|---------|--------|
| `/start` `/help` | Дисклеймер, меню, статус связей |
| `/connect_yandex` | Implicit URL из браузера |
| `/connect_spotify` | OAuth в браузере |
| `/scan` | Snapshot Яндекса |
| `/plan` | Dry-run лайков (пачками из‑за ~650/сутки) |
| `/review` | Спорные: кнопки 1 / 2 / Пропуск / Позже |
| `/migrate` | Песочница или «Любимое» (слово `СОХРАНИТЬ`) |
| `/playlists` | Короткий плейлист → `YaSpotSurfer: …` |
| `/status` `/cancel` `/logout` | Ход работы, остановка, стереть ключи |

---

## Архитектура

```text
CLI / Telegram  →  application (сценарии + порты)  →  domain (Track, matching)
                         ↑
                 infrastructure (Yandex / Spotify / SQLite / .data)
```

- **domain** — сущности, нормализация, matching (без HTTP)
- **application** — dry-run, review, write; порты `MusicCatalogSearcher`, `LibraryWriter`
- **infrastructure** — адаптеры API и хранилище
- **presentation** — CLI (`main.py`), Textual TUI (`cli_tui/`) и Telegram (`telegram/`)

---

## Команды CLI (шпаргалка)

### Авторизация и диагностика

| Команда | Что делает |
|---------|------------|
| `help` / `menu` | Справка и TUI-меню (Textual) |
| `menu-classic` | Простое меню без Textual |
| `probe` | Проверка Yandex Music token |
| `auth-implicit` | Music-совместимый token через браузер |
| `auth-app` | Свой OAuth app (Music API обычно 403) |
| `probe-id` | Яндекс ID, не Музыка |
| `spotify-spike` | OAuth Spotify + короткий smoke |

### Библиотека и matching

| Команда | Что делает |
|---------|------------|
| `scan` / `inspect` | Snapshot лайков и плейлистов |
| `migrate-dry-run` | Search + match, без записи (**все** лайки по умолчанию) |
| `review` | Очередь спорных; `--accept` / `--skip` |
| `normalize-preview` / `match-preview` | Офлайн-превью |

### Запись

| Команда | Что делает |
|---------|------------|
| `migrate` | Запись лайков; default → sandbox; `--dest library` → «Любимое» |
| `migrate-playlists` | Копии плейлистов; default → все непустые, без обрезки треков |

Полезные флаги: `--limit`, `--track-limit`, `--resume`, `--dest`, `--playlist-id`, `--kind`, `--dry-run`.

---

## Тесты

```bash
uv run python -m unittest discover -s tests -v
```

Нужен `tests/__init__.py`: иначе unittest может подхватить чужой пакет `tests` из `yandex-music`.

---

## Документация

| Тема | Файл |
|------|------|
| CLI, песочница, VPN | [docs/a7-cli.md](docs/a7-cli.md) |
| Dry-run и квота Spotify | [docs/dry-run.md](docs/dry-run.md) |
| Запись лайков | [docs/migrate.md](docs/migrate.md) |
| Matching | [docs/matching.md](docs/matching.md) |
| Домен и слои | [docs/domain.md](docs/domain.md) |
| Telegram-бот (ТЗ) | [docs/telegram-bot.md](docs/telegram-bot.md) |
| Яндекс auth | [docs/yandex-auth.md](docs/yandex-auth.md) |
| Spotify spike | [docs/spotify-spike.md](docs/spotify-spike.md) |

---

## Секреты

Не коммить `.env` и `.data/` (токены, snapshot, SQLite).  
Redirect с `#access_token=` — только в локальный терминал, не в чат и не в issue.

---

## Планы (без розовых очков)

**Сделано:** CLI полный пайплайн; Telegram-бот B0–B9 (connect → scan → plan → review → migrate → playlists).

**Ближайшее (B10):** боевой прогон большой медиатеки через бот/CLI с учётом квоты ~650 search/сутки — это дни ожидания, не «одна кнопка».

**Не обещаем скоро:**

- Extended Quota / чужие Spotify-аккаунты «из коробки» — у Spotify порог для организаций
- Official Yandex library API — его нет; implicit останется хрупким
- Мгновенный перенос тысяч треков — упирается в Dev Mode, не в «оптимизацию бота»
- Донаты, web dashboard, двусторонняя синхронизация, LLM-matching — бэклог этапа C, не спринт B

**Реалистичный запуск публичной беты для других:** свой VPS, HTTPS OAuth callback, очередь jobs, честный дисклеймер про квоту и Dev Mode. Без этого бот удобен в первую очередь автору app и тем, кого добавили в Dashboard.
