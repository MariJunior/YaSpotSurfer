"""Точка входа бота: polling, только private chat."""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from yandex_spike.telegram.handlers import (
    cmd_help,
    cmd_start,
    on_menu_callback,
    on_plain_text,
    on_unknown_command,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Меню клиента Telegram: в B1 не рекламируем ещё не готовые команды.
_BOT_COMMANDS = [
    ("start", "Дисклеймер и меню"),
    ("help", "Пайплайн, matching, VPN"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(_BOT_COMMANDS)


def build_application(token: str) -> Application:
    """Сборка Application без запуска — удобно для тестов позже."""
    # filters.ChatType.PRIVATE: группы и каналы не обрабатываем (ТЗ: личка only).
    private = filters.ChatType.PRIVATE
    application = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", cmd_start, filters=private))
    application.add_handler(CommandHandler("help", cmd_help, filters=private))
    application.add_handler(CallbackQueryHandler(on_menu_callback, pattern=r"^menu:"))
    # Неизвестные /команды — после start/help, иначе перехватят их тоже.
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
    if not token:
        print("Задай TELEGRAM_BOT_TOKEN в .env (токен от @BotFather).", file=sys.stderr)
        raise SystemExit(1)
    # Не логируем token: длина достаточна, чтобы понять, что env подхватился.
    logger.info("Starting YaSpotSurfer bot (polling), token length=%s", len(token))
    application = build_application(token)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
