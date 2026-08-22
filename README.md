# YaSpotSurfer

Локальный Python-spike для миграции музыкальной библиотеки из Яндекс Музыки в Spotify.

Сейчас в репозитории есть только Yandex auth spike (`yandex-spike`). Spotify не подключён.

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

## Секреты

Не коммитьте `.env` и файлы в `.data/` (токен Яндекса, будущие снимки). Они уже в `.gitignore`.
