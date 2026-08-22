# YaSpotSurfer

Локальный Python-spike для миграции музыкальной библиотеки из Яндекс Музыки в Spotify.

Сейчас в репозитории есть только проверка интеграции с Яндекс Музыкой (`yandex-spike`). Spotify ещё не подключён. Снимок библиотеки в коде есть, но на практике он пока не подтверждён: токен собственного OAuth-приложения получает `401 Unauthorized` на `Client.init()`.

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Запуск

```bash
uv sync
uv run yandex-spike
```

Скопируйте `.env.example` в `.env` и заполните `YANDEX_CLIENT_ID` и `YANDEX_CLIENT_SECRET`.

## Секреты

Не коммитьте `.env` и файлы в `.data/` (токен Яндекса, будущие снимки). Они уже в `.gitignore`.
