from __future__ import annotations

import base64
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv
from requests.exceptions import ConnectionError, Timeout

load_dotenv()

DATA_DIR = Path(".data")
TOKEN_FILE = DATA_DIR / "spotify-token.json"

HOST = "127.0.0.1"
PORT = 8766
REDIRECT_URI = f"http://{HOST}:{PORT}/callback"

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# Минимум для A2 + запас на A6, чтобы не гонять consent повторно.
SCOPES = " ".join(
    [
        "user-read-private",
        "playlist-read-private",
        "playlist-modify-private",
        "playlist-modify-public",
        "user-library-read",
        "user-library-modify",
    ]
)

SEARCH_QUERY = "track:Lullaby artist:The Cure"
TEST_PLAYLIST_NAME = "YaSpotSurfer spike test"


class SpotifyOAuthHandler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None
    state: str | None = None
    received_state: str | None = None
    server: HTTPServer | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(404)
            return

        params = parse_qs(parsed.query)
        if "error" in params:
            self.__class__.error = params["error"][0]
        elif "code" in params:
            self.__class__.code = params["code"][0]
            self.__class__.received_state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = not self.__class__.error
        title = "Авторизация успешна" if ok else "Авторизация не удалась"
        self.wfile.write(
            f"""
            <!doctype html>
            <html lang="ru">
              <head><meta charset="utf-8"><title>YaSpotSurfer</title></head>
              <body><h1>{title}</h1><p>Можешь закрыть окно.</p></body>
            </html>
            """.encode("utf-8")
        )
        threading.Thread(
            target=self.__class__.server.shutdown,
            daemon=True,
        ).start()

    def log_message(self, format: str, *args: object) -> None:
        pass


def _credentials() -> tuple[str, str]:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Задайте SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET в .env. "
            "Redirect URI в Dashboard: " + REDIRECT_URI
        )
    return client_id, client_secret


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _save_token(token_data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    token_data["saved_at"] = int(time.time())
    TOKEN_FILE.write_text(
        json.dumps(token_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_token() -> dict | None:
    if not TOKEN_FILE.exists():
        return None
    return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))


def _exchange_code(code: str) -> dict:
    client_id, client_secret = _credentials()
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={
            "Authorization": _basic_auth_header(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    data["source"] = "spotify-authorization-code"
    return data


def _refresh_access_token(refresh_token: str) -> dict:
    client_id, client_secret = _credentials()
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        headers={
            "Authorization": _basic_auth_header(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    # Spotify может не вернуть новый refresh_token.
    if "refresh_token" not in data:
        data["refresh_token"] = refresh_token
    data["source"] = "spotify-refresh"
    return data


def _token_is_fresh(token_data: dict) -> bool:
    saved_at = token_data.get("saved_at")
    expires_in = token_data.get("expires_in")
    if not saved_at or not expires_in:
        return False
    # Запас 60 секунд до истечения.
    return int(time.time()) < int(saved_at) + int(expires_in) - 60


def authenticate() -> str:
    token_data = _load_token()
    if token_data and token_data.get("access_token"):
        if _token_is_fresh(token_data):
            print("Найден свежий Spotify token.")
            return token_data["access_token"]
        if token_data.get("refresh_token"):
            print("Обновляю Spotify token...")
            refreshed = _refresh_access_token(token_data["refresh_token"])
            _save_token(refreshed)
            return refreshed["access_token"]

    client_id, _secret = _credentials()
    state = secrets.token_urlsafe(16)

    SpotifyOAuthHandler.code = None
    SpotifyOAuthHandler.error = None
    SpotifyOAuthHandler.state = state
    SpotifyOAuthHandler.received_state = None

    server = HTTPServer((HOST, PORT), SpotifyOAuthHandler)
    SpotifyOAuthHandler.server = server

    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )
    auth_url = f"{AUTHORIZE_URL}?{query}"
    print("Авторизация Spotify")
    print()
    print(f"Открываю: {auth_url}")
    print()
    webbrowser.open(auth_url)
    print("Жду callback на", REDIRECT_URI)
    server.serve_forever()
    server.server_close()

    if SpotifyOAuthHandler.error:
        raise RuntimeError(f"Spotify OAuth error: {SpotifyOAuthHandler.error}")
    if not SpotifyOAuthHandler.code:
        raise RuntimeError("Не получен authorization code.")
    if SpotifyOAuthHandler.received_state != state:
        raise RuntimeError("OAuth state не совпал — прерываю.")

    print("Меняю code на token...")
    token_data = _exchange_code(SpotifyOAuthHandler.code)
    _save_token(token_data)
    print(f"Token сохранён в {TOKEN_FILE}.")
    return token_data["access_token"]


def _api(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    attempts: int = 4,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(
                method,
                f"{API_BASE}{path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                params=params,
                json=json_body,
                timeout=20,
            )
        except (Timeout, ConnectionError) as exc:
            last_error = exc
            print(
                f"Сеть: {method} {path} не достучался "
                f"(попытка {attempt}/{attempts})."
            )
            if attempt < attempts:
                time.sleep(2 * attempt)
            continue

        # Dev Mode 2026 легко ловит 429 на серии search.
        if response.status_code == 429 and attempt < attempts:
            retry_after = response.headers.get("Retry-After", "")
            wait_sec = int(retry_after) if retry_after.isdigit() else 2 * attempt
            print(f"429 {method} {path}, жду {wait_sec}с")
            time.sleep(wait_sec)
            continue
        return response

    raise RuntimeError(
        "Не удалось соединиться с api.spotify.com. "
        "OAuth уже прошёл, токен лежит в .data/spotify-token.json — "
        "повтори ту же команду. Если падает снова: VPN или другая сеть."
    ) from last_error


def _unfollow_library_uris(
    access_token: str,
    uris: list[str],
) -> requests.Response:
    """DELETE /me/library: uris — query string, по одному, без JSON body.

    Docs: comma-separated query. requests.urlencode кодирует запятую как %2C,
    поэтому несколько URI в одном параметре ломаются. По одному URI безопаснее.
    """
    last: requests.Response | None = None
    for uri in uris:
        last = _api(
            "DELETE",
            "/me/library",
            access_token,
            params={"uris": uri},
        )
        if last.status_code not in (200, 204):
            return last
    if last is None:
        raise RuntimeError("unfollow: пустой список URI")
    return last


def _find_test_playlist_uris(access_token: str) -> list[str]:
    """Старые spike-плейлисты после прошлого 400 cleanup. Пагинация: limit 10."""
    uris: list[str] = []
    offset = 0
    page_size = 10
    # Запас: личная библиотека Spotify редко больше пары сотен плейлистов.
    max_offset = 200

    while offset <= max_offset:
        response = _api(
            "GET",
            "/me/playlists",
            access_token,
            params={"limit": page_size, "offset": offset},
        )
        if response.status_code != 200:
            break

        payload = response.json()
        items = payload.get("items") or []
        for item in items:
            if item.get("name") == TEST_PLAYLIST_NAME:
                uri = item.get("uri") or f"spotify:playlist:{item.get('id')}"
                uris.append(uri)

        total = payload.get("total")
        offset += len(items)
        if not items or (total is not None and offset >= total):
            break

    return uris


def run_spotify_spike() -> dict:
    """Search → create private playlist → add 1 track → unfollow via /me/library."""
    access_token = authenticate()

    me_response = _api("GET", "/me", access_token)
    me_response.raise_for_status()
    me = me_response.json()
    user_id = me.get("id")
    display_name = me.get("display_name")

    # Dev Mode после Feb 2026: search limit максимум 10.
    search_response = _api(
        "GET",
        "/search",
        access_token,
        params={"q": SEARCH_QUERY, "type": "track", "limit": 1},
    )
    search_response.raise_for_status()
    items = search_response.json().get("tracks", {}).get("items") or []
    if not items:
        raise RuntimeError(f"Search пустой: {SEARCH_QUERY}")

    track = items[0]
    track_id = track["id"]
    track_uri = track["uri"]
    isrc = (track.get("external_ids") or {}).get("isrc")

    create_response = _api(
        "POST",
        "/me/playlists",
        access_token,
        json_body={
            "name": TEST_PLAYLIST_NAME,
            "public": False,
            "description": "Temporary YaSpotSurfer A2 spike. Safe to delete.",
        },
    )
    create_response.raise_for_status()
    playlist = create_response.json()
    playlist_id = playlist["id"]
    playlist_uri = playlist.get("uri") or f"spotify:playlist:{playlist_id}"

    add_response = _api(
        "POST",
        f"/playlists/{playlist_id}/items",
        access_token,
        json_body={"uris": [track_uri]},
    )
    add_response.raise_for_status()

    leftover_uris = _find_test_playlist_uris(access_token)
    # Текущий тестовый плейлист тоже в список — unfollow одним запросом.
    all_cleanup = list(dict.fromkeys([*leftover_uris, playlist_uri]))
    cleanup_response = _unfollow_library_uris(access_token, all_cleanup)
    cleanup_ok = cleanup_response.status_code in (200, 204)
    cleanup_status = cleanup_response.status_code
    if not cleanup_ok:
        cleanup_excerpt = (cleanup_response.text or "")[:200]
    else:
        cleanup_excerpt = None

    return {
        "user_id": user_id,
        "display_name": display_name,
        "search_query": SEARCH_QUERY,
        "track_id": track_id,
        "track_name": track.get("name"),
        "track_artists": [
            artist.get("name") for artist in (track.get("artists") or [])
        ],
        "track_isrc": isrc,
        "playlist_id": playlist_id,
        "added": add_response.status_code in (200, 201),
        "cleanup_ok": cleanup_ok,
        "cleanup_http": cleanup_status,
        "cleanup_excerpt": cleanup_excerpt,
        "cleanup_uris": len(all_cleanup),
    }
