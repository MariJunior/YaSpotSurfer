from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from yandex_music import Client

import os

from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["YANDEX_CLIENT_ID"]
CLIENT_SECRET = os.environ["YANDEX_CLIENT_SECRET"]

DATA_DIR = Path(".data")
TOKEN_FILE = DATA_DIR / "yandex-token.json"

HOST = "127.0.0.1"
PORT = 8765
REDIRECT_URI = f"http://{HOST}:{PORT}/callback"

OAUTH_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"


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
            <h1>❌ Авторизация не удалась</h1>
            <p>Можешь закрыть это окно.</p>
            """
        else:
            body = """
            <h1>✅ Авторизация успешна</h1>
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


def save_token(token_data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    TOKEN_FILE.write_text(
        json.dumps(
            token_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_token() -> dict | None:
    if not TOKEN_FILE.exists():
        return None

    return json.loads(
        TOKEN_FILE.read_text(encoding="utf-8")
    )


def request_access_token(code: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=15,
    )

    response.raise_for_status()

    return response.json()


def authenticate() -> Client:
    token_data = load_token()

    if token_data:
        print("🔑 Найден сохранённый токен.")

        client = Client(token_data["access_token"])
        client.init()

        return client

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
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
        }
    )

    auth_url = f"{OAUTH_URL}?{query}"

    print("🔐 Авторизация в Яндекс Музыке")
    print()
    print(f"Открываю: {auth_url}")
    print()

    webbrowser.open(auth_url)

    print("⏳ Жду завершения авторизации...")

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

    print("✅ Authorization code получен.")
    print("🔄 Получаю access token...")

    token_data = request_access_token(
        OAuthHandler.code
    )

    save_token(token_data)

    print("✅ Access token получен и сохранён.")

    client = Client(token_data["access_token"])
    client.init()

    return client


def get_library_snapshot(client: Client) -> dict:
    account_status = client.me()

    liked_tracks = client.users_likes_tracks()
    playlists = client.users_playlists()

    snapshot = {
        "account": {
            "uid": (
                account_status.account.uid
                if account_status.account
                else None
            ),
            "login": (
                account_status.account.login
                if account_status.account
                else None
            ),
            "display_name": (
                account_status.account.display_name
                if account_status.account
                else None
            ),
        },
        "liked_tracks_count": len(liked_tracks),
        "playlists_count": len(playlists),
        "playlists": [
            {
                "uid": playlist.uid,
                "kind": playlist.kind,
                "title": playlist.title,
                "track_count": playlist.track_count,
            }
            for playlist in playlists
        ],
    }

    return snapshot
