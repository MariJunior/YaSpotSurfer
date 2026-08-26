"""Локальный HTTP callback для Spotify OAuth. Не путать с Telegram Bot API."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# (code|None, state|None, error|None) — ровно одно из code/error обычно заполнено.
CallbackHandler = Callable[[str | None, str | None, str | None], None]


def _html_page(title: str, body: str) -> bytes:
    return (
        "<!doctype html>"
        '<html lang="ru"><head><meta charset="utf-8">'
        f"<title>{title}</title></head>"
        f"<body><h1>{title}</h1><p>{body}</p></body></html>"
    ).encode("utf-8")


class SpotifyOAuthServer:
    """Слушает redirect_uri на localhost, пока крутится бот."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        path: str,
        on_result: CallbackHandler,
    ) -> None:
        self._host = host
        self._port = port
        self._path = path if path.startswith("/") else f"/{path}"
        self._on_result = on_result
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def listen_url(self) -> str:
        return f"http://{self._host}:{self._port}{self._path}"

    def start(self) -> None:
        path = self._path
        on_result = self._on_result

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 — HTTP API
                parsed = urlparse(self.path)
                if parsed.path != path:
                    self.send_error(404)
                    return
                params = parse_qs(parsed.query)
                error = params.get("error", [None])[0]
                code = params.get("code", [None])[0]
                state = params.get("state", [None])[0]
                try:
                    on_result(code, state, error)
                except Exception:
                    logger.exception("Spotify OAuth callback handler failed")
                    self._reply(
                        500,
                        "Что-то сломалось",
                        "Вернись в Telegram и попробуй /connect_spotify ещё раз.",
                    )
                    return
                if error:
                    self._reply(
                        200,
                        "Вход не завершён",
                        "Можешь закрыть окно и вернуться в Telegram.",
                    )
                elif code and state:
                    self._reply(
                        200,
                        "Spotify подключён",
                        "Можешь закрыть окно и вернуться в Telegram.",
                    )
                else:
                    self._reply(
                        400,
                        "Неполный ответ",
                        "Вернись в Telegram и нажми «Подключить Spotify» снова.",
                    )

            def _reply(self, status: int, title: str, body: str) -> None:
                payload = _html_page(title, body)
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                # Не светим query с code в access-логах сервера.
                logger.info("spotify-oauth %s", args[0] if args else format)

        self._httpd = ThreadingHTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="spotify-oauth-callback",
            daemon=True,
        )
        self._thread.start()
        logger.info("Spotify OAuth callback listening on %s", self.listen_url)

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
