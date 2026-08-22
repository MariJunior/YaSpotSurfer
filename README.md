# YaSpotSurfer

Локальный Python-spike для миграции музыкальной библиотеки из Яндекс Музыки в Spotify.

Yandex-выгрузка работает (`inspect`). Spotify spike: `yandex-spike spotify-spike` (нужен app в Dashboard).

Рабочий путь к Music API: `uv run yandex-spike auth-implicit` (official-like client). Токен своего OAuth-приложения Music API не принимает (HTTP 403). Подробности: [docs/yandex-auth.md](docs/yandex-auth.md).

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Запуск

```bash
uv sync
uv run yandex-spike probe
uv run yandex-spike auth-implicit
```

`probe` проверяет сохранённые токены на `api.music.yandex.net/account/status` и не печатает секреты.

Официальный Яндекс ID (не Музыка): `uv run yandex-spike probe-id`.  
Вывод по public API: [docs/yandex-public-api.md](docs/yandex-public-api.md).

`auth-implicit` получает Music-совместимый token через браузер (вставьте redirect URL с `#access_token=` только в локальный терминал, не в чат).

Своё OAuth-приложение (`YANDEX_CLIENT_ID` / `YANDEX_CLIENT_SECRET` в `.env`) token получает, но Music API отвечает 403.

Выгрузка библиотеки (нужен Music token):

```bash
uv run yandex-spike inspect
```

Пишет `.data/library-snapshot.json` и `.data/raw/`. Токены и write-запросы к Яндексу не используются.

## Spotify

Создайте app в [Developer Dashboard](https://developer.spotify.com/dashboard), Redirect URI: `http://127.0.0.1:8766/callback`. Нужен Spotify Premium у владельца app (Dev Mode 2026). Заполните `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` в `.env`.

```bash
uv run yandex-spike spotify-spike
```

Подробности: [docs/spotify-spike.md](docs/spotify-spike.md).

Доменная модель и нормализация (без matching): [docs/domain.md](docs/domain.md).

```bash
uv run yandex-spike normalize-preview
uv run python -m unittest tests.test_normalization
```

## Секреты

Не коммитьте `.env` и файлы в `.data/` (токен Яндекса, будущие снимки). Они уже в `.gitignore`.
