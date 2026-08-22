# Spotify spike (A2)

Контекст7 в этой сессии недоступен. Сверка: [Authorization Code Flow](https://developer.spotify.com/documentation/web-api/tutorials/code-flow), [Create Playlist](https://developer.spotify.com/documentation/web-api/reference/create-playlist), [Add Items](https://developer.spotify.com/documentation/web-api/reference/add-items-to-playlist), [Feb 2026 Dev Mode migration](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide).

Сегодня 2026-08-22: Development Mode уже на новых ограничениях (миграция 9 марта 2026).

## Что нужно сделать вам

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) — создать app.
2. Redirect URI **точно**: `http://127.0.0.1:8766/callback`
3. В `.env`:

```text
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

4. У владельца app должен быть **Spotify Premium** (требование Dev Mode с февраля 2026).
5. Dev Mode: до **5 пользователей** на app, если нет Extended Quota.

## Команда

```bash
uv run yandex-spike spotify-spike
```

Делает: OAuth → `GET /me` → search 1 трека → `POST /me/playlists` → `POST /playlists/{id}/items` → cleanup `DELETE /me/library`.

Токен: `.data/spotify-token.json` (не коммитить). Access token короткоживущий — spike умеет refresh.

## API, которые сознательно используем (Dev Mode 2026)

| Действие | Endpoint |
|----------|----------|
| профиль | `GET /me` (часть полей профиля снята) |
| поиск | `GET /search` limit ≤ 10 |
| создать плейлист | `POST /me/playlists` (не `/users/{id}/playlists`) |
| добавить трек | `POST /playlists/{id}/items` (не `/tracks`) |
| убрать тестовый плейлист | `DELETE /me/library` с `spotify:playlist:...` |

Search-запрос: `track:Lullaby artist:The Cure`. Если Spotify отдаст `external_ids.isrc` — это плюс для matching (с Яндекса ISRC нет).

## Если OAuth прошёл, а `/v1/me` упал с ConnectTimeout

Это **не** сломанный token. `accounts.spotify.com` (логин) и `api.spotify.com` (данные) — разные хосты. Token уже в `.data/spotify-token.json`.

Повтори ту же команду — браузер не обязателен. Spike делает несколько попыток сам.

Проверка сети без токена (ожидается HTTP 401):

```bash
curl.exe -I --connect-timeout 10 https://api.spotify.com/v1/me
```

Если TCP/timeout стабильно — нужен VPN или другая сеть. Если 401/200 — API доступен, гони `spotify-spike` ещё раз.
