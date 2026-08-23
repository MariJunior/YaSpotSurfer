"""Шифрование строк ключом из env. Не логировать plaintext."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    """Fernet: нельзя прочитать и нельзя подменить blob без ключа."""

    def __init__(self, key: str) -> None:
        # Ключ — url-safe base64 на 32 байта, как даёт Fernet.generate_key().
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, blob: str) -> str | None:
        try:
            return self._fernet.decrypt(blob.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return None
