"""OAuth и probe Яндекса. Выгрузка библиотеки — ``infrastructure.yandex.library``.

Свой OAuth app получает token, но Music API отвечает 403.
Рабочий путь: implicit с official-like ``client_id`` (см. docs/yandex-auth.md).
"""

from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv
from yandex_music import Client
from yandex_music.exceptions import UnauthorizedError

load_dotenv()

# Client ID официального Android-приложения Яндекс Музыки.
# Его же использует yandex-music 3.0.0 в Device Flow (см. docs/yandex-auth.md).
# Секрет приложения в наш код не копируем.
OFFICIAL_LIKE_CLIENT_ID = "23cabbbdc6cd418abb4b39c32c41195d"

DATA_DIR = Path(".data")
# Токен своего OAuth-приложения (music:api-public) — ожидаемый 401 на Music API.
TOKEN_FILE_APP = DATA_DIR / "yandex-token.json"
# Токен implicit / official-like client — отдельный файл, чтобы не затереть первый.
TOKEN_FILE_MUSIC = DATA_DIR / "yandex-token-music.json"

HOST = "127.0.0.1"
PORT = 8765
REDIRECT_URI = f"http://{HOST}:{PORT}/callback"

OAUTH_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
MUSIC_ACCOUNT_STATUS_URL = "https://api.music.yandex.net/account/status"
# Официальный API Яндекс ID — не Music API.
YANDEX_ID_INFO_URL = "https://login.yandex.ru/info"
OAUTH_CLIENT_INFO_URL = "https://oauth.yandex.ru/client/{client_id}/info"

# Те же заголовки, что ставит yandex-music 3.0.0 (RequestBase).
MUSIC_API_HEADERS = {
    "X-Yandex-Music-Client": "YandexMusicAndroid/24023621",
    "User-Agent": "Yandex-Music-API",
}


class OAuthHandler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None
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

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if self.__class__.error:
            body = """
            <h1>Авторизация не удалась</h1>
            <p>Можешь закрыть это окно.</p>
            """
        else:
            body = """
            <h1>Авторизация успешна</h1>
            <p>Можешь закрыть это окно и вернуться в терминал.</p>
            """

        self.wfile.write(
            f"""
            <!doctype html>
            <html lang="ru">
              <head>
                <meta charset="utf-8">
                <title>YaSpotSurfer</title>
              </head>
              <body>
                {body}
              </body>
            </html>
            """.encode("utf-8")
        )

        threading.Thread(
            target=self.__class__.server.shutdown,
            daemon=True,
        ).start()

    def log_message(self, format: str, *args: object) -> None:
        pass


def get_own_app_credentials() -> tuple[str, str]:
    """Читает креды своего приложения только когда они реально нужны."""
    client_id = os.environ.get("YANDEX_CLIENT_ID")
    client_secret = os.environ.get("YANDEX_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Задайте YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET в .env"
        )

    return client_id, client_secret


def save_token(token_data: dict, path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            token_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_token(path: Path) -> dict | None:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def token_fingerprint(token_data: dict) -> dict:
    """Метаданные токена без самого секрета — можно печатать в лог."""
    access = token_data.get("access_token") or ""
    parts = access.split(".")
    looks_like_jwt = len(parts) == 3 and all(parts)

    return {
        "has_access_token": bool(access),
        "access_token_length": len(access),
        "looks_like_jwt": looks_like_jwt,
        "token_type": token_data.get("token_type"),
        "expires_in": token_data.get("expires_in"),
        "has_refresh_token": bool(token_data.get("refresh_token")),
        "source": token_data.get("source"),
    }


def request_access_token(code: str) -> dict:
    client_id, client_secret = get_own_app_credentials()

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )

    response.raise_for_status()

    token_data = response.json()
    token_data["source"] = "own-app-authorization-code"
    return token_data


def probe_music_http(access_token: str, *, timeout: float | tuple[float, float] = (5, 15)) -> dict:
    """Быстрая проверка токена: только GET /account/status.

    Без Client.init() — у библиотеки нет жёсткого timeout, на «плохом» VPN
    init может висеть минутами и заморозить Telegram polling.
    """
    headers = {
        **MUSIC_API_HEADERS,
        "Authorization": f"OAuth {access_token}",
    }
    response = requests.get(
        MUSIC_ACCOUNT_STATUS_URL,
        headers=headers,
        timeout=timeout,
    )
    error_text = None
    if response.status_code != 200:
        error_text = (response.text or "")[:200]
    return {
        "http_status": response.status_code,
        "http_error_excerpt": error_text,
        "ok": response.status_code == 200,
    }


def probe_account_status(access_token: str) -> dict:
    """Повторяет запрос Client.init(): GET /account/status с заголовками библиотеки."""
    headers = {
        **MUSIC_API_HEADERS,
        "Authorization": f"OAuth {access_token}",
    }

    response = requests.get(
        MUSIC_ACCOUNT_STATUS_URL,
        headers=headers,
        timeout=15,
    )

    error_text = None
    if response.status_code != 200:
        # Тело ошибки может содержать описание, но не должно эхо-ить токен.
        error_text = (response.text or "")[:200]

    library_init_ok = False
    library_error = None

    try:
        client = Client(access_token)
        client.init()
        library_init_ok = True
    except UnauthorizedError as exc:
        library_error = f"UnauthorizedError: {exc}"
    except Exception as exc:  # noqa: BLE001 — probe должен дожить до отчёта
        library_error = f"{type(exc).__name__}: {exc}"

    return {
        "http_status": response.status_code,
        "http_error_excerpt": error_text,
        "library_init_ok": library_init_ok,
        "library_error": library_error,
    }


def probe_yandex_id(access_token: str) -> dict:
    """Официальный GET login.yandex.ru/info. Логин в лог не печатаем."""
    response = requests.get(
        YANDEX_ID_INFO_URL,
        headers={"Authorization": f"OAuth {access_token}"},
        params={"format": "json"},
        timeout=15,
    )

    has_id = False
    has_login = False
    if response.status_code == 200:
        try:
            payload = response.json()
            has_id = "id" in payload
            has_login = "login" in payload
        except ValueError:
            pass

    return {
        "http_status": response.status_code,
        "has_id": has_id,
        "has_login": has_login,
    }


def fetch_oauth_client_info(client_id: str) -> dict:
    """Публичный паспорт OAuth-приложения: имя и scopes, без секретов."""
    response = requests.get(
        OAUTH_CLIENT_INFO_URL.format(client_id=client_id),
        timeout=15,
    )
    response.raise_for_status()
    raw = response.json()
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "callback": raw.get("callback"),
        "is_yandex": raw.get("is_yandex"),
        "scope": raw.get("scope") or [],
    }


def probe_token_file(path: Path, label: str) -> dict:
    token_data = load_token(path)

    if token_data is None:
        return {
            "label": label,
            "path": str(path),
            "exists": False,
        }

    access_token = token_data.get("access_token")
    result = {
        "label": label,
        "path": str(path),
        "exists": True,
        "fingerprint": token_fingerprint(token_data),
    }

    if not access_token:
        result["probe"] = {"library_init_ok": False, "library_error": "no access_token"}
        return result

    result["probe"] = probe_account_status(access_token)
    return result


def authenticate() -> Client:
    token_data = load_token(TOKEN_FILE_APP)

    if token_data:
        print("Найден сохранённый токен своего приложения.")

        client = Client(token_data["access_token"])
        client.init()

        return client

    client_id, _client_secret = get_own_app_credentials()

    OAuthHandler.code = None
    OAuthHandler.error = None

    server = HTTPServer(
        (HOST, PORT),
        OAuthHandler,
    )

    OAuthHandler.server = server

    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
        }
    )

    auth_url = f"{OAUTH_URL}?{query}"

    print("Авторизация своим OAuth-приложением Яндекса")
    print()
    print(f"Открываю: {auth_url}")
    print()

    webbrowser.open(auth_url)

    print("Жду завершения авторизации...")

    server.serve_forever()

    server.server_close()

    if OAuthHandler.error:
        raise RuntimeError(
            f"Яндекс вернул ошибку OAuth: {OAuthHandler.error}"
        )

    if not OAuthHandler.code:
        raise RuntimeError(
            "Не удалось получить authorization code."
        )

    print("Authorization code получен.")
    print("Получаю access token...")

    token_data = request_access_token(
        OAuthHandler.code
    )

    save_token(token_data, TOKEN_FILE_APP)

    print(f"Access token сохранён в {TOKEN_FILE_APP}.")

    client = Client(token_data["access_token"])
    client.init()

    return client


def build_implicit_auth_url() -> str:
    query = urlencode(
        {
            "response_type": "token",
            "client_id": OFFICIAL_LIKE_CLIENT_ID,
        }
    )
    return f"{OAUTH_URL}?{query}"


def parse_implicit_redirect(redirect_url: str) -> dict:
    """Достаёт token из fragment. #access_token не уходит на HTTP-сервер."""
    raw = redirect_url.strip().strip('"').strip("'")
    parsed = urlparse(raw)

    # Яндекс кладёт токен в hash; если пользователь вставил только хвост — тоже ок.
    fragment = parsed.fragment
    if not fragment:
        if "#" in raw:
            fragment = raw.split("#", 1)[1]
        elif "access_token=" in raw:
            fragment = raw
        else:
            raise RuntimeError(
                "В строке нет #access_token=... "
                "Вставь полный redirect URL из адресной строки."
            )

    params = parse_qs(fragment)

    if "error" in params:
        raise RuntimeError(
            f"Яндекс вернул ошибку OAuth: {params['error'][0]}"
        )

    if "access_token" not in params:
        raise RuntimeError(
            "В URL нет access_token. Скопируй адрес до повторного редиректа."
        )

    expires_in = None
    if "expires_in" in params:
        expires_in = int(params["expires_in"][0])

    return {
        "access_token": params["access_token"][0],
        "token_type": params.get("token_type", ["bearer"])[0],
        "expires_in": expires_in,
        "source": "implicit-official-like",
        "client_id": OFFICIAL_LIKE_CLIENT_ID,
    }


def authenticate_implicit(
    *,
    redirect_url: str | None = None,
    open_browser: bool = True,
) -> dict:
    """Открывает implicit OAuth official-like client и сохраняет token.

    ``redirect_url`` — полный URL с ``#access_token=...``.
    Если не передан — спросит через ``input()`` (обычный CLI).
    В TUI: сначала модалка, затем вызов с ``redirect_url=...``, ``open_browser=False``.
    """
    auth_url = build_implicit_auth_url()

    if open_browser:
        print("Implicit OAuth через official-like client_id")
        print()
        print("1. Откроется браузер. Войди в Яндекс и разреши доступ.")
        print("2. Страница music.yandex.ru редиректит очень быстро.")
        print("   Скопируй полный URL с #access_token=... до второго редиректа.")
        print("   При необходимости включи Network throttling в DevTools.")
        print()
        print(f"Открываю: {auth_url}")
        print()
        webbrowser.open(auth_url)

    if redirect_url is None:
        redirect_url = input("Вставь полный redirect URL: ").strip()
    else:
        redirect_url = redirect_url.strip()

    if not redirect_url:
        raise RuntimeError("Пустой ввод: URL не получен.")

    token_data = parse_implicit_redirect(redirect_url)
    save_token(token_data, TOKEN_FILE_MUSIC)

    print(f"Access token сохранён в {TOKEN_FILE_MUSIC}.")
    print("Проверяю api.music.yandex.net/account/status...")

    probe = probe_account_status(token_data["access_token"])
    return {
        "fingerprint": token_fingerprint(token_data),
        "probe": probe,
    }


# Выгрузка — ``infrastructure.yandex.library.inspect_library``.
# Не вызывать ``client.me()`` как метод и ``users_playlists()`` без kind.
