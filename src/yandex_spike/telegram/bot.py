"""Точка входа бота: polling + localhost Spotify OAuth callback."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from yandex_spike.application.spotify_connect import SpotifyConnectService, SpotifyOAuthError
from yandex_spike.infrastructure.spotify.oauth import (
    DEFAULT_REDIRECT_URI,
    load_spotify_oauth_settings,
)
from yandex_spike.infrastructure.spotify_oauth_server import SpotifyOAuthServer
from yandex_spike.infrastructure.sqlite_users import SqliteUserStore
from yandex_spike.infrastructure.token_cipher import TokenCipher
from yandex_spike.telegram.copy import spotify_connect_failed_text, spotify_connected_text
from yandex_spike.telegram.handlers import (
    cmd_connect_spotify,
    cmd_help,
    cmd_logout,
    cmd_start,
    on_menu_callback,
    on_plain_text,
    on_unknown_command,
)

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(".data/bot-users.sqlite")

_BOT_COMMANDS = [
    ("start", "О боте и меню"),
    ("help", "Как будет устроен перенос"),
    ("connect_spotify", "Подключить Spotify"),
    ("logout", "Отключить аккаунты и стереть доступ"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(_BOT_COMMANDS)
    # Callback OAuth идёт в другом потоке — нужен loop для send_message.
    application.bot_data["event_loop"] = asyncio.get_running_loop()


def _parse_redirect(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http" or not parsed.hostname or not parsed.path:
        raise ValueError(f"Некорректный SPOTIFY_REDIRECT_URI: {redirect_uri}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname, port, parsed.path


def _notify_user(application: Application, telegram_id: int, text: str) -> None:
    loop = application.bot_data.get("event_loop")
    if loop is None:
        logger.error("event_loop missing; cannot notify telegram_id=%s", telegram_id)
        return
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(chat_id=telegram_id, text=text),
        loop,
    )


def _make_oauth_callback(application: Application):
    def on_result(code: str | None, state: str | None, error: str | None) -> None:
        service: SpotifyConnectService | None = application.bot_data.get("spotify_connect")
        if service is None:
            return
        try:
            result = service.complete(code=code, state=state, error=error)
        except SpotifyOAuthError as exc:
            # Без валидного state не знаем, кому писать — только логируем.
            telegram_id = None
            try:
                from yandex_spike.infrastructure.oauth_state import parse_oauth_state

                cipher: TokenCipher | None = application.bot_data.get("token_cipher")
                if cipher is not None and state:
                    telegram_id = parse_oauth_state(cipher, state)
            except Exception:
                telegram_id = None
            if telegram_id is not None:
                _notify_user(
                    application,
                    telegram_id,
                    spotify_connect_failed_text(str(exc)),
                )
            else:
                logger.warning("Spotify OAuth failed without resolvable user: %s", exc)
            return
        _notify_user(
            application,
            result.telegram_id,
            spotify_connected_text(result.display_name),
        )

    return on_result


def build_application(
    token: str,
    user_store: SqliteUserStore,
    *,
    spotify_connect: SpotifyConnectService | None = None,
    token_cipher: TokenCipher | None = None,
    oauth_server: SpotifyOAuthServer | None = None,
) -> Application:
    private = filters.ChatType.PRIVATE
    application = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )
    application.bot_data["user_store"] = user_store
    if spotify_connect is not None:
        application.bot_data["spotify_connect"] = spotify_connect
    if token_cipher is not None:
        application.bot_data["token_cipher"] = token_cipher
    if oauth_server is not None:
        application.bot_data["oauth_server"] = oauth_server

    application.add_handler(CommandHandler("start", cmd_start, filters=private))
    application.add_handler(CommandHandler("help", cmd_help, filters=private))
    application.add_handler(
        CommandHandler("connect_spotify", cmd_connect_spotify, filters=private)
    )
    application.add_handler(CommandHandler("logout", cmd_logout, filters=private))
    application.add_handler(CallbackQueryHandler(on_menu_callback, pattern=r"^menu:"))
    application.add_handler(MessageHandler(filters.COMMAND & private, on_unknown_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & private, on_plain_text)
    )
    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "").strip()
    if not token:
        print("Задай TELEGRAM_BOT_TOKEN в .env (токен от @BotFather).", file=sys.stderr)
        raise SystemExit(1)
    if not key:
        print(
            "Задай TOKEN_ENCRYPTION_KEY в .env. "
            "Сгенерировать: uv run python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        cipher = TokenCipher(key)
    except ValueError:
        print(
            "TOKEN_ENCRYPTION_KEY не подходит. Нужен ключ из Fernet.generate_key().",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    db_path = Path(os.environ.get("BOT_DB_PATH", str(_DEFAULT_DB)))
    user_store = SqliteUserStore(db_path, cipher)

    spotify_connect: SpotifyConnectService | None = None
    oauth_server: SpotifyOAuthServer | None = None
    try:
        client_id, client_secret, redirect_uri = load_spotify_oauth_settings()
        spotify_connect = SpotifyConnectService(
            store=user_store,
            cipher=cipher,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    except SpotifyOAuthError as exc:
        logger.warning("Spotify OAuth disabled: %s", exc)

    application = build_application(
        token,
        user_store,
        spotify_connect=spotify_connect,
        token_cipher=cipher,
    )

    if spotify_connect is not None:
        host, port, path = _parse_redirect(
            os.environ.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()
        )
        oauth_server = SpotifyOAuthServer(
            host=host,
            port=port,
            path=path,
            on_result=_make_oauth_callback(application),
        )
        try:
            oauth_server.start()
        except OSError as exc:
            print(
                f"Не удалось слушать Spotify callback {host}:{port}{path}: {exc}. "
                "Освободи порт (не запускай одновременно CLI spotify-spike) "
                "или смени SPOTIFY_REDIRECT_URI.",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        application.bot_data["oauth_server"] = oauth_server

    logger.info(
        "Starting YaSpotSurfer bot (polling), token length=%s, db=%s, spotify_oauth=%s",
        len(token),
        db_path,
        "on" if spotify_connect else "off",
    )
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        if oauth_server is not None:
            oauth_server.stop()
        user_store.close()


if __name__ == "__main__":
    main()
