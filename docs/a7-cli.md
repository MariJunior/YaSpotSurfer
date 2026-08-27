# CLI: полный перенос и безопасная репетиция

CLI (`yandex-spike`) — **боевой** контур того же пайплайна, что и бот. Подходит для форка: можно перенести свою медиатеку без Telegram.

**TypeScript** на этапе A/B нет. Web dashboard (если появится) — этап C.

## Куда пишем

| Режим | Куда | Когда |
|-------|------|--------|
| Default | плейлист `YaSpotSurfer sandbox` | безопасная проверка matching |
| `--dest library` | Liked Songs / «Любимое» | только после проверки песочницы |
| `migrate-playlists` | `YaSpotSurfer: <имя Яндекса>` | копии плейлистов, лайки не трогает |

По умолчанию **вся** коллекция лайков / все непустые плейлисты. `--limit` / `--track-limit` — для репетиции на куске.

## Боевой прогон (лайки)

```bash
uv run yandex-spike help
uv run yandex-spike              # меню
uv run yandex-spike auth-implicit
uv run yandex-spike probe
uv run yandex-spike spotify-spike
uv run yandex-spike scan
uv run yandex-spike migrate-dry-run --resume
uv run yandex-spike review
uv run yandex-spike migrate --resume                 # → sandbox
uv run yandex-spike migrate --dest library --resume  # → «Любимое»
```

При `QUOTA_EXCEEDED` (~650 search/сутки) checkpoint сохраняется → через часы снова с `--resume`. См. [dry-run.md](dry-run.md).

## Репетиция на куске

```bash
uv run yandex-spike migrate-dry-run --limit 50 --resume
uv run yandex-spike review
uv run yandex-spike migrate --limit 50 --resume
uv run yandex-spike migrate-playlists --limit 3 --track-limit 20 --resume
```

## Плейлисты

```bash
# Все непустые (сначала короткие), треки без обрезки
uv run yandex-spike migrate-playlists --resume

# Один kind из snapshot
uv run yandex-spike migrate-playlists --kind 1063
```

`migrate --dry-run` = `migrate-dry-run`. Если dry-run-state ещё нет на нужный объём, `migrate` сам доищет недостающие треки.

Matching кэшируется в `.data/dry-run-state.json`. Смена auto-порога пересчитывает status в кэше. `review` уважает accept/skip при следующей записи.

## VPN

- Spotify create/search → часто нужен VPN («unavailable in this country»).
- Тот же VPN может ронять Яндекс (`TimedOutError`). CLI ретраит и читает `.data/raw/playlist-*-{kind}.json`, если уже качали.
- Split tunnel: `oauth.yandex.ru`, `music.yandex.ru`, `api.music.yandex.net` мимо VPN.

## Как проверить sandbox

1. `migrate --limit 20` — появится/дополнится `YaSpotSurfer sandbox` (лайки не пишутся).
2. Повтор `--resume` → `already`.
3. `review` → accept/skip → следующий migrate уважает решение.
4. `migrate-playlists --limit 1` → `YaSpotSurfer: <имя>`.
5. Песочницы можно удалить руками в Spotify. Автоотката тестовых лайков нет.
