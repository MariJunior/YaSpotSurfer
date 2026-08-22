# Domain model (A3)

Слои внутри пакета `yandex_spike`, без нового package и без БД.

```text
presentation  CLI (main.py)
application   порты + preview
domain        Track / Playlist / MatchResult, нормализация
infrastructure  Yandex/Spotify mappers, JSON file store
```

Домен не импортирует `yandex_music` и Spotify HTTP.

## Сущности

- `Track` — провайдер-независимый трек. `provider_ids` — кортеж пар `(provider, id)`. `raw` в matching не участвует и в JSON-store не пишется.
- `ArtistRef`, `AlbumRef`, `Playlist`
- `MatchCandidate`, `MatchResult` — результат `match_track` (A4). Подробности: [matching.md](matching.md).

Yandex `isrc` из inspect почти всегда `None`. Spotify `isrc` берём из `external_ids`, если search его отдал.

## Нормализация (ТЗ §26)

`normalize_title` / `normalize_artist`:

- NFKC, lowercase, `ё` → `е`
- punctuation и лишние пробелы
- `feat.` / `ft.` / `featuring`
- скобки вырезаются из текста
- version keywords (`live`, `remaster`, `remix`, …) — **теги**, не часть original
- год `19xx`/`20xx` снимается только если тег версии уже найден (заголовок `1999` не трогаем)
- границы слов: `Olivia` не становится `live`

Формы `Song Name (Remastered 2011)` и `Song Name - 2011 Remaster` дают один и тот же `text`, но разные `version_tags`. Неверный match хуже пропуска — A4 не должен сливать remaster с original только по тексту.

## Команда

Нужен `.data/library-snapshot.json` после `inspect`. Write-запросов к API нет.

```bash
uv run yandex-spike normalize-preview
uv run python -m unittest tests.test_normalization
```

`tests/__init__.py` обязателен: иначе `python -m unittest tests...` импортирует `tests` из `yandex-music` в site-packages (там нужен pytest).

Превью: 20 лайков → `.data/normalized-preview.json`.
