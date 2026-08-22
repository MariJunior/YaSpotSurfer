# Matching v1 (A4)

Детерминированный matching. LLM нет. Правило: **неверный match хуже пропуска**.

Домен не ходит в Yandex/Spotify. Кандидаты приходят снаружи (в A5 — search). Сейчас калибровка — offline self-match по snapshot.

## Пайплайн

1. **ISRC exact** — только если ISRC есть у обеих сторон. У Яндекса в A1 его не было; при разном ISRC кандидат отбрасывается.
2. Нормализованные title + artist (порядок исполнителей не важен, кириллица сличается с систематической латиницей).
3. Duration: полные 1.0 при Δ ≤ 2с, ноль при Δ ≥ 15с, линейно между ними.
4. Album: если одной стороны нет — нейтрально 0.7, не валим точный title+artist.
5. Version tags (`live` / `remaster` / `remix` / …): несовместимые **не могут** получить auto. Потолок score = 0.919 → `review` или `not-found`.
6. Два кандидата оба ≥ 0.92 и почти равны → `review` без `selected`.

Стартовые веса ТЗ: title 0.45, artist 0.30, album 0.15, duration 0.10.

Пороги: auto ≥ 0.92, review ≥ 0.70, иначе `not-found`. Конфиг — `MatchConfig`.

`exact` — ISRC или почти идеальные title+artist+duration при совместимых версиях. Иначе при auto — `high-confidence`.

Yandex часто кладёт remaster/live в поле `version`, не в title. Маппер и `effective_version_tags` это учитывают.

## Команды

```bash
uv run python -m unittest tests.test_matching tests.test_normalization
uv run yandex-spike match-preview
```

`match-preview` берёт ~250 реальных лайков (с квотой versioned-треков), каждый ищет в том же каталоге. Пишет `.data/match-preview.json`.

- `wrong_auto` должен быть 0: трек не должен автоматом сматчиться с чужим id.
- `runner_up_auto` — второй кандидат тоже ≥ 0.92 (дубль в лайках или риск). Не ошибка само по себе.

Фикстуры ТЗ §38: `tests/fixtures/matching_cases.json` (в т.ч. реальные Balder remix, Running Up That Hill, «Я влюблён»).
