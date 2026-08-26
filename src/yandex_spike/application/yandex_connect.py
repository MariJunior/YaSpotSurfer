"""Подключение Яндекс Музыки: implicit URL → проверка → UserAccountStore."""

from __future__ import annotations

from dataclasses import dataclass

from requests.exceptions import ConnectionError, RequestException, Timeout

from yandex_spike.application.ports import UserAccountStore
from yandex_spike.yandex import (
    build_implicit_auth_url,
    parse_implicit_redirect,
    probe_music_http,
)

# Текст для чата: из РФ Telegram/Spotify часто нужен VPN, а Яндекс через тот же VPN падает.
_YANDEX_NETWORK_HINT = (
    "Яндекс Музыка не отвечает с этой сети. "
    "VPN нужен для Telegram и Spotify, но через него api.music.yandex.net часто молчит. "
    "Не выключай VPN целиком: сделай исключение (split tunnel) для Яндекса — "
    "oauth.yandex.ru, music.yandex.ru и api.music.yandex.net мимо VPN — "
    "и пришли адрес снова."
)


class YandexConnectError(RuntimeError):
    """Понятная ошибка для чата: неверный URL, сеть, отказ API."""


@dataclass(frozen=True)
class YandexConnectLink:
    authorize_url: str


@dataclass(frozen=True)
class YandexConnectResult:
    telegram_id: int
    ok: bool


def begin_yandex_connect() -> YandexConnectLink:
    return YandexConnectLink(authorize_url=build_implicit_auth_url())


def complete_yandex_connect(
    store: UserAccountStore,
    telegram_id: int,
    pasted_url: str,
) -> YandexConnectResult:
    """Разбирает pasted URL, проверяет Music API, шифрует токен в store.

    Текст URL в логи не пишем — там ключ доступа.
    Проверка только HTTP с timeout (без Client.init), чтобы бот не зависал.
    """
    try:
        token_data = parse_implicit_redirect(pasted_url)
    except RuntimeError as exc:
        # Сообщения parse_* уже по-русски; обернём единым типом для хендлера.
        raise YandexConnectError(_friendly_parse_error(str(exc))) from exc

    access_token = token_data["access_token"]
    try:
        probe = probe_music_http(access_token)
    except (Timeout, ConnectionError) as exc:
        raise YandexConnectError(_YANDEX_NETWORK_HINT) from exc
    except RequestException as exc:
        raise YandexConnectError(_YANDEX_NETWORK_HINT) from exc
    except Exception as exc:  # noqa: BLE001 — в чат без traceback
        raise YandexConnectError(
            "Не удалось проверить ключ Яндекса. Попробуй /connect_yandex ещё раз."
        ) from exc

    if not probe.get("ok"):
        raise YandexConnectError(
            "Яндекс не принял этот ключ. Открой ссылку снова, скопируй адрес "
            "сразу после входа (пока в нём есть доступ) и пришли боту."
        )

    store.save_yandex_token(telegram_id, access_token)
    return YandexConnectResult(telegram_id=telegram_id, ok=True)


def _friendly_parse_error(raw: str) -> str:
    # Уже человекочитаемо из parse_implicit_redirect; чуть смягчаем тон.
    if "access_token" in raw or "#access_token" in raw:
        return (
            "В сообщении нет адреса с ключом доступа. "
            "Открой ссылку входа, скопируй полный адрес из строки браузера "
            "(там будет длинный хвост после #) и пришли его сюда."
        )
    if "ошибку OAuth" in raw or "error" in raw.lower():
        return "Яндекс не дал доступ. Нажми /connect_yandex и попробуй ещё раз."
    return raw
