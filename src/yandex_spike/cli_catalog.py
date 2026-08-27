"""Каталог команд CLI: единый источник для help и интерактивного меню."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CliCommand:
    name: str
    title: str
    blurb: str
    # Показывать в интерактивном меню (research/preview можно спрятать в help).
    in_menu: bool = True


# Порядок = порядок в справке и меню.
CLI_COMMANDS: tuple[CliCommand, ...] = (
    CliCommand(
        "help",
        "Справка",
        "Полный список команд и типичный сценарий переноса.",
    ),
    CliCommand(
        "menu",
        "Интерактивное меню",
        "Выбор шага по номеру, без запоминания флагов.",
    ),
    CliCommand(
        "auth-implicit",
        "Яндекс: войти",
        "Music-совместимый token через браузер (рабочий путь).",
    ),
    CliCommand(
        "probe",
        "Яндекс: проверка",
        "Проверить Music token на /account/status.",
    ),
    CliCommand(
        "spotify-spike",
        "Spotify: войти",
        "OAuth + короткий smoke (порт callback как у бота).",
    ),
    CliCommand(
        "scan",
        "Снимок библиотеки",
        "Лайки и плейлисты → .data/library-snapshot.json.",
    ),
    CliCommand(
        "migrate-dry-run",
        "Подбор в Spotify",
        "Search + match без записи. По умолчанию вся коллекция; --resume.",
    ),
    CliCommand(
        "review",
        "Спорные треки",
        "Очередь review; --accept / --skip yandex:ID.",
    ),
    CliCommand(
        "migrate",
        "Запись лайков",
        "В песочницу (default) или --dest library. Пишет auto + accept.",
    ),
    CliCommand(
        "migrate-playlists",
        "Копия плейлистов",
        "Яндекс → YaSpotSurfer: <имя>. По умолчанию все непустые.",
    ),
    CliCommand(
        "auth-app",
        "Яндекс: свой OAuth app",
        "Свой client_id; Music API обычно 403. Для исследования.",
        in_menu=False,
    ),
    CliCommand(
        "probe-id",
        "Яндекс ID",
        "login.yandex.ru/info — не Музыка.",
        in_menu=False,
    ),
    CliCommand(
        "oauth-app-info",
        "Паспорт official-like app",
        "Публичные поля client без секретов.",
        in_menu=False,
    ),
    CliCommand(
        "inspect",
        "Снимок (alias scan)",
        "То же, что scan.",
        in_menu=False,
    ),
    CliCommand(
        "normalize-preview",
        "Превью нормализации",
        "20 лайков без API.",
        in_menu=False,
    ),
    CliCommand(
        "match-preview",
        "Превью matching",
        "Offline self-match по snapshot.",
        in_menu=False,
    ),
)

COMMAND_NAMES: tuple[str, ...] = tuple(cmd.name for cmd in CLI_COMMANDS)


def normalize_command(raw: str | None) -> str | None:
    """``help``, ``/help``, пустая строка → нормализованное имя или None."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.startswith("/"):
        text = text[1:]
    return text.lower().replace("_", "-")


def format_help_text() -> str:
    lines = [
        # Без emoji: Windows-консоль часто на cp1251 и падает на print.
        "YaSpotSurfer CLI",
        "Перенос Яндекс Музыка → Spotify",
        "",
        "Запуск:",
        "  uv run yandex-spike              -> интерактивное меню (в TTY)",
        "  uv run yandex-spike help         -> эта справка",
        "  uv run yandex-spike menu         -> меню явно",
        "  uv run yandex-spike <команда>    -> сразу шаг",
        "  uv run yandex-spike /help        -> то же, что help",
        "",
        "Типичный путь:",
        "  1) auth-implicit -> probe",
        "  2) spotify-spike",
        "  3) scan",
        "  4) migrate-dry-run --resume",
        "  5) review",
        "  6) migrate --resume",
        "  7) migrate --dest library --resume   # только после проверки песочницы",
        "  8) migrate-playlists --resume",
        "",
        "* Квота Spotify Dev Mode: ~650 search/сутки. После QUOTA_EXCEEDED -> --resume.",
        "* По умолчанию migrate пишет в «YaSpotSurfer sandbox», не в «Любимое».",
        "",
        "Команды:",
        "",
    ]
    for cmd in CLI_COMMANDS:
        lines.append(f"  {cmd.name:<20} {cmd.title}")
        lines.append(f"  {'':20} {cmd.blurb}")
        lines.append("")
    lines.extend(
        [
            "Полезные флаги:",
            "  --resume          продолжить с checkpoint",
            "  --limit N         обрезать лайки / число плейлистов",
            "  --track-limit N   обрезать треки в плейлисте",
            "  --dest playlist|library",
            "  --dry-run         только search (для migrate / migrate-playlists)",
            "  --kind ID         один плейлист Яндекса",
            "  --accept / --skip id   для review",
            "",
            "Документация: README.md, docs/a7-cli.md, docs/dry-run.md",
        ]
    )
    return "\n".join(lines)
