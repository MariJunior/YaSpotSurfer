"""Модалка: видимый Input для paste redirect URL (Yandex OAuth)."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class PasteRedirectScreen(ModalScreen[str | None]):
    """Пользователь видит курсор и вставляемый текст; Enter подтверждает."""

    BINDINGS = [
        Binding("escape", "cancel", "Отмена", show=True),
    ]

    CSS = """
    PasteRedirectScreen {
        align: center middle;
    }
    #paste-dialog {
        width: 90%;
        max-width: 100;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #paste-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #paste-hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    #paste-input {
        width: 100%;
        margin-bottom: 1;
    }
    #paste-actions {
        height: auto;
        align: right middle;
        width: 100%;
    }
    #paste-actions Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        *,
        title: str = "Вставь redirect URL",
        hint: str = "Полный адрес с #access_token=... · Enter — ок · Esc — отмена",
    ) -> None:
        super().__init__()
        self._title = title
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(id="paste-dialog"):
            yield Label(self._title, id="paste-title")
            yield Static(self._hint, id="paste-hint")
            yield Input(
                placeholder="https://...#access_token=...",
                id="paste-input",
            )
            with Horizontal(id="paste-actions"):
                yield Button("Отмена", id="paste-cancel")
                yield Button("Сохранить", variant="primary", id="paste-ok")

    def on_mount(self) -> None:
        self.query_one("#paste-input", Input).focus()

    @on(Input.Submitted, "#paste-input")
    def on_submitted(self, event: Input.Submitted) -> None:
        self._submit(event.value)

    @on(Button.Pressed, "#paste-ok")
    def on_ok(self) -> None:
        self._submit(self.query_one("#paste-input", Input).value)

    @on(Button.Pressed, "#paste-cancel")
    def on_cancel_button(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self, raw: str) -> None:
        value = raw.strip()
        if not value:
            self.notify("URL пустой — вставь ссылку из браузера.", severity="warning")
            return
        self.dismiss(value)
