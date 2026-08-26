"""YaSpotSurfer — миграция библиотеки Яндекс Музыки в Spotify.

Слои (зависимости только внутрь):

- ``domain`` — Track, нормализация, matching. Без HTTP.
- ``application`` — сценарии (dry-run, review, write) и порты.
- ``infrastructure`` — Yandex Music, Spotify Web API, SQLite бота, JSON в ``.data/``.
- CLI (``main``) — парсинг аргументов и I/O файлов.
- Telegram (``telegram``) — хендлеры; B3: Spotify OAuth, Яндекс ещё нет.

Правило matching: неверный auto-match хуже пропуска. LLM в matching нет.
"""
