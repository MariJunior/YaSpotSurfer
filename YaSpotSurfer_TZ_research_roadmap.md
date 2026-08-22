# YaSpotSurfer — техническое задание, исследование и roadmap

## 1. Краткое описание проекта

**YaSpotSurfer** — сервис для миграции музыкальной библиотеки пользователя из **Яндекс Музыки** в **Spotify**.

Изначальная пользовательская задача:

- перенести любимые треки;
- перенести плейлисты;
- перенести подписки / любимых исполнителей;
- по возможности перенести любимые альбомы;
- сохранить структуру библиотеки;
- корректно сопоставлять версии треков;
- не создавать мусор и дубликаты в Spotify;
- давать пользователю контроль над сомнительными совпадениями.

Целевая UX-форма сервиса — **Telegram-бот**, но разработка начинается с локального CLI/spike для проверки интеграций и качества данных.

---

# 2. Главная продуктовая идея

Не делать «ещё один TuneMyMusic», который молча пытается перенести всё и в конце показывает процент успеха.

Главная ценность YaSpotSurfer:

1. **Прозрачный matching**
   - сервис объясняет, насколько он уверен, что найден именно тот трек;
   - различает original / live / remaster / remix / acoustic / radio edit и т.п.

2. **Dry run до записи в Spotify**
   - сначала строится полный план миграции;
   - пользователь видит статистику;
   - только потом изменения применяются в Spotify.

3. **Ручная проверка спорных совпадений**
   - high confidence → автоматически;
   - medium confidence → очередь review;
   - low confidence → не переносить без решения пользователя.

4. **Возобновляемая миграция**
   - при падении на 4 217-м треке сервис не должен начинать всё сначала;
   - состояние должно сохраняться.

5. **Работа с очень большой библиотекой**
   - проектировать сразу на тысячи/десятки тысяч треков;
   - учитывать пагинацию, rate limits, retry, checkpoints и idempotency.

---

# 3. Основные пользовательские сценарии

## 3.1. Подключение Яндекс Музыки

Пользователь авторизуется через Яндекс OAuth.

Нужно получить возможность читать:

- account / user profile;
- liked tracks;
- playlists;
- playlist tracks;
- liked/favorite artists;
- liked/favorite albums — если API позволяет;
- метаданные трека:
  - title;
  - artists;
  - album;
  - duration;
  - version;
  - track ID;
  - availability;
  - ISRC — если доступен.

---

## 3.2. Подключение Spotify

Пользователь авторизуется через Spotify OAuth.

Нужно уметь:

- искать треки;
- создавать плейлисты;
- добавлять треки в плейлисты;
- сохранять треки в библиотеку;
- сохранять/подписываться на исполнителей;
- по возможности переносить альбомы;
- читать уже существующую библиотеку для дедупликации.

---

## 3.3. Импорт библиотеки из Яндекса

Импорт должен сначала привести данные к собственной внутренней модели, не зависящей напрямую от API Яндекса.

Пример:

```ts
interface Track {
  source: "yandex" | "spotify";
  sourceId: string;

  title: string;
  artists: ArtistRef[];

  album?: {
    title: string;
    year?: number;
  };

  durationMs?: number;
  version?: string;

  isrc?: string;

  raw?: unknown;
}
```

---

## 3.4. Matching Yandex → Spotify

Приоритет matching:

1. ISRC exact match;
2. exact normalized artist + title;
3. exact artist + title + duration;
4. fuzzy title/artist match;
5. album/version comparison;
6. review queue.

Пример базовой оценки:

```text
score =
  title_similarity    * 0.45 +
  artist_similarity   * 0.30 +
  album_similarity    * 0.15 +
  duration_similarity * 0.10
```

Эти веса не считать финальными — они должны проверяться на реальных данных.

### Категории confidence

Пример:

- **>= 0.92** → auto match;
- **0.70–0.92** → manual review;
- **< 0.70** → not found / low confidence.

Пороговые значения конфигурируемые.

---

# 4. Что НЕ надо делать на первом этапе

Не начинать с Telegram UI.

Не писать сложную БД до проверки API.

Не использовать LLM для обычного matching.

Для 5–20 тысяч треков deterministic matching:

- быстрее;
- дешевле;
- объяснимее;
- воспроизводимее.

LLM можно добавить позже только как вспомогательную эвристику для действительно сложных случаев.

---

# 5. Предлагаемая архитектура

```text
                     ┌────────────────────┐
                     │   Telegram Bot     │
                     │   presentation     │
                     └─────────┬──────────┘
                               │
                               ▼
                     ┌────────────────────┐
                     │ Migration Service  │
                     ├────────────────────┤
                     │ import             │
                     │ normalization      │
                     │ matching           │
                     │ review             │
                     │ export             │
                     └─────────┬──────────┘
                               │
                   ┌───────────┴───────────┐
                   ▼                       ▼
          ┌─────────────────┐     ┌─────────────────┐
          │ Yandex Provider │     │ Spotify Provider│
          └─────────────────┘     └─────────────────┘
```

---

# 6. Возможная целевая структура проекта

Пока проект небольшой, можно держать всё в одном repo.

```text
YaSpotSurfer/
├── apps/
│   ├── bot/
│   └── cli/
│
├── packages/
│   ├── core/
│   ├── providers/
│   │   ├── yandex/
│   │   └── spotify/
│   ├── matching/
│   └── persistence/
│
├── experiments/
│   └── yandex-spike/
│
├── docs/
│
├── .env.example
├── .gitignore
└── README.md
```

Но **до появления Telegram-бота monorepo не обязателен**.

---

# 7. Текущий spike

На текущем этапе используется Python.

## Стек

- Python 3.12
- uv
- yandex-music==3.0.0
- requests
- python-dotenv
- hatchling

Причина Python для spike:
существует зрелый неофициальный клиент `yandex-music`.

В перспективе основной backend/bot можно писать на TypeScript.

---

# 8. Текущая локальная структура spike

```text
YaSpotSurfer/
├── src/
│   └── yandex_spike/
│       ├── __init__.py
│       ├── main.py
│       └── yandex.py
│
├── .data/
│
├── .env
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

---

# 9. pyproject.toml

Актуальная концепция:

```toml
[project]
name = "yaspotsurfer"
version = "0.1.0"
description = "Migration tool from Yandex Music to Spotify"
readme = "README.md"
requires-python = ">=3.12,<3.13"

dependencies = [
    "yandex-music==3.0.0",
    "requests",
    "python-dotenv",
]

[project.scripts]
yandex-spike = "yandex_spike.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/yandex_spike"]
```

---

# 10. Ошибки и исследования, которые уже были проведены

Этот раздел важен: **не повторять эти эксперименты без причины**.

---

## 10.1. Python version conflict

После:

```powershell
uv init
uv python pin 3.12
```

была ошибка:

```text
The requested Python version `3.12` is incompatible
with the project `requires-python` value of `>=3.13`.
```

Причина:

`uv init` создал:

```toml
requires-python = ">=3.13"
```

Исправлено на:

```toml
requires-python = ">=3.12,<3.13"
```

После этого:

```powershell
uv python pin 3.12
uv sync
```

работает.

---

## 10.2. Hatchling не видел package

Ошибка:

```text
ValueError: Unable to determine which files to ship inside the wheel
```

Причина:

project name:

```text
yaspotsurfer
```

а package:

```text
src/yandex_spike
```

Hatchling пытался найти package `yaspotsurfer`.

Исправление:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/yandex_spike"]
```

---

# 11. Исследование Yandex OAuth

Это наиболее важный блок текущего состояния проекта.

---

## 11.1. Попытка использовать device_auth()

Было:

```python
client = Client()
token = client.device_auth(on_code=on_code)
```

Библиотека пыталась выполнить:

```text
POST https://oauth.yandex.ru/device/code
```

и получала:

```text
yandex_music.exceptions.TimedOutError
```

Исходный traceback показывал connect timeout 5 секунд.

---

## 11.2. Проверили сеть

Проверка:

```powershell
Test-NetConnection oauth.yandex.ru -Port 443
```

результат:

```text
TcpTestSucceeded : True
```

Проверка:

```powershell
curl.exe -I https://oauth.yandex.ru
```

Яндекс ответил HTTP 405 — endpoint доступен.

Проверка:

```powershell
curl.exe -I https://oauth.yandex.com
```

Яндекс ответил HTTP 302.

Следовательно:
**общей проблемы DNS/TCP/TLS нет**.

---

## 11.3. Проверили Python requests

```powershell
uv run python -c "import requests; print(requests.get('https://oauth.yandex.ru', timeout=15).status_code)"
```

Ответ:

```text
200
```

POST:

```python
requests.post(
    "https://oauth.yandex.ru/device/code",
    data={
        "client_id": "",
        "device_id": "1234567890",
        "device_name": "YandexMusicAPI",
    },
    timeout=15,
)
```

Ответ:

```text
400
{"error": "invalid_client", "error_description": "Client not found"}
```

Следовательно:
**Python requests → oauth.yandex.ru работает нормально**.

---

# 12. Что делает yandex-music 3.0.0

Была проверена реальная установленная версия библиотеки.

Сигнатура:

```python
Client.device_auth(
    self,
    on_code,
    poll_interval=None,
    timeout=None,
    should_cancel=None,
    device_id=None,
    device_name=None,
    client_id=None,
    client_secret=None,
)
```

`request_device_code()`:

```python
data = {
    "client_id": client_id or _DEFAULT_CLIENT_ID,
    "device_id": device_id or _rand_device_id(),
    "device_name": device_name or _DEFAULT_DEVICE_NAME,
}

result = self._request.post(
    f"{_OAUTH_BASE_URL}/device/code",
    data,
)
```

Встроенный client ID:

```text
23cabbbdc6cd418abb4b39c32c41195d
```

OAuth base URL:

```text
https://oauth.yandex.ru
```

---

# 13. Implicit OAuth с official-like client ID

Проверялся URL:

```text
https://oauth.yandex.ru/authorize
?response_type=token
&client_id=23cabbbdc6cd418abb4b39c32c41195d
```

Этот flow **сработал**.

После авторизации Яндекс вернул redirect с:

```text
#access_token=...
```

То есть implicit OAuth через этот client ID работает.

Важно:

URL fragment `#access_token=...` **не отправляется HTTP-серверу**, поэтому его нельзя поймать обычным localhost callback server.

Для spike возможен ручной copy/paste redirect URL.

---

# 14. Попытка authorization code flow с official-like client ID

Пробовали:

```text
https://oauth.yandex.ru/authorize
?response_type=code
&client_id=23cabbbdc6cd418abb4b39c32c41195d
&redirect_uri=http://127.0.0.1:8765/callback
```

Получена ошибка:

```text
400
redirect_uri не совпадает с Callback URL,
указанным при регистрации приложения
```

Причина:
Callback URL зашит в конфигурации чужого/официального OAuth client и не совпадает с localhost.

---

# 15. Собственное Yandex OAuth приложение

Было создано собственное OAuth приложение:

```text
YaSpotSurfer
```

Callback URL:

```text
http://127.0.0.1:8765/callback
```

Выбран scope:

```text
music:api-public
```

UI label:

```text
Использование API Яндекс.Музыки
```

Дополнительно использовался базовый доступ к данным аккаунта.

Получены:

- client_id
- client_secret

Хранятся локально в `.env`.

**Не коммитить client_secret.**

---

# 16. Authorization code flow собственного приложения

Flow с собственным OAuth приложением успешно прошёл:

```text
authorize
→ callback?code=...
→ POST /token
→ access_token
```

Логи:

```text
✅ Authorization code получен.
🔄 Получаю access token...
✅ Access token получен и сохранён.
```

Но затем:

```python
client = Client(access_token)
client.init()
```

падает:

```text
yandex_music.exceptions.UnauthorizedError: None
```

То есть:

- OAuth token валидно выпущен;
- но `yandex-music` API его не принимает.

Это текущая важнейшая проблема.

---

# 17. Текущая рабочая гипотеза

Есть два разных класса OAuth token:

1. обычный Yandex OAuth token собственного приложения;
2. токен, который принимает private/reverse-engineered Yandex Music API.

Несмотря на scope:

```text
music:api-public
```

токен собственного приложения на текущем endpoint, который использует `yandex-music`, дал `401 Unauthorized`.

Нужно выяснить:

- существует ли отдельный официальный public Music API endpoint;
- принимает ли он `music:api-public`;
- может ли `yandex-music` 3.0.0 использовать такой токен;
- либо reverse-engineered API требует токен официального клиента.

---

# 18. Текущее направление следующего эксперимента

Вернуться к implicit flow с client ID:

```text
23cabbbdc6cd418abb4b39c32c41195d
```

Получить redirect:

```text
https://music.yandex.ru/#access_token=...
```

Распарсить token вручную.

Далее проверить:

```python
client = Client(access_token)
client.init()
```

Если этот token работает, значит проблема подтверждена:
**API принимает token official client, но не token собственного OAuth приложения**.

---

# 19. Проблема с input() — диагностика

Во время одного запуска после:

```text
Access token:
```

казалось, что CLI намертво завис и не принимает input.

Была проведена диагностика Windows Terminal.

Окружение:

```text
Windows Terminal
PowerShell 7.6.4
ConsoleHost
PSReadLine 2.4.5
```

Глобальный Python:

```text
Python 3.13.13
```

Тест:

```powershell
python -c "print(input('TEST> '))"
```

работает.

Также:

```powershell
uv run python -c "print(input('TEST> '))"
```

работает.

Следовательно:
**общей проблемы stdin / Windows Terminal нет**.

Если input снова ведёт себя странно, проблема локальна для конкретного flow/process.

---

# 20. Безопасность

Никогда не коммитить:

```text
.env
.data/yandex-token.json
Spotify refresh/access tokens
Yandex access/refresh tokens
client_secret
```

`.gitignore` должен содержать минимум:

```gitignore
.venv/
__pycache__/
*.py[cod]

.data/*
!.data/.gitkeep

.env
.env.*
!.env.example

.idea/
.vscode/

.DS_Store
Thumbs.db
```

---

# 21. Что должен делать следующий Yandex spike

Цель:

**получить реально работающий access_token и прочитать библиотеку.**

Минимальные тесты:

```python
client.init()
```

затем:

```python
client.users_likes_tracks()
client.users_playlists()
```

и получить:

```text
account
liked_tracks_count
playlists_count
```

После этого:

- взять один небольшой playlist;
- получить все его tracks;
- сериализовать raw track JSON;
- изучить доступные поля.

Особенно проверить:

```text
track.id
track.title
track.artists
track.albums
track.duration_ms
track.version
track.available
track.isrc
```

---

# 22. Snapshot данных

После успешной авторизации сохранить:

```text
.data/library-snapshot.json
```

Пример:

```json
{
  "account": {
    "uid": "...",
    "login": "...",
    "display_name": "..."
  },
  "liked_tracks_count": 8000,
  "playlists_count": 40,
  "playlists": [
    {
      "uid": "...",
      "kind": 123,
      "title": "Бег",
      "track_count": 624
    }
  ]
}
```

---

# 23. Raw export

Кроме normalized snapshot желательно сохранить raw данные:

```text
.data/raw/
├── account.json
├── liked-tracks.json
├── playlists.json
└── playlist-<id>.json
```

Это даст возможность разрабатывать matching без повторных запросов к API.

---

# 24. Абстракция MusicProvider

После spike стоит перейти к общей модели:

```ts
interface MusicProvider {
  getCurrentUser(): Promise<User>;

  getPlaylists(): Promise<Playlist[]>;
  getPlaylistTracks(id: string): Promise<Track[]>;

  getLikedTracks(): Promise<Track[]>;
  getLikedArtists(): Promise<Artist[]>;
  getLikedAlbums(): Promise<Album[]>;

  searchTrack(query: TrackSearchQuery): Promise<Track[]>;
}
```

Реализации:

```text
YandexMusicProvider
SpotifyProvider
```

---

# 25. Внутренняя модель данных

## Track

```ts
interface Track {
  id: string;

  title: string;
  normalizedTitle: string;

  artists: ArtistRef[];

  album?: AlbumRef;

  durationMs?: number;
  version?: string;

  isrc?: string;

  providerIds: {
    yandex?: string;
    spotify?: string;
  };

  raw?: unknown;
}
```

## MatchResult

```ts
interface MatchResult {
  sourceTrack: Track;

  candidates: MatchCandidate[];

  selected?: MatchCandidate;

  status:
    | "exact"
    | "high-confidence"
    | "review"
    | "not-found"
    | "skipped";
}
```

## MatchCandidate

```ts
interface MatchCandidate {
  track: Track;

  score: number;

  reasons: {
    isrc?: number;
    title?: number;
    artist?: number;
    album?: number;
    duration?: number;
    version?: number;
  };
}
```

---

# 26. Matching details

Нужно нормализовать:

- lowercase;
- Unicode;
- `ё` / `е`;
- punctuation;
- whitespace;
- `feat.`, `ft.`, `featuring`;
- artist ordering;
- brackets;
- version suffixes.

Например:

```text
Song Name (Remastered 2011)
Song Name - 2011 Remaster
Song Name (Remaster)
```

не должны автоматически считаться original version.

Отдельно детектировать keywords:

```text
live
remaster
remastered
remix
acoustic
instrumental
radio edit
sped up
slowed
demo
mono
stereo
cover
```

---

# 27. Spotify integration — требования

Нужно проверить актуальные Spotify API endpoints перед реализацией.

Функциональность:

- OAuth;
- read current library;
- search tracks;
- create playlist;
- add playlist items;
- save tracks;
- follow artists;
- optionally save albums;
- deduplicate existing content.

---

# 28. Idempotency

Повторный запуск миграции не должен:

- создавать дубликаты playlists;
- повторно добавлять уже добавленные tracks;
- терять progress;
- менять результаты review без необходимости.

Нужно хранить:

```text
migration_id
source_entity_id
target_entity_id
status
match_score
attempt_count
last_error
updated_at
```

---

# 29. БД

Для CLI spike БД не нужна.

Для полноценного сервиса:

### MVP

SQLite.

### Production

PostgreSQL.

Сущности:

```text
users
provider_accounts
oauth_tokens
playlists
tracks
playlist_tracks
migrations
migration_items
match_candidates
review_decisions
```

---

# 30. Telegram UX

Пример стартового экрана:

```text
🎧 YaSpotSurfer

Yandex Music: 🟢 connected
Spotify: 🔴 disconnected

[Connect Spotify]
```

После подключения:

```text
What should I migrate?

[❤️ Liked tracks]
[🎵 Playlists]
[👤 Artists]
[💿 Albums]
[🔥 Everything]
```

---

# 31. Migration preview

Перед записью:

```text
🎧 Migration plan

Tracks: 8 347

🟢 Exact/high confidence: 8 012
🟡 Need review:             287
🔴 Not found:                48

[Review]
[Start migration]
[Cancel]
```

---

# 32. Review UX

Пример:

```text
Yandex:

The Cure — Lullaby

Spotify candidates:

1. The Cure — Lullaby
   confidence: 96%

2. The Cure — Lullaby (Live)
   confidence: 61%

[1]
[2]
[Skip]
[Search manually]
```

---

# 33. После миграции

Отчёт:

```text
🎧 Migration finished

Playlist: Running & Suffering

412 tracks

389 migrated
17 reviewed
6 not found

Success: 94.4%
```

---

# 34. Дополнительная продуктовая фича: Library Cleaner

После миграции сервис может анализировать библиотеку:

```text
8 347 liked tracks

1 204 are not in any playlist
386 possible duplicates
94 alternate versions
217 unavailable/missing artists
```

Функции:

- найти дубликаты;
- найти live/remaster duplicates;
- найти orphan liked tracks;
- создать плейлист «Not found»;
- создать плейлист «Needs review»;
- создать backup playlist.

---

# 35. ROADMAP

---

# A. БАЗОВЫЙ МИНИМУМ

Цель:
**реально перенести свою музыкальную библиотеку из Яндекса в Spotify без ручной работы на тысячи треков.**

## Этап A1 — Yandex spike

- [ ] получить рабочий Music API token;
- [ ] получить current user;
- [ ] получить liked tracks;
- [ ] получить playlists;
- [ ] получить playlist tracks;
- [ ] проверить liked artists;
- [ ] проверить liked albums;
- [ ] сохранить raw JSON;
- [ ] определить наличие ISRC.

Definition of Done:

```text
Локальный CLI выгружает библиотеку пользователя
в JSON без ручного редактирования данных.
```

---

## Этап A2 — Spotify spike

- [ ] создать Spotify developer app;
- [ ] OAuth;
- [ ] current user;
- [ ] search track;
- [ ] создать тестовый playlist;
- [ ] добавить 1 track;
- [ ] удалить/очистить test artifacts.

Definition of Done:

```text
CLI способен найти трек и добавить его
в тестовый Spotify playlist.
```

---

## Этап A3 — Normalized model

- [ ] Track;
- [ ] Artist;
- [ ] Album;
- [ ] Playlist;
- [ ] serializers;
- [ ] raw provider data.

---

## Этап A4 — Matching v1

- [ ] ISRC;
- [ ] artist;
- [ ] title;
- [ ] duration;
- [ ] album;
- [ ] normalized strings;
- [ ] confidence score;
- [ ] unit tests.

Тестировать на выборке минимум:

```text
100–300 реальных треков
```

---

## Этап A5 — Dry run

CLI:

```powershell
yaspotsurfer migrate --dry-run
```

Результат:

```text
exact
review
not_found
```

JSON report.

---

## Этап A6 — Spotify write

- [ ] liked tracks;
- [ ] playlists;
- [ ] playlist contents;
- [ ] artists;
- [ ] albums, если API позволяет.

Обязательно:

- batching;
- retry;
- rate limit;
- resume;
- idempotency.

---

## Этап A7 — Первый реально полезный CLI

Пример:

```powershell
yaspotsurfer auth yandex
yaspotsurfer auth spotify

yaspotsurfer scan

yaspotsurfer migrate --dry-run

yaspotsurfer review

yaspotsurfer migrate
```

После этого проект уже решает исходную личную задачу.

---

# B. КОМФОРТНЫЙ MVP

После работающего CLI.

## Telegram bot

- [ ] `/start`;
- [ ] connect Yandex;
- [ ] connect Spotify;
- [ ] scan library;
- [ ] start dry run;
- [ ] progress messages;
- [ ] review candidates;
- [ ] migration;
- [ ] final report.

---

## Persistence

- [ ] SQLite/Postgres;
- [ ] OAuth token storage;
- [ ] migration state;
- [ ] match cache;
- [ ] review decisions.

---

## Reliability

- [ ] retry with backoff;
- [ ] rate limits;
- [ ] resumable migrations;
- [ ] structured logging;
- [ ] error reports.

---

# C. РОСКОШНЫЙ МАКСИМУМ

Цель:
**не просто мигратор, а полноценный cross-platform music library manager.**

---

## C1. Двусторонняя синхронизация

Не только:

```text
Yandex → Spotify
```

а:

```text
Yandex ↔ Spotify
```

Позже:

```text
Apple Music
YouTube Music
Deezer
SoundCloud
```

---

## C2. Continuous sync

Пользователь может включить:

```text
sync liked tracks every N hours
```

или:

```text
new Yandex likes → Spotify
```

---

## C3. Smart playlist sync

Например:

```text
Yandex playlist "Running"
↕
Spotify playlist "Running"
```

с сохранением изменений.

---

## C4. Advanced matching engine

- ISRC;
- duration fingerprint;
- artist aliases;
- transliteration;
- localized artist names;
- release year;
- album edition;
- version classifier;
- popularity hints;
- manual user rules.

---

## C5. Пользовательские правила

Например:

```text
Always prefer original over remaster.

Never choose live versions.

Prefer explicit version.

Treat "Би-2" and "Bi-2" as same artist.
```

---

## C6. Matching memory

Если пользователь один раз выбрал:

```text
Yandex track X
→
Spotify track Y
```

это решение сохраняется и переиспользуется.

---

## C7. Library intelligence

Аналитика:

- дубликаты;
- orphan tracks;
- dead playlists;
- unavailable tracks;
- repeated artists;
- genre distribution;
- decades;
- listening-library evolution.

---

## C8. Auto organization

Создание smart playlists:

```text
2020s indie
running 170–180 BPM
recent discoveries
forgotten favorites
Russian rock 2000s
summer electronic
```

---

## C9. Music backup

Экспорт библиотеки в portable format:

```text
JSON
CSV
SQLite
```

с возможностью восстановить её позже.

---

## C10. Migration history

Пользователь видит:

```text
Migration #14

Yandex → Spotify
8 347 tracks
2026-08-17

success 98.2%
```

Можно повторно запускать только failed items.

---

## C11. Web dashboard

Кроме Telegram:

```text
React / Next.js UI
```

Функции:

- OAuth;
- migration dashboard;
- progress;
- visual review;
- filters;
- diff;
- analytics.

Telegram остаётся lightweight companion.

---

## C12. Visual matching review

Для спорного трека показывать:

```text
SOURCE

Cover
Artist
Track
Album
Year
Duration

vs

SPOTIFY CANDIDATES
```

Пользователь выбирает визуально.

---

## C13. Intelligent search fallback

Если Spotify search ничего не нашёл:

1. убрать album;
2. убрать feat;
3. убрать punctuation;
4. transliterate;
5. search by ISRC;
6. search artist separately;
7. fuzzy candidate generation.

Только потом считать трек not found.

---

## C14. LLM-assisted review

Не использовать LLM как основной matcher.

Но для сложных кейсов:

```text
"Covers vs originals"
"Russian transliteration"
"weird remaster naming"
```

LLM может давать дополнительную рекомендацию.

---

## C15. Multi-user SaaS

Если проект перерастёт личный pet-project:

- accounts;
- encrypted credentials;
- jobs;
- queues;
- workers;
- billing;
- quotas;
- monitoring.

Но это **не делать раньше времени**.

---

# 36. Технические приоритеты

При выборе между feature и reliability:

1. корректность;
2. отсутствие потери данных;
3. idempotency;
4. explainable matching;
5. resumability;
6. UX;
7. скорость.

---

# 37. Основные риски

## Yandex

Главный риск:

API неофициальный/reverse-engineered и может меняться.

Нужно изолировать всё в:

```text
YandexMusicProvider
```

чтобы изменения API не затрагивали core.

---

## Spotify

- rate limits;
- API changes;
- Development Mode limitations;
- search differences between markets;
- unavailable tracks.

---

## Matching

Главный продуктовый риск:

```text
wrong match > missing match
```

Лучше не перенести трек, чем молча перенести неправильную live/remix версию.

---

# 38. Тестирование

Нужны fixtures:

```text
original
remaster
live
remix
feat
Russian transliteration
same title different artist
same artist different version
different duration
missing album
multiple artists
```

---

# 39. Logging

Не логировать OAuth tokens.

Допустимо:

```text
provider=yandex
operation=get_playlist
playlist_id=123
tracks=430
duration=1.4s
```

Недопустимо:

```text
Authorization: OAuth AQAAAA...
```

---

# 40. Cursor: рекомендуемый первый task

Не начинать писать весь сервис.

Первый task для Cursor:

> Проанализируй текущий Python spike и библиотеку `yandex-music==3.0.0`.  
> Нужно установить, почему OAuth token собственного приложения со scope `music:api-public` получает `401 Unauthorized` при `Client.init()`, тогда как implicit OAuth через client ID `23cabbbdc6cd418abb4b39c32c41195d` успешно выдаёт access_token.  
>
> Не менять архитектуру проекта до установления причины.
>
> Проверить:
>
> 1. какие API endpoints вызывает `Client.init()`;
> 2. какие headers формирует библиотека;
> 3. отличается ли формат/тип токена;
> 4. существует ли официальный endpoint для `music:api-public`;
> 5. какие auth flows ожидает `yandex-music`;
> 6. можно ли безопасно использовать implicit token official client;
> 7. зафиксировать результаты исследования в `docs/yandex-auth.md`.

---

# 41. Cursor: второй task после успешного auth

> Реализуй Yandex library inspector.
>
> Требования:
>
> - current user;
> - liked tracks;
> - playlists;
> - tracks одного playlist;
> - liked artists;
> - liked albums;
> - raw JSON export;
> - normalized JSON export;
> - исследовать доступность ISRC;
> - никаких write-запросов;
> - tokens не логировать;
> - output сохранять только в `.data/`.

---

# 42. Definition of success проекта

Минимальная успешная версия YaSpotSurfer:

```text
1. Авторизоваться в Yandex.
2. Авторизоваться в Spotify.
3. Просканировать библиотеку.
4. Найти соответствия.
5. Показать dry run.
6. Разобрать ambiguous matches.
7. Перенести liked tracks и playlists.
8. Безопасно продолжить после падения.
9. Не создавать дубликаты.
10. Выдать понятный final report.
```

После этого всё остальное — уже приятная роскошь.
