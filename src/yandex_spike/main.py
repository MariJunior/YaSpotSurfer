from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from .application.dry_run import run_dry_run
from .application.migrate import migrate_liked_tracks
from .application.migrate_playlists import (
    playlist_migration_entry,
    sandbox_playlist_name,
    select_playlist_headers,
)
from .application.review import apply_decision, list_review_queue
from .application.match_preview import preview_self_match
from .application.normalize_preview import preview_liked_tracks
from .infrastructure.file_store import save_tracks
from .infrastructure.spotify.library import SpotifyLibraryWriter
from .infrastructure.spotify.playlists import (
    SANDBOX_PLAYLIST_NAME,
    PlaylistTrackSink,
    SpotifyPlaylistClient,
)
from .infrastructure.spotify.searcher import SpotifySearcher
from .infrastructure.yandex.mapper import track_from_yandex_snapshot
from .inspector import (
    SNAPSHOT_FILE,
    connect_music_client,
    fetch_playlist_with_tracks,
    inspect_library,
)
from .spotify import authenticate as authenticate_spotify
from .spotify import run_spotify_spike
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


def cmd_scan() -> None:
    """A7-имя из ТЗ. Тот же inspect — snapshot для matching и бота."""
    cmd_inspect()


def cmd_inspect() -> None:
    print("Yandex library inspector")
    print("-" * 40)
    print()
    print("Токены не печатаются. Write-запросов к Яндексу нет.")
    print()

    snapshot = inspect_library()

    print()
    print(f"Любимых треков:     {snapshot['liked_tracks_count']}")
    print(f"Любимых исполнителей: {snapshot['liked_artists_count']}")
    print(f"Любимых альбомов:   {snapshot['liked_albums_count']}")
    print(f"Плейлистов:         {snapshot['playlists_count']}")
    print(
        f"ISRC в лайках:      {snapshot['isrc']['liked_tracks_with_isrc']} / "
        f"{snapshot['liked_tracks_count']}"
    )
    print()
    print("Плейлисты:")
    for playlist in snapshot["playlists"]:
        print(
            f"   • {playlist['title']} — {playlist['track_count']} треков"
        )
    print()
    print(f"Snapshot: {SNAPSHOT_FILE}")
    print("Raw:      .data/raw/")


def cmd_spotify_spike() -> None:
    print("Spotify spike")
    print("-" * 40)
    print()
    print("Токены не печатаются. Тестовый плейлист удаляется в конце.")
    print()

    result = run_spotify_spike()
    print(f"user_id:       {result['user_id']}")
    print(f"display_name:  {result['display_name']}")
    print(f"search:        {result['search_query']}")
    print(
        f"track:         {result['track_artists']} — {result['track_name']} "
        f"({result['track_id']})"
    )
    print(f"track_isrc:    {result['track_isrc']}")
    print(f"playlist_id:   {result['playlist_id']}")
    print(f"added:         {result['added']}")
    print(f"cleanup_ok:    {result['cleanup_ok']} (HTTP {result['cleanup_http']})")
    print(f"cleanup_uris:  {result['cleanup_uris']}")
    if result["cleanup_excerpt"]:
        print(f"cleanup excerpt: {result['cleanup_excerpt']}")


def cmd_normalize_preview() -> None:
    print("Normalize preview")
    print("-" * 40)
    print()
    print("Токены и write-запросы не используются. Нужен inspect-snapshot.")
    print()

    tracks = preview_liked_tracks(SNAPSHOT_FILE, limit=20)
    preview_path = Path(".data") / "normalized-preview.json"
    save_tracks(preview_path, tracks)

    print(f"Треков в превью: {len(tracks)}")
    for track in tracks:
        artists = ", ".join(artist.name for artist in track.artists)
        tags = ",".join(track.version_tags) if track.version_tags else "-"
        print(f"   {artists} — {track.title}")
        print(f"      → {track.normalized_title}  tags={tags}")
    print()
    print(f"JSON: {preview_path}")


def cmd_match_preview() -> None:
    print("Match preview (offline self-match)")
    print("-" * 40)
    print()
    print("Токены и write-запросы не используются. Нужен inspect-snapshot.")
    print()

    report = preview_self_match(SNAPSHOT_FILE, limit=250)
    report_path = Path(".data") / "match-preview.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = report["counts"]
    print(f"Каталог:          {report['catalog_size']}")
    print(f"С version tags:   {report['tagged_in_catalog']}")
    print(f"exact:            {counts.get('exact', 0)}")
    print(f"high-confidence:  {counts.get('high-confidence', 0)}")
    print(f"review:           {counts.get('review', 0)}")
    print(f"not-found:        {counts.get('not-found', 0)}")
    print(f"wrong_auto:       {report['wrong_auto_count']}")
    print(f"runner_up_auto:   {report['runner_up_auto_count']}")
    for item in report["runner_up_auto"][:8]:
        print(
            f"   • {item['title']} → {item['rival_title']} "
            f"({item['rival_score']})"
        )
    print()
    print(f"JSON: {report_path}")


def cmd_migrate_dry_run(*, limit: int, resume: bool) -> None:
    print("Migrate dry-run")
    print("-" * 40)
    print()
    print("Write в Spotify нет. Нужны inspect-snapshot и Spotify token.")
    print()

    if not SNAPSHOT_FILE.exists():
        raise RuntimeError("Нет snapshot. Сначала: uv run yandex-spike inspect")

    snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    items = snapshot.get("liked_tracks") or []
    tracks = [track_from_yandex_snapshot(item) for item in items[:limit]]

    state_path = Path(".data") / "dry-run-state.json"
    processed = {}
    if resume and state_path.exists():
        processed = json.loads(state_path.read_text(encoding="utf-8")).get(
            "processed"
        ) or {}
        print(f"Resume: уже есть {len(processed)} результатов.")

    access_token = authenticate_spotify()
    searcher = SpotifySearcher(access_token)
    report = run_dry_run(tracks, searcher, processed=processed)

    report_path = Path(".data") / "dry-run-report.json"
    state_path.write_text(
        json.dumps({"processed": report["processed"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    public_report = {key: value for key, value in report.items() if key != "processed"}
    report_path.write_text(
        json.dumps(public_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = report["counts"]
    tz_counts = report["tz_counts"]
    print(f"Треков:           {report['track_count']}")
    print(f"exact:            {counts.get('exact', 0)}")
    print(f"high-confidence:  {counts.get('high-confidence', 0)}")
    print(f"review:           {counts.get('review', 0)}")
    print(f"not-found:        {counts.get('not-found', 0)}")
    print(
        f"TZ: exact={tz_counts['exact']} review={tz_counts['review']} "
        f"not_found={tz_counts['not_found']}"
    )
    print(f"wrote_to_spotify: {report['wrote_to_spotify']}")
    print()
    for row in report["results"][:12]:
        selected = row.get("selected") or {}
        target = selected.get("title") or "-"
        print(f"   {row['status']:16} {row['title']} → {target}")
    print()
    print(f"Report: {report_path}")
    print(f"State:  {state_path}")


def cmd_review(*, accept: str | None, skip: str | None) -> None:
    print("Review queue")
    print("-" * 40)
    print()

    dry_state_path = Path(".data") / "dry-run-state.json"
    if not dry_state_path.exists():
        raise RuntimeError("Нет dry-run-state.json. Сначала migrate-dry-run.")

    payload = json.loads(dry_state_path.read_text(encoding="utf-8"))
    processed = payload.get("processed") or {}

    if accept:
        row = apply_decision(processed, accept, "accept")
        payload["processed"] = processed
        dry_state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"accept {accept} → {row.get('selected', {}).get('title')}")
        return
    if skip:
        apply_decision(processed, skip, "skip")
        payload["processed"] = processed
        dry_state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"skip {skip}")
        return

    queue = list_review_queue(processed)
    open_count = sum(1 for row in queue if not row.get("decision"))
    print(f"В очереди: {open_count} без решения, всего строк: {len(queue)}")
    print()
    for row in queue:
        selected = row.get("selected") or {}
        decision = row.get("decision") or "-"
        print(
            f"   {row['source_id']}  {decision:6}  {row.get('title')} → "
            f"{selected.get('title') or '-'}"
        )
    if not queue:
        print("Пусто. Для песочницы достаточно migrate --dest playlist.")


def cmd_migrate(
    *,
    limit: int,
    resume: bool,
    dest: str,
    playlist_name: str,
    playlist_id: str | None,
) -> None:
    print("Migrate")
    print("-" * 40)
    print()
    if dest == "library":
        print("DEST=library: пишет лайки в медиатеку.")
    else:
        print(f"DEST=playlist: песочница «{playlist_name}», лайки не трогает.")
    print("Пишет только exact / high-confidence и review --accept.")
    print()

    if not SNAPSHOT_FILE.exists():
        raise RuntimeError("Нет snapshot. Сначала: uv run yandex-spike inspect")

    dry_state_path = Path(".data") / "dry-run-state.json"
    if not dry_state_path.exists():
        raise RuntimeError(
            "Нет dry-run-state.json. Сначала: "
            f"uv run yandex-spike migrate-dry-run --limit {limit}"
        )

    snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    items = snapshot.get("liked_tracks") or []
    tracks = [track_from_yandex_snapshot(item) for item in items[:limit]]
    processed = json.loads(dry_state_path.read_text(encoding="utf-8")).get(
        "processed"
    ) or {}

    match_rows = []
    missing = []
    for track in tracks:
        row = processed.get(track.id)
        if row is None:
            missing.append(track.id)
        else:
            match_rows.append(row)
    if missing:
        raise RuntimeError(
            f"Нет dry-run для {len(missing)} треков. "
            f"Сначала: uv run yandex-spike migrate-dry-run --limit {limit}"
        )

    write_path = Path(".data") / f"migrate-state-{dest}.json"
    # Старый A6 checkpoint лайков.
    if dest == "library" and not write_path.exists():
        legacy = Path(".data") / "migrate-state.json"
        if legacy.exists():
            write_path = legacy
    write_state = {}
    migration_id = str(uuid.uuid4())
    if resume and write_path.exists():
        saved = json.loads(write_path.read_text(encoding="utf-8"))
        write_state = saved.get("write_state") or {}
        migration_id = saved.get("migration_id") or migration_id
        print(f"Resume: migration_id={migration_id}, уже {len(write_state)} записей.")

    access_token = authenticate_spotify()
    if dest == "library":
        writer: SpotifyLibraryWriter | PlaylistTrackSink = SpotifyLibraryWriter(
            access_token
        )
    else:
        client = SpotifyPlaylistClient(access_token)
        resolved_id = playlist_id or client.find_or_create(playlist_name)
        print(f"Плейлист: {resolved_id}")
        writer = PlaylistTrackSink(client, resolved_id)
    report = migrate_liked_tracks(
        match_rows,
        writer,
        write_state=write_state,
        migration_id=migration_id,
    )

    write_path.write_text(
        json.dumps(
            {
                "migration_id": report["migration_id"],
                "write_state": report["write_state"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    public_report = {
        key: value for key, value in report.items() if key != "write_state"
    }
    public_report["dest"] = dest
    report_path = Path(".data") / f"migrate-report-{dest}.json"
    report_path.write_text(
        json.dumps(public_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = report["counts"]
    print(f"Треков:    {report['track_count']}")
    print(f"saved:     {counts.get('saved', 0)}")
    print(f"already:   {counts.get('already', 0)}")
    print(f"skipped:   {counts.get('skipped', 0)}")
    print()
    for row in report["results"]:
        print(
            f"   {row['write_status']:8} {row.get('title')} → "
            f"{row.get('spotify_title') or '-'}"
        )
    print()
    print(f"Report: {report_path}")
    print(f"State:  {write_path}")


def cmd_migrate_playlists(
    *,
    limit: int,
    resume: bool,
    kind: int | None,
    track_limit: int,
) -> None:
    print("Migrate playlists")
    print("-" * 40)
    print()
    print("Отдельный Spotify playlist «YaSpotSurfer: <имя Яндекса>».")
    print("Лайки и общий sandbox лайков не трогает.")
    print("Пишет только exact / high-confidence и review --accept.")
    print()

    if track_limit < 1:
        raise RuntimeError("--track-limit должен быть >= 1")
    if not SNAPSHOT_FILE.exists():
        raise RuntimeError("Нет snapshot. Сначала: uv run yandex-spike inspect")

    snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    selected = select_playlist_headers(
        snapshot.get("playlists") or [],
        limit=limit,
        kind=kind,
    )
    if not selected:
        raise RuntimeError("В snapshot нет непустых плейлистов.")

    dry_state_path = Path(".data") / "dry-run-state.json"
    dry_payload: dict = {"processed": {}}
    if dry_state_path.exists():
        dry_payload = json.loads(dry_state_path.read_text(encoding="utf-8"))
        dry_payload.setdefault("processed", {})

    print("Подключаюсь к Яндексу за треками выбранных плейлистов...")
    yandex_client = connect_music_client()
    access_token = authenticate_spotify()
    searcher = SpotifySearcher(access_token)
    spotify = SpotifyPlaylistClient(access_token)

    entries: list[dict] = []
    for header in selected:
        yandex_kind = int(header["kind"])
        title = header.get("title") or ""
        print(
            f"Плейлист Яндекса: «{title}» "
            f"(kind={yandex_kind}, в snapshot {header.get('track_count')} треков, "
            f"берём ≤{track_limit})"
        )
        detail = fetch_playlist_with_tracks(
            yandex_kind,
            client=yandex_client,
            uid=header.get("uid"),
            track_limit=track_limit,
        )
        tracks = [
            track_from_yandex_snapshot(item) for item in (detail.get("tracks") or [])
        ]
        if not tracks:
            print("   пустой после fetch — пропуск")
            continue

        dry_report = run_dry_run(
            tracks,
            searcher,
            processed=dry_payload.get("processed") or {},
        )
        dry_payload["processed"] = dry_report["processed"]
        match_rows = [dry_report["processed"][track.id] for track in tracks]

        write_path = Path(".data") / f"migrate-state-yandex-pl-{yandex_kind}.json"
        write_state: dict = {}
        migration_id = str(uuid.uuid4())
        if resume and write_path.exists():
            saved = json.loads(write_path.read_text(encoding="utf-8"))
            write_state = saved.get("write_state") or {}
            migration_id = saved.get("migration_id") or migration_id
            print(
                f"   Resume: migration_id={migration_id}, "
                f"уже {len(write_state)} записей."
            )

        dest_name = sandbox_playlist_name(detail.get("title") or title)
        playlist_id = spotify.find_or_create(dest_name)
        print(f"   Spotify: {playlist_id}  «{dest_name}»")
        writer = PlaylistTrackSink(spotify, playlist_id)
        migrate_report = migrate_liked_tracks(
            match_rows,
            writer,
            write_state=write_state,
            migration_id=migration_id,
        )
        write_path.write_text(
            json.dumps(
                {
                    "migration_id": migrate_report["migration_id"],
                    "yandex_kind": yandex_kind,
                    "spotify_playlist_id": playlist_id,
                    "write_state": migrate_report["write_state"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        entry = playlist_migration_entry(
            yandex_kind=yandex_kind,
            yandex_title=detail.get("title") or title,
            spotify_playlist_id=playlist_id,
            spotify_playlist_name=dest_name,
            migrate_report=migrate_report,
        )
        entries.append(entry)
        counts = entry["counts"]
        print(
            f"   saved={counts.get('saved', 0)} "
            f"already={counts.get('already', 0)} "
            f"skipped={counts.get('skipped', 0)}"
        )
        for row in entry["results"]:
            print(
                f"      {row['write_status']:8} {row.get('title')} → "
                f"{row.get('spotify_title') or '-'}"
            )

    dry_state_path.parent.mkdir(parents=True, exist_ok=True)
    dry_state_path.write_text(
        json.dumps(dry_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path = Path(".data") / "migrate-report-playlists.json"
    report_path.write_text(
        json.dumps(
            {
                "wrote_to_spotify": True,
                "dest": "yandex-playlists",
                "playlist_count": len(entries),
                "playlists": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print()
    print(f"Report: {report_path}")
    print(f"Dry-run cache: {dry_state_path}")
    print("review смотрит тот же dry-run-state (новые review из плейлистов).")


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
            "inspect",
            "spotify-spike",
            "normalize-preview",
            "match-preview",
            "scan",
            "migrate-dry-run",
            "review",
            "migrate",
            "migrate-playlists",
        ),
        help="По умолчанию probe — не трогает snapshot библиотеки.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "migrate / dry-run: сколько лайков (по умолчанию 20). "
            "migrate-playlists: сколько плейлистов (по умолчанию 1, сначала короткие)."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Пропустить уже обработанные id в state-файле.",
    )
    parser.add_argument(
        "--dest",
        choices=("playlist", "library"),
        default="playlist",
        help="migrate: playlist = песочница (по умолчанию), library = лайки.",
    )
    parser.add_argument(
        "--playlist-name",
        default=SANDBOX_PLAYLIST_NAME,
        help="Имя песочницы для --dest playlist.",
    )
    parser.add_argument(
        "--playlist-id",
        help="Уже существующий Spotify playlist id, без create.",
    )
    parser.add_argument(
        "--kind",
        type=int,
        help="migrate-playlists: конкретный kind плейлиста Яндекса из snapshot.",
    )
    parser.add_argument(
        "--track-limit",
        type=int,
        default=10,
        help="migrate-playlists: максимум треков в одном плейлисте (не весь гигант).",
    )
    parser.add_argument("--accept", help="review: принять selected для source_id")
    parser.add_argument("--skip", help="review: пропустить source_id")
    args = parser.parse_args()
    # Общий --limit: для лайков 20, для плейлистов 1 — чтобы не создать 20 копий случайно.
    if args.limit is None:
        args.limit = 1 if args.command == "migrate-playlists" else 20

    if args.command == "probe":
        cmd_probe()
    elif args.command == "probe-id":
        cmd_probe_id()
    elif args.command == "oauth-app-info":
        cmd_oauth_app_info()
    elif args.command == "auth-implicit":
        cmd_auth_implicit()
    elif args.command == "auth-app":
        cmd_auth_app()
    elif args.command in {"inspect", "scan"}:
        cmd_inspect()
    elif args.command == "spotify-spike":
        cmd_spotify_spike()
    elif args.command == "normalize-preview":
        cmd_normalize_preview()
    elif args.command == "match-preview":
        cmd_match_preview()
    elif args.command == "migrate-dry-run":
        cmd_migrate_dry_run(limit=args.limit, resume=args.resume)
    elif args.command == "review":
        cmd_review(accept=args.accept, skip=args.skip)
    elif args.command == "migrate-playlists":
        cmd_migrate_playlists(
            limit=args.limit,
            resume=args.resume,
            kind=args.kind,
            track_limit=args.track_limit,
        )
    else:
        cmd_migrate(
            limit=args.limit,
            resume=args.resume,
            dest=args.dest,
            playlist_name=args.playlist_name,
            playlist_id=args.playlist_id,
        )
