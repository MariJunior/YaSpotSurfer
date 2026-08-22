from __future__ import annotations

import argparse
import json

from .yandex import (
    OFFICIAL_LIKE_CLIENT_ID,
    TOKEN_FILE_APP,
    TOKEN_FILE_MUSIC,
    authenticate,
    authenticate_implicit,
    fetch_oauth_client_info,
    load_token,
    probe_token_file,
    probe_yandex_id,
)


def _print_probe(result: dict) -> None:
    print(f"Источник: {result['label']}")
    print(f"   Файл: {result['path']}")

    if not result["exists"]:
        print("   Файл отсутствует.")
        print()
        return

    fingerprint = result["fingerprint"]
    print(f"   access_token_length: {fingerprint['access_token_length']}")
    print(f"   looks_like_jwt:      {fingerprint['looks_like_jwt']}")
    print(f"   token_type:          {fingerprint['token_type']}")
    print(f"   expires_in:          {fingerprint['expires_in']}")
    print(f"   has_refresh_token:   {fingerprint['has_refresh_token']}")
    print(f"   source:              {fingerprint['source']}")

    probe = result["probe"]
    print(f"   HTTP /account/status: {probe.get('http_status')}")
    print(f"   Client.init() ok:     {probe.get('library_init_ok')}")

    if probe.get("library_error"):
        print(f"   Client.init() error:  {probe['library_error']}")

    if probe.get("http_error_excerpt"):
        print(f"   HTTP excerpt:         {probe['http_error_excerpt']}")

    print()


def cmd_probe() -> None:
    print("Yandex Music API probe")
    print("-" * 40)
    print()
    print("Токены в лог не печатаются.")
    print()

    app_result = probe_token_file(TOKEN_FILE_APP, "own-app (music:api-public)")
    music_result = probe_token_file(
        TOKEN_FILE_MUSIC,
        "official-like implicit",
    )

    _print_probe(app_result)
    _print_probe(music_result)

    print("JSON summary:")
    print(
        json.dumps(
            {
                "own_app": app_result,
                "official_like": music_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_auth_implicit() -> None:
    print("Yandex implicit auth")
    print("-" * 40)
    print()

    result = authenticate_implicit()
    fingerprint = result["fingerprint"]
    probe = result["probe"]

    print()
    print(f"access_token_length: {fingerprint['access_token_length']}")
    print(f"looks_like_jwt:      {fingerprint['looks_like_jwt']}")
    print(f"HTTP /account/status: {probe['http_status']}")
    print(f"Client.init() ok:     {probe['library_init_ok']}")

    if probe.get("library_error"):
        print(f"Client.init() error:  {probe['library_error']}")

    if probe["library_init_ok"]:
        print()
        print("Гипотеза подтверждена: official-like token принимает Music API.")
    else:
        print()
        print("Official-like token тоже не прошёл Client.init().")


def cmd_auth_app() -> None:
    print("Yandex own-app auth")
    print("-" * 40)
    print()
    print("Ожидаемый результат на Music API: HTTP 403 / UnauthorizedError.")
    print()

    authenticate()


def cmd_probe_id() -> None:
    print("Yandex ID probe (own-app token)")
    print("-" * 40)
    print()
    print("Официальный host: login.yandex.ru/info")
    print("Логин и token в лог не печатаются.")
    print()

    token_data = load_token(TOKEN_FILE_APP)
    if token_data is None or not token_data.get("access_token"):
        print(f"Нет own-app token в {TOKEN_FILE_APP}. Сначала auth-app.")
        return

    result = probe_yandex_id(token_data["access_token"])
    print(f"HTTP:      {result['http_status']}")
    print(f"has_id:    {result['has_id']}")
    print(f"has_login: {result['has_login']}")


def cmd_oauth_app_info() -> None:
    print("Публичный паспорт official-like OAuth app")
    print("-" * 40)
    print()

    info = fetch_oauth_client_info(OFFICIAL_LIKE_CLIENT_ID)
    print(f"name:      {info['name']}")
    print(f"callback:  {info['callback']}")
    print(f"is_yandex: {info['is_yandex']}")
    print("scopes:")
    for scope in info["scope"]:
        print(f"   • {scope}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YaSpotSurfer Yandex spike (auth research)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="probe",
        choices=(
            "probe",
            "probe-id",
            "oauth-app-info",
            "auth-implicit",
            "auth-app",
        ),
        help="По умолчанию probe — не трогает snapshot библиотеки.",
    )
    args = parser.parse_args()

    if args.command == "probe":
        cmd_probe()
    elif args.command == "probe-id":
        cmd_probe_id()
    elif args.command == "oauth-app-info":
        cmd_oauth_app_info()
    elif args.command == "auth-implicit":
        cmd_auth_implicit()
    else:
        cmd_auth_app()
