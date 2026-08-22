from __future__ import annotations

import argparse
import json

from .yandex import (
    TOKEN_FILE_APP,
    TOKEN_FILE_MUSIC,
    authenticate,
    authenticate_implicit,
    probe_token_file,
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
    print("━" * 40)
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
    print("━" * 40)
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
    print("━" * 40)
    print()
    print("Ожидаемый результат на Client.init(): 401 Unauthorized.")
    print()

    authenticate()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YaSpotSurfer Yandex spike (auth research)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="probe",
        choices=("probe", "auth-implicit", "auth-app"),
        help="По умолчанию probe — не трогает snapshot библиотеки.",
    )
    args = parser.parse_args()

    if args.command == "probe":
        cmd_probe()
    elif args.command == "auth-implicit":
        cmd_auth_implicit()
    else:
        cmd_auth_app()
