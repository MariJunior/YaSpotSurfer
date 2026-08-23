"""Точка входа бота: polling, только private chat, SQLite на пользователя."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from yandex_spike.infrastructure.sqlite_users import SqliteUserStore
from yandex_spike.infrastructure.token_cipher import TokenCipher
from yandex_spike.telegram.handlers import (
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
    ("logout", "Отключить аккаунты и стереть доступ"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(_BOT_COMMANDS)


def build_application(token: str, user_store: SqliteUserStore) -> Application:
    private = filters.ChatType.PRIVATE
    application = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )
    application.bot_data["user_store"] = user_store
    application.add_handler(CommandHandler("start", cmd_start, filters=private))
    application.add_handler(CommandHandler("help", cmd_help, filters=private))
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
            "Сгенерировать: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        cipher = TokenCipher(key)
    except ValueError:
        print("TOKEN_ENCRYPTION_KEY не подходит. Нужен ключ из Fernet.generate_key().", file=sys.stderr)
        raise SystemExit(1) from None
    db_path = Path(os.environ.get("BOT_DB_PATH", str(_DEFAULT_DB)))
    user_store = SqliteUserStore(db_path, cipher)
    logger.info(
        "Starting YaSpotSurfer bot (polling), token length=%s, db=%s",
        len(token),
        db_path,
    )
    application = build_application(token, user_store)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
