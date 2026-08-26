"""Подключение Spotify из бота: ссылка → callback → запись в UserAccountStore."""

from __future__ import annotations

from dataclasses import dataclass

from yandex_spike.application.ports import UserAccountStore
from yandex_spike.infrastructure.oauth_state import make_oauth_state, parse_oauth_state
from yandex_spike.infrastructure.spotify.oauth import (
    SpotifyOAuthError,
    build_authorize_url,
    exchange_code,
    fetch_profile,
)
from yandex_spike.infrastructure.token_cipher import TokenCipher


@dataclass(frozen=True)
class SpotifyConnectLink:
    authorize_url: str


@dataclass(frozen=True)
class SpotifyConnectResult:
    telegram_id: int
    display_name: str | None


class SpotifyConnectService:
    """Сценарии B3. HTTP к Spotify — через infrastructure, без Telegram SDK."""

    def __init__(
        self,
        *,
        store: UserAccountStore,
        cipher: TokenCipher,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._store = store
        self._cipher = cipher
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def begin(self, telegram_id: int) -> SpotifyConnectLink:
        state = make_oauth_state(self._cipher, telegram_id)
        url = build_authorize_url(
            client_id=self._client_id,
            redirect_uri=self._redirect_uri,
            state=state,
        )
        return SpotifyConnectLink(authorize_url=url)

    def complete(
        self,
        *,
        code: str | None,
        state: str | None,
        error: str | None,
    ) -> SpotifyConnectResult:
        if error:
            raise SpotifyOAuthError(
                "Вход в Spotify отменён или не удался. Нажми «Подключить Spotify» снова."
            )
        if not code or not state:
            raise SpotifyOAuthError(
                "Spotify вернул неполный ответ. Нажми «Подключить Spotify» снова."
            )
        telegram_id = parse_oauth_state(self._cipher, state)
        if telegram_id is None:
            raise SpotifyOAuthError(
                "Ссылка устарела или повреждена. Открой новую через бота."
            )
        tokens = exchange_code(
            code,
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=self._redirect_uri,
        )
        profile = fetch_profile(tokens.access_token)
        self._store.save_spotify_tokens(
            telegram_id,
            tokens.access_token,
            tokens.refresh_token,
            profile.display_name,
        )
        return SpotifyConnectResult(
            telegram_id=telegram_id,
            display_name=profile.display_name,
        )


__all__ = [
    "SpotifyConnectLink",
    "SpotifyConnectResult",
    "SpotifyConnectService",
    "SpotifyOAuthError",
]
