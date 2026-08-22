# YaSpotSurfer

Локальный Python-spike для миграции музыкальной библиотеки из Яндекс Музыки в Spotify.

Сейчас в репозитории есть только Yandex auth spike (`yandex-spike`). Spotify не подключён. Токен своего OAuth-приложения получает `401` на `Client.init()`; рабочий Music token ещё не подтверждён.

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

`auth-implicit` — следующий эксперимент: токен official-like client через браузер (нужно вставить redirect URL с `#access_token=`).

Своё OAuth-приложение (`YANDEX_CLIENT_ID` / `YANDEX_CLIENT_SECRET` в `.env`) по-прежнему получает token, но Music API отвечает `401`. Подробности: [docs/yandex-auth.md](docs/yandex-auth.md).

Снимок библиотеки в этом шаге не запускается.

## Секреты

Не коммитьте `.env` и файлы в `.data/` (токен Яндекса, будущие снимки). Они уже в `.gitignore`.
