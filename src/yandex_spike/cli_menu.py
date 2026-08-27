"""Интерактивное меню CLI (без внешних TUI-зависимостей)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from yandex_spike.cli_catalog import CLI_COMMANDS, format_help_text
from yandex_spike.infrastructure.spotify.playlists import SANDBOX_PLAYLIST_NAME


@dataclass
class MenuAction:
    """Пункт меню → вызов use case с уже собранными kwargs."""

    key: str
    label: str
    runner: Callable[[], None]


def _ask(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def _ask_yes(prompt: str, *, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = _ask(f"{prompt} ({hint})", default="").lower()
    if not raw:
        return default
    return raw in {"y", "yes", "д", "да"}


def _ask_int(prompt: str) -> int | None:
    raw = _ask(prompt + " (пусто = все)", default="")
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("Нужно целое число или пусто.") from exc
    if value < 1:
        raise ValueError("Число должно быть >= 1.")
    return value


def build_menu_actions(
    *,
    run_command: Callable[..., None],
) -> list[MenuAction]:
    """run_command(name, **kwargs) — диспетчер из main."""

    def go_help() -> None:
        print(format_help_text())

    def go_auth() -> None:
        run_command("auth-implicit")

    def go_probe() -> None:
        run_command("probe")

    def go_spotify() -> None:
        run_command("spotify-spike")

    def go_scan() -> None:
        run_command("scan")

    def go_dry_run() -> None:
        resume = _ask_yes("Продолжить с checkpoint (--resume)?", default=True)
        limit = _ask_int("Лимит лайков")
        run_command("migrate-dry-run", limit=limit, resume=resume)

    def go_review() -> None:
        print("Список очереди. Accept/skip — отдельной командой с флагами.")
        run_command("review", accept=None, skip=None)

    def go_migrate() -> None:
        resume = _ask_yes("Продолжить с checkpoint (--resume)?", default=True)
        dest_raw = _ask(
            "Куда писать: playlist (песочница) / library (Любимое)",
            default="playlist",
        ).lower()
        if dest_raw not in {"playlist", "library"}:
            raise ValueError("Нужно playlist или library.")
        if dest_raw == "library":
            print("Внимание: запись в настоящие «Любимое» Spotify.")
            if not _ask_yes("Точно продолжить?", default=False):
                print("Отменено.")
                return
        limit = _ask_int("Лимит лайков")
        run_command(
            "migrate",
            limit=limit,
            resume=resume,
            dest=dest_raw,
            playlist_name=SANDBOX_PLAYLIST_NAME,
            playlist_id=None,
            dry_run=False,
        )

    def go_playlists() -> None:
        resume = _ask_yes("Продолжить с checkpoint (--resume)?", default=True)
        limit = _ask_int("Сколько плейлистов (сначала короткие)")
        track_limit = _ask_int("Максимум треков в одном плейлисте")
        dry = _ask_yes("Только dry-run (без записи в Spotify)?", default=False)
        run_command(
            "migrate-playlists",
            limit=limit,
            resume=resume,
            kind=None,
            track_limit=track_limit,
            dry_run=dry,
        )

    # Подписи без emoji — безопасны для cp1251 / старых консолей Windows.
    return [
        MenuAction("1", "Справка (help)", go_help),
        MenuAction("2", "Яндекс: войти (auth-implicit)", go_auth),
        MenuAction("3", "Яндекс: проверка (probe)", go_probe),
        MenuAction("4", "Spotify: войти (spotify-spike)", go_spotify),
        MenuAction("5", "Снимок библиотеки (scan)", go_scan),
        MenuAction("6", "Подбор без записи (migrate-dry-run)", go_dry_run),
        MenuAction("7", "Спорные (review)", go_review),
        MenuAction("8", "Запись лайков (migrate)", go_migrate),
        MenuAction("9", "Копия плейлистов (migrate-playlists)", go_playlists),
        MenuAction("0", "Выход", lambda: None),
    ]


def run_interactive_menu(*, run_command: Callable[..., None]) -> None:
    """Цикл меню, пока пользователь не выберет выход."""
    if not sys.stdin.isatty():
        print(
            "Интерактивное меню нужно в терминале (TTY).\n"
            "Справка: uv run yandex-spike help",
            file=sys.stderr,
        )
        print(format_help_text())
        return

    actions = build_menu_actions(run_command=run_command)
    by_key = {action.key: action for action in actions}

    print("YaSpotSurfer — интерактивное меню")
    print("Выбери номер шага. Полный список: help · выход: 0")
    print()

    while True:
        for action in actions:
            print(f"  {action.key}. {action.label}")
        print()
        choice = _ask("Номер", default="").strip().lower()
        if choice in {"q", "quit", "exit", "выход"}:
            choice = "0"
        if choice in {"h", "help", "/help"}:
            print()
            print(format_help_text())
            print()
            continue
        action = by_key.get(choice)
        if action is None:
            print("Не понял номер. Введи цифру из списка, help или 0.\n")
            continue
        if action.key == "0":
            print("Пока.")
            return
        print()
        print("-" * 40)
        try:
            action.runner()
        except (ValueError, RuntimeError, SystemExit) as exc:
            # SystemExit(2) от квоты — уже напечатали подсказку.
            if isinstance(exc, SystemExit):
                if exc.code not in (0, None):
                    print(f"(код выхода {exc.code})")
            else:
                print(f"! {exc}")
        except KeyboardInterrupt:
            print("\nПрервано. Меню снова:")
        print()
        print("-" * 40)
        print()


def menu_commands_for_tests() -> list[str]:
    """Имена команд, доступные из меню (для тестов)."""
    return [cmd.name for cmd in CLI_COMMANDS if cmd.in_menu]
