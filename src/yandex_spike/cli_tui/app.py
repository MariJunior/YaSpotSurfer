"""Textual TUI для YaSpotSurfer CLI."""

from __future__ import annotations

import contextlib
import io
import sys
import webbrowser
from collections.abc import Callable
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Footer,
    Header,
    Label,
    OptionList,
    ProgressBar,
    RichLog,
    Static,
)
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from yandex_spike.application.cli_dashboard import CliDashboard, load_cli_dashboard
from yandex_spike.cli_tui.paste_screen import PasteRedirectScreen
from yandex_spike.infrastructure.spotify.playlists import SANDBOX_PLAYLIST_NAME
from yandex_spike.yandex import build_implicit_auth_url

RunCommand = Callable[..., None]


class StatusPanel(Static):
    """Верхняя плашка: auth + этап.

    Нельзя писать сырой ``[OK]`` в строку — Rich съест это как markup-тег.
    """

    def show_dashboard(self, dash: CliDashboard) -> None:
        exact = dash.dry_by_status.get("exact", 0)
        review = dash.dry_by_status.get("review", 0)
        miss = dash.dry_by_status.get("miss", 0)

        line = Text()
        self._badge(line, "Yandex", dash.yandex_token)
        line.append("  ")
        self._badge(line, "Spotify", dash.spotify_token)
        line.append("  ")
        self._badge(line, "Snapshot", dash.snapshot_exists)
        line.append(
            f"  likes={dash.likes_total}  playlists={dash.playlists_total}\n",
            style="dim",
        )
        line.append(dash.stage_hint + "\n")
        line.append(
            f"Dry-run: done={dash.dry_done}  exact={exact}  "
            f"review={review} (open {dash.review_open})  miss={miss}",
            style="dim",
        )
        self.update(line)

    @staticmethod
    def _badge(line: Text, name: str, ok: bool) -> None:
        line.append(f"{name}: ", style="bold")
        if ok:
            line.append("OK", style="bold green")
        else:
            line.append("нет", style="bold red")


class YaSpotSurferApp(App[None]):
    """Левый бар команд + прогресс + лог выполнения."""

    TITLE = "YaSpotSurfer"
    SUB_TITLE = "Яндекс Музыка → Spotify"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status {
        height: 5;
        padding: 0 1;
        background: $surface;
        border: solid $accent;
        margin: 0 1;
    }
    #body {
        height: 1fr;
    }
    #sidebar {
        width: 34;
        border: solid $primary;
        margin: 0 0 0 1;
    }
    #sidebar-title {
        padding: 1 1 0 1;
        text-style: bold;
    }
    #commands {
        height: 1fr;
    }
    #main {
        width: 1fr;
        margin: 0 1;
    }
    #bars {
        height: auto;
        max-height: 14;
        border: solid $accent;
        padding: 0 1 1 1;
    }
    .bar-row {
        height: 3;
        margin-top: 1;
    }
    .bar-label {
        height: 1;
    }
    #log {
        height: 1fr;
        border: solid $secondary;
        margin-top: 1;
    }
    OptionList > .option-list--option-disabled {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Выход"),
        Binding("r", "refresh", "Обновить"),
        Binding("question_mark", "show_help", "Help", key_display="?"),
    ]

    def __init__(self, *, run_command: RunCommand) -> None:
        super().__init__()
        self._run_command = run_command
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatusPanel(id="status")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Label("Команды", id="sidebar-title")
                yield OptionList(id="commands")
            with Vertical(id="main"):
                with VerticalScroll(id="bars"):
                    yield Label("Прогресс", classes="bar-label")
                    for key, _label in (
                        ("dry", "Dry-run"),
                        ("quota", "Квота"),
                        ("review", "Review"),
                        ("migrate_pl", "Песочница"),
                        ("migrate_lib", "Любимое"),
                    ):
                        with Vertical(classes="bar-row"):
                            yield Label("", id=f"label-{key}", classes="bar-label")
                            yield ProgressBar(
                                id=f"bar-{key}",
                                total=100,
                                show_eta=False,
                            )
                yield RichLog(
                    id="log",
                    highlight=True,
                    markup=True,
                    wrap=True,
                    min_width=20,
                )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_dashboard()
        self.query_one("#commands", OptionList).focus()

    def action_refresh(self) -> None:
        self.refresh_dashboard()
        self.query_one("#log", RichLog).write("[dim]Статусы обновлены.[/]")

    def action_show_help(self) -> None:
        if self._busy:
            return
        self._launch("help")

    def refresh_dashboard(self) -> None:
        dash = load_cli_dashboard()
        self.query_one("#status", StatusPanel).show_dashboard(dash)
        self._fill_commands(dash)
        self._fill_bars(dash)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        # На время работы — не принимать клики по командам (фокус на Input модалки ок).
        self.query_one("#commands", OptionList).disabled = busy

    def _fill_commands(self, dash: CliDashboard) -> None:
        options = self.query_one("#commands", OptionList)
        options.clear_options()
        for item in dash.commands:
            prefix = "•" if item.enabled else "×"
            label = f"{prefix} {item.title}"
            if item.reason and not item.enabled:
                label = f"{label}  ({item.reason})"
            options.add_option(
                Option(label, id=item.command, disabled=not item.enabled)
            )

    def _fill_bars(self, dash: CliDashboard) -> None:
        by_key = {bar.key: bar for bar in dash.bars}
        for key, bar in by_key.items():
            label = self.query_one(f"#label-{key}", Label)
            progress = self.query_one(f"#bar-{key}", ProgressBar)
            label.update(bar.label)
            if bar.total is None or bar.total <= 0:
                progress.update(total=None)
            else:
                progress.update(total=bar.total, progress=min(bar.done, bar.total))

    @on(OptionList.OptionSelected, "#commands")
    def on_command_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return
        command = str(option_id)
        if command == "quit":
            self.exit()
            return
        if command == "refresh":
            self.action_refresh()
            return
        if event.option.disabled:
            self.query_one("#log", RichLog).write(
                f"[yellow]Пока недоступно:[/] {command}"
            )
            return
        if self._busy:
            self.query_one("#log", RichLog).write(
                "[yellow]Дождись окончания текущей команды.[/]"
            )
            return
        self._launch(command)

    def _launch(self, command: str) -> None:
        self._set_busy(True)
        self.query_one("#log", RichLog).write(f"[bold cyan]>>> {command}[/]")
        # auth-implicit требует видимый Input — нельзя звать input() из worker.
        if command == "auth-implicit":
            self.run_auth_implicit()
            return
        self.run_cli_command(command)

    @work(exclusive=True)
    async def run_auth_implicit(self) -> None:
        """Браузер + модалка paste + probe в thread (без stdin)."""
        try:
            auth_url = build_implicit_auth_url()
            log = self.query_one("#log", RichLog)
            log.write("Implicit OAuth (official-like client_id)")
            log.write("1. Войди в Яндекс в браузере и разреши доступ.")
            log.write(
                "2. Скопируй полный URL с #access_token=... до второго редиректа."
            )
            log.write(f"Открываю: {auth_url}")
            webbrowser.open(auth_url)

            pasted = await self.push_screen_wait(
                PasteRedirectScreen(
                    title="Яндекс: вставь redirect URL",
                    hint=(
                        "Ctrl+V / Shift+Insert · виден курсор и текст · "
                        "Enter — сохранить · Esc — отмена"
                    ),
                )
            )
            if not pasted:
                log.write("[yellow]Авторизация отменена.[/]")
                return

            # Не логируем сам token/URL целиком — только длину.
            log.write(f"URL получен ({len(pasted)} символов), проверяю Music API…")
            await self.run_cli_command_async(
                "auth-implicit",
                redirect_url=pasted,
                open_browser=False,
            )
        except Exception as exc:  # noqa: BLE001
            self._log_line(f"! {type(exc).__name__}: {exc}")
        finally:
            self._command_finished()

    async def run_cli_command_async(self, command: str, **kwargs: Any) -> None:
        """Запуск команды в thread из async-worker (с редиректом stdout)."""
        # Worker берём здесь: внутри to_thread контекста worker может не быть.
        worker = get_current_worker()

        def _job() -> tuple[int | None, str | None]:
            stream = self._make_log_stream(worker)
            exit_code: int | None = None
            error: str | None = None
            try:
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(
                    stream
                ):
                    try:
                        self._run_command(command, **kwargs)
                    except SystemExit as exc:
                        code = exc.code
                        exit_code = code if isinstance(code, int) else 1
                        if isinstance(code, str):
                            error = code
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
            finally:
                stream.flush()
            return exit_code, error

        exit_code, error = await self._run_in_thread(_job)
        if error:
            self._log_line(f"! {error}")
        if exit_code not in (None, 0):
            self._log_line(f"(exit {exit_code})")

    async def _run_in_thread(self, fn: Callable[[], Any]) -> Any:
        """Обёртка: sync-функция в thread, результат обратно в async worker."""
        import asyncio

        return await asyncio.to_thread(fn)

    def _make_log_stream(self, worker: Any) -> io.TextIOBase:
        app = self

        class _LogStream(io.TextIOBase):
            encoding = "utf-8"

            def __init__(self_stream) -> None:
                self_stream._pending = ""

            def write(self_stream, s: str) -> int:  # type: ignore[override]
                if not s:
                    return 0
                self_stream._pending += s
                while "\n" in self_stream._pending:
                    line, self_stream._pending = self_stream._pending.split("\n", 1)
                    if not worker.is_cancelled:
                        app.call_from_thread(app._log_line, line)
                return len(s)

            def flush(self_stream) -> None:
                if self_stream._pending and not worker.is_cancelled:
                    app.call_from_thread(app._log_line, self_stream._pending)
                    self_stream._pending = ""

        return _LogStream()

    @work(thread=True, exclusive=True)
    def run_cli_command(self, command: str) -> None:
        """Долгие OAuth/API — в worker, stdout → Log построчно. Без input()."""
        worker = get_current_worker()
        stream = self._make_log_stream(worker)
        kwargs = self._kwargs_for(command)
        exit_code: int | None = None
        error: str | None = None
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                try:
                    self._run_command(command, **kwargs)
                except SystemExit as exc:
                    code = exc.code
                    exit_code = code if isinstance(code, int) else 1
                    if isinstance(code, str):
                        error = code
        except Exception as exc:  # noqa: BLE001 — показать в TUI, не уронить app
            error = f"{type(exc).__name__}: {exc}"
        finally:
            stream.flush()
            if error:
                self.call_from_thread(self._log_line, f"! {error}")
            if exit_code not in (None, 0):
                self.call_from_thread(self._log_line, f"(exit {exit_code})")
            self.call_from_thread(self._command_finished)

    def _log_line(self, line: str) -> None:
        self.query_one("#log", RichLog).write(line)

    def _command_finished(self) -> None:
        self._set_busy(False)
        self.refresh_dashboard()
        self.query_one("#log", RichLog).write("[dim]— готово —[/]")
        commands = self.query_one("#commands", OptionList)
        commands.disabled = False
        commands.focus()

    def _kwargs_for(self, command: str) -> dict[str, Any]:
        """Дефолты без интерактивных вопросов: resume, песочница, без limit."""
        if command == "migrate-dry-run":
            return {"limit": None, "resume": True}
        if command == "migrate":
            return {
                "limit": None,
                "resume": True,
                "dest": "playlist",
                "playlist_name": SANDBOX_PLAYLIST_NAME,
                "playlist_id": None,
                "dry_run": False,
            }
        if command == "migrate-playlists":
            return {
                "limit": None,
                "resume": True,
                "kind": None,
                "track_limit": None,
                "dry_run": False,
            }
        if command == "review":
            return {"accept": None, "skip": None}
        return {}


def run_tui(*, run_command: RunCommand) -> None:
    """Точка входа: нужен TTY и установленный textual."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError(
            "TUI нужен интерактивный терминал. "
            "Справка: uv run yandex-spike help"
        )
    YaSpotSurferApp(run_command=run_command).run()
