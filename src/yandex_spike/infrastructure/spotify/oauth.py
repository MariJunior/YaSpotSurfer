"""Spotify Authorization Code Flow для бота (не CLI JSON-файл)."""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from requests.exceptions import ConnectionError, Timeout

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# Те же права, что у CLI: поиск, плейлисты, лайки.
SCOPES = " ".join(
    [
        "user-read-private",
        "playlist-read-private",
        "playlist-modify-private",
        "playlist-modify-public",
        "user-library-read",
        "user-library-modify",
    ]
)

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8766/callback"


@dataclass(frozen=True)
class SpotifyTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_in: int | None


@dataclass(frozen=True)
class SpotifyProfile:
    display_name: str | None
    user_id: str | None


class SpotifyOAuthError(RuntimeError):
    """Ошибка входа Spotify: сеть, отказ пользователя, неверный ответ API."""


def load_spotify_oauth_settings() -> tuple[str, str, str]:
    """client_id, client_secret, redirect_uri из env."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()
    if not client_id or not client_secret:
        raise SpotifyOAuthError(
            "В .env нет SPOTIFY_CLIENT_ID или SPOTIFY_CLIENT_SECRET. "
            f"Redirect URI в Dashboard должен совпадать: {redirect_uri}"
        )
    return client_id, client_secret, redirect_uri


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def exchange_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> SpotifyTokenBundle:
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Authorization": _basic_auth_header(client_id, client_secret),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=20,
        )
    except (Timeout, ConnectionError) as exc:
        raise SpotifyOAuthError(
            "Spotify не отвечает (сеть или VPN). Попробуй ещё раз позже."
        ) from exc
    if response.status_code >= 400:
        logger.warning("Spotify token exchange HTTP %s", response.status_code)
        raise SpotifyOAuthError(
            "Spotify не принял вход. Часто помогает VPN или повтор через минуту."
        )
    data = response.json()
    access = data.get("access_token")
    if not access:
        raise SpotifyOAuthError("Spotify не вернул ключ доступа.")
    return SpotifyTokenBundle(
        access_token=access,
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
    )


def fetch_profile(access_token: str) -> SpotifyProfile:
    try:
        response = requests.get(
            f"{API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except (Timeout, ConnectionError) as exc:
        raise SpotifyOAuthError(
            "Не удалось прочитать профиль Spotify (сеть или VPN)."
        ) from exc
    if response.status_code >= 400:
        logger.warning("Spotify /me HTTP %s", response.status_code)
        raise SpotifyOAuthError(
            "Spotify не отдал профиль. Если аккаунт чужой — возможно, "
            "приложение ещё в тестовом режиме."
        )
    data = response.json()
    return SpotifyProfile(
        display_name=data.get("display_name") or data.get("id"),
        user_id=data.get("id"),
    )
