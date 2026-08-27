"""Тексты бота — простой русский, оформление для Telegram (эмодзи, списки)."""

from __future__ import annotations

# callback_data ≤ 64 байт (лимит Telegram).
CALLBACK_CONNECT_YANDEX = "menu:ya"
CALLBACK_CONNECT_SPOTIFY = "menu:sp"
CALLBACK_SCAN = "menu:scan"
CALLBACK_PLAN = "menu:plan"
CALLBACK_REVIEW = "menu:review"
CALLBACK_MIGRATE = "menu:mig"
CALLBACK_MIGRATE_SANDBOX = "menu:mig_sb"
CALLBACK_MIGRATE_LIBRARY = "menu:mig_lib"
CALLBACK_PLAYLISTS = "menu:pl"
CALLBACK_HELP = "menu:help"
CALLBACK_STATUS = "menu:status"

# Подтверждение записи в Liked Songs — ровно так (как в ТЗ).
MIGRATE_LIBRARY_CONFIRM_WORD = "СОХРАНИТЬ"

# Эмпирика Dev Mode (2026): ~650 search/сутки до QUOTA_EXCEEDED; не жёсткий лимит API.
SPOTIFY_DAILY_SEARCH_SOFT_CAP = 650

HELP_HINT = (
    "💬 Я отвечаю командами и кнопками, не свободным текстом.\n"
    "→ Напиши /help — там весь путь обычными словами."
)

UNKNOWN_COMMAND = (
    "❓ Такой команды пока нет.\n"
    "\n"
    "Сейчас можно:\n"
    "• /start — меню\n"
    "• /help — как устроен перенос\n"
    "• /connect_yandex · /connect_spotify\n"
    "• /scan · /plan · /review · /migrate · /playlists · /status · /cancel\n"
    "• /logout"
)

SCAN_START = "📥 Собираю список треков из Яндекс Музыки…"
SCAN_PROGRESS_PREFIX = "📥 Собираю список…\n"
SCAN_NEED_YANDEX = (
    "⚠️ Сначала подключи Яндекс Музыку.\n"
    "→ /connect_yandex или кнопка «Подключить Яндекс»."
)
SCAN_ALREADY_RUNNING = (
    "⏳ Уже идёт другая долгая операция.\n"
    "→ Подожди или останови: /cancel"
)

PLAN_START = (
    "🔎 Подбираю лайки в Spotify…\n"
    "\n"
    "📌 Важно про лимит Spotify (Dev Mode):\n"
    f"• за сутки обычно получается подобрать ~{SPOTIFY_DAILY_SEARCH_SOFT_CAP} треков;\n"
    "• потом API отвечает «квота исчерпана» на много часов;\n"
    "• прогресс сохраняется — завтра /plan продолжит с того же места.\n"
    "\n"
    "Можно свернуть чат. Смотреть ход: /status. Остановить: /cancel"
)
PLAN_PROGRESS_PREFIX = "🔎 Подбираю лайки…\n"
PLAN_ALREADY_RUNNING = SCAN_ALREADY_RUNNING

STATUS_IDLE = (
    "😴 Сейчас ничего не делается.\n"
    "→ /scan · /plan · /help"
)
JOB_CANCEL_REQUESTED = (
    "🛑 Останавливаю…\n"
    "Уже сделанное сохраняю — той же командой можно продолжить позже."
)
CANCEL_NOTHING = "🤷 Сейчас нечего отменять."

LOGOUT_DONE = (
    "🚪 Яндекс и Spotify отключены.\n"
    "Ключи доступа стёрты. Чтобы снова переносить — подключи аккаунты заново."
)
LOGOUT_NOTHING = "ℹ️ Аккаунты и так не были подключены."

SPOTIFY_CONNECT_INTRO = (
    "🎧 Подключение Spotify\n"
    "\n"
    "1. Открой ссылку ниже и войди в браузере\n"
    "2. Разреши доступ\n"
    "3. Вернись сюда — я напишу, когда аккаунт подключится\n"
    "\n"
    "⏱ Ссылка живёт ~10 минут. Не успеешь — нажми /connect_spotify снова."
)
SPOTIFY_CONNECT_NOT_CONFIGURED = (
    "⚙️ Spotify ещё не настроен на сервере бота.\n"
    "В .env нужны SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET.\n"
    "Redirect URI в кабинете Spotify должен совпадать с тем, что слушает бот\n"
    "(по умолчанию http://127.0.0.1:8766/callback)."
)

YANDEX_CONNECT_INTRO = (
    "🎵 Подключение Яндекс Музыки\n"
    "\n"
    "1. Нажми «Открыть Яндекс» и войди в аккаунт\n"
    "2. В адресной строке появится длинный хвост после #\n"
    "   → скопируй адрес целиком (не текст со страницы)\n"
    "3. Пришли этот адрес сюда одним сообщением\n"
    "\n"
    "🗑 Сообщение с адресом постараюсь сразу удалить.\n"
    "Отмена: /cancel"
)
YANDEX_CONNECTED = "✅ Яндекс Музыка подключена."
YANDEX_CONNECT_PROGRESS = "🔍 Проверяю доступ к Яндекс Музыке…"
YANDEX_CONNECT_SAVE_FAILED = (
    "❌ Что-то пошло не так при сохранении.\n"
    "→ Попробуй /connect_yandex ещё раз."
)
YANDEX_CONNECT_CANCELLED = (
    "Подключение Яндекса отменено.\n"
    "→ Можно начать снова: /connect_yandex"
)


def spotify_connected_text(display_name: str | None) -> str:
    if display_name:
        return f"✅ Spotify подключён как {display_name}."
    return "✅ Spotify подключён."


def spotify_connect_failed_text(reason: str) -> str:
    return f"❌ {reason}\n\n→ Попробовать снова: /connect_spotify"


def yandex_connect_failed_text(reason: str) -> str:
    return (
        f"❌ {reason}\n"
        "\n"
        "→ Пришли адрес ещё раз или начни заново: /connect_yandex\n"
        "→ Отмена: /cancel"
    )


def start_text(*, yandex_connected: bool = False, spotify_display_name: str | None = None) -> str:
    """Приветствие + статус связей — без гейта «согласен»."""
    yandex = "✅ подключена" if yandex_connected else "⚪ не подключена"
    if spotify_display_name:
        spotify = f"✅ подключён как {spotify_display_name}"
    else:
        spotify = "⚪ не подключён"
    return (
        "🌊 YaSpotSurfer\n"
        "Переносит музыку из Яндекс Музыки в Spotify.\n"
        "\n"
        "⚠️ Любительский проект, не сервис Яндекса и не сервис Spotify. "
        "Официального способа отдать библиотеку Яндекса другой программе нет — "
        "перенос неофициальный. Пользуешься на свой страх и риск.\n"
        "\n"
        f"🎵 Яндекс Музыка: {yandex}\n"
        f"🎧 Spotify: {spotify}\n"
        "\n"
        "Как это будет:\n"
        "1️⃣ подключаешь оба аккаунта\n"
        "2️⃣ бот читает музыку в Яндексе\n"
        "3️⃣ ищет те же треки в Spotify (спорные — спросит в /review)\n"
        "4️⃣ сначала проверочный плейлист; в «Любимые» — только с твоего согласия\n"
        "\n"
        f"📌 Подбор в Spotify (/plan): ~{SPOTIFY_DAILY_SEARCH_SOFT_CAP} треков в сутки "
        "из‑за лимита Spotify Dev Mode. Большая библиотека — несколькими днями."
    )


HELP_TEXT = (
    "📖 Что умеет бот\n"
    "\n"
    "Помогает перенести лайки и плейлисты из Яндекс Музыки в Spotify.\n"
    "Не угадывает «на глаз» и не пользуется нейросетями: "
    "сомнительный трек лучше пропустить, чем сохранить чужой.\n"
    "\n"
    "🗺 Путь\n"
    "1️⃣ /connect_yandex и /connect_spotify — аккаунты\n"
    "2️⃣ /scan — список треков из Яндекса\n"
    "3️⃣ /plan — поиск в Spotify + сводка\n"
    "4️⃣ /review — спорные по одному (кнопки)\n"
    "5️⃣ /migrate — запись лайков: сначала песочница, «Любимое» — слово СОХРАНИТЬ\n"
    "6️⃣ /playlists — короткий плейлист Яндекса → «YaSpotSurfer: …»\n"
    "\n"
    "🔑 Вход\n"
    "• Яндекс → ссылка → скопируй адрес с # из браузера → пришли боту "
    "(сообщение удалю)\n"
    "• Spotify → ссылка в браузере → вход → сообщение сюда\n"
    "\n"
    "📶 VPN (из России)\n"
    "• Telegram и Spotify часто нужен VPN\n"
    "• Яндекс через тот же VPN часто молчит\n"
    "• Не выключай VPN целиком → split tunnel мимо VPN:\n"
    "  oauth.yandex.ru · music.yandex.ru · api.music.yandex.net\n"
    "\n"
    "⏳ Лимит Spotify (/plan)\n"
    f"• приложение в Dev Mode: обычно ~{SPOTIFY_DAILY_SEARCH_SOFT_CAP} поисков в сутки\n"
    "• дальше — пауза на много часов (квота), не «баг бота»\n"
    "• прогресс сохраняется → снова /plan продолжит с места остановки\n"
    "• Extended Quota у Spotify для любительского app почти недоступна "
    "(нужна крупная компания)\n"
    "\n"
    "ℹ️ Только личка, не группы.\n"
    "Чужой Spotify в тестовом режиме app могут не пустить — ограничение Spotify.\n"
    "\n"
    "🚪 /logout — отключить аккаунты и стереть ключи.\n"
    "\n"
    "✅ Сейчас: /start /help /connect_* /scan /plan /review /migrate /playlists "
    "/status /cancel /logout"
)


def scan_done_text(*, liked_tracks: int, playlists: int, liked_with_isrc: int) -> str:
    if liked_tracks > 0 and liked_with_isrc == 0:
        isrc_line = (
            "ℹ️ Международных кодов почти нет — буду искать по названию и исполнителю."
        )
    elif liked_tracks > 0:
        isrc_line = (
            f"ℹ️ С кодом: {liked_with_isrc} из {liked_tracks}. "
            "Остальное — по названию и исполнителю."
        )
    else:
        isrc_line = "ℹ️ Лайков пока нет — плейлисты можно разобрать позже."
    return (
        f"✅ Список собран\n"
        f"\n"
        f"• Лайков: {liked_tracks}\n"
        f"• Плейлистов: {playlists}\n"
        f"{isrc_line}\n"
        "\n"
        f"➡️ Дальше /plan — подбор в Spotify "
        f"(~{SPOTIFY_DAILY_SEARCH_SOFT_CAP} треков/сутки, остальное — на следующие дни)."
    )


def scan_failed_text(reason: str) -> str:
    return f"❌ {reason}\n\n→ Снова: /scan"


def plan_done_text(
    *,
    track_count: int,
    auto_count: int,
    review_count: int,
    not_found_count: int,
    cancelled: bool,
    resumed: bool,
) -> str:
    head = "⏹ Подбор остановлен" if cancelled else "✅ Лайки: подобрал"
    notes: list[str] = []
    if resumed and not cancelled:
        notes.append("↩️ Продолжил с прошлого раза.")
    if cancelled:
        notes.append("➡️ Снова /plan — продолжу с сохранённого места.")
    note_block = ("\n" + "\n".join(notes) + "\n") if notes else "\n"
    next_step = (
        "➡️ Дальше: /review — разбери спорные по одному.\n"
        if review_count > 0
        else "Спорных нет — можно /migrate.\n"
    )
    return (
        f"{head}\n"
        f"\n"
        f"Обработано: {track_count}\n"
        f"\n"
        f"• 🟢 Уверенно: {auto_count}\n"
        f"• 🟡 Нужно твоё решение: {review_count}\n"
        f"• 🔴 В Spotify нет: {not_found_count}"
        f"{note_block}"
        "\n"
        "В Spotify уйдут только уверенные совпадения.\n"
        "Спорные и ненайденные сами не запишутся.\n"
        "\n"
        f"{next_step}"
        "ℹ️ Статус: /status"
    )


def plan_failed_text(reason: str) -> str:
    return f"{reason}\n\n→ Когда можно снова: /plan"


def plan_quota_exceeded_text(*, done: int, hours: int) -> str:
    """Сообщение при QUOTA_EXCEEDED — дневной потолок Dev Mode."""
    return (
        "🚫 Квота Spotify на сегодня исчерпана\n"
        "\n"
        "Это лимит приложения в Dev Mode (не поломка бота).\n"
        f"За сутки обычно успевает ~{SPOTIFY_DAILY_SEARCH_SOFT_CAP} поисков; "
        "потом API просит паузу на много часов.\n"
        "\n"
        f"✅ Уже подобрано и сохранено: {done}\n"
        f"⏰ Продолжить можно примерно через {hours} ч\n"
        "\n"
        "Как работать с большой библиотекой:\n"
        "1️⃣ дождись паузы (или следующего дня)\n"
        "2️⃣ снова /plan — продолжит с того же места\n"
        "3️⃣ повторяй, пока не закроешь всю коллекцию\n"
        "\n"
        "Extended Quota у Spotify для любительского проекта почти не дают "
        "(нужна крупная компания) — пока двигаемся пачками."
    )


def status_busy_text(
    *,
    label: str,
    done: int,
    total: int,
    checkpoint: int = 0,
    note: str = "",
) -> str:
    shown = max(done, checkpoint)
    if total > 0:
        line = f"⏳ Сейчас {label}: {shown}/{total}"
    else:
        line = f"⏳ Сейчас {label}."
    if checkpoint > done:
        line += (
            f"\n💾 В сохранении уже {checkpoint} "
            "(экран мог не успеть обновиться)"
        )
    if note:
        line += f"\n{note}"
    return f"{line}\n→ Остановка: /cancel"


def status_last_plan_text(
    *,
    track_count: int,
    auto_count: int,
    review_count: int,
    not_found_count: int,
    cancelled: bool,
) -> str:
    flag = " (раньше остановили)" if cancelled else ""
    return (
        f"😴 Сейчас ничего не делается.\n"
        f"\n"
        f"📊 Последний подбор лайков{flag}:\n"
        f"• Треков: {track_count}\n"
        f"• 🟢 Уверенно: {auto_count}\n"
        f"• 🟡 Нужно решение: {review_count}\n"
        f"• 🔴 Нет в Spotify: {not_found_count}\n"
        f"\n"
        f"→ /plan снова · /review · /help"
    )


REVIEW_EMPTY = (
    "✅ Очередь спорных пуста.\n"
    "\n"
    "Либо всё разобрано, либо сначала нужен /plan.\n"
    "→ /status · /help"
)
REVIEW_STALE = (
    "⏳ Эта кнопка устарела.\n"
    "→ Снова /review"
)
REVIEW_NEED_PLAN = (
    "⚠️ Сначала /plan — без подбора разбирать нечего."
)


def review_card_text(
    *,
    title: str,
    artists: tuple[str, ...] | list[str],
    candidates: tuple[dict, ...] | list[dict],
    open_remaining: int,
) -> str:
    artist_line = ", ".join(artists) if artists else "—"
    lines = [
        f"🟡 Спорный трек · осталось {open_remaining}",
        "",
        f"Яндекс: {artist_line} — {title}",
        "",
    ]
    if not candidates:
        lines.append("В Spotify подходящих вариантов почти нет.")
        lines.append("→ Пропуск или «Позже».")
    else:
        lines.append("Варианты в Spotify:")
        for index, cand in enumerate(candidates, start=1):
            cand_artists = ", ".join(cand.get("artists") or []) or "—"
            cand_title = cand.get("title") or "—"
            score = cand.get("score")
            score_s = f"{float(score):.2f}" if score is not None else "—"
            lines.append(f"{index}. {cand_artists} — {cand_title}  ({score_s})")
        lines.append("")
        lines.append("Нажми номер варианта, «Пропуск» или «Позже».")
    return "\n".join(lines)


def review_accepted_flash(chosen_title: str | None) -> str:
    if chosen_title:
        return f"Принято: {chosen_title}"
    return "Принято"


def review_done_text(*, accepted_hint: str | None = None) -> str:
    head = "✅ Спорные разобраны"
    if accepted_hint:
        return f"{head}\n\nПоследнее: {accepted_hint}\n\n→ Дальше /migrate · /status"
    return f"{head}\n\n→ Дальше /migrate · /status"


def review_failed_text(reason: str) -> str:
    return f"❌ {reason}\n\n→ /review"


MIGRATE_CHOOSE = (
    "💾 Куда записать уверенные совпадения?\n"
    "\n"
    "Пишу только:\n"
    "• 🟢 уверенный auto-match\n"
    "• 🟡 спорные, которые ты принял в /review\n"
    "\n"
    "Пропуск / без решения / «нет в Spotify» — не трогаю.\n"
    "\n"
    "Рекомендую сначала проверочный плейлист "
    "«YaSpotSurfer sandbox» — лайки Spotify не меняются.\n"
    "В «Любимые» — только после отдельного подтверждения."
)
MIGRATE_LIBRARY_CONFIRM = (
    "⚠️ Запись в «Любимое» Spotify\n"
    "\n"
    "Это уже настоящая медиатека, не песочница.\n"
    "\n"
    f"Чтобы продолжить, пришли одним сообщением слово:\n"
    f"→ {MIGRATE_LIBRARY_CONFIRM_WORD}\n"
    "\n"
    "Отмена: /cancel"
)
MIGRATE_LIBRARY_CONFIRM_CANCELLED = (
    "Запись в «Любимое» отменена.\n"
    "→ Можно снова: /migrate"
)
MIGRATE_START_SANDBOX = (
    "🧪 Пишу в проверочный плейлист «YaSpotSurfer sandbox»…\n"
    "Лайки Spotify не трогаю.\n"
    "\n"
    "→ /status · /cancel"
)
MIGRATE_START_LIBRARY = (
    "💚 Пишу в «Любимое» Spotify…\n"
    "\n"
    "→ /status · /cancel"
)
MIGRATE_PROGRESS_PREFIX = "💾 Записываю…\n"
MIGRATE_ALREADY_RUNNING = (
    "⏳ Уже идёт другая долгая операция.\n"
    "→ Подожди или останови: /cancel"
)


def migrate_done_text(
    *,
    dest: str,
    track_count: int,
    saved: int,
    already: int,
    skipped: int,
    cancelled: bool,
    playlist_name: str | None = None,
) -> str:
    if cancelled:
        head = "⏹ Запись остановлена"
        foot = "\n➡️ Снова /migrate — продолжу с сохранённого места."
    elif dest == "library":
        head = "✅ Готово: «Любимое»"
        foot = ""
    else:
        name = playlist_name or "YaSpotSurfer sandbox"
        head = f"✅ Готово: плейлист «{name}»"
        foot = (
            "\n\nПроверь плейлист в Spotify.\n"
            "Если всё ок — /migrate → «Любимое» (слово СОХРАНИТЬ)."
        )
    return (
        f"{head}\n"
        f"\n"
        f"Обработано строк: {track_count}\n"
        f"\n"
        f"• 💾 Сохранено: {saved}\n"
        f"• 📎 Уже были: {already}\n"
        f"• ⏭ Пропущено: {skipped}"
        f"{foot}\n"
        f"\n"
        f"ℹ️ /status"
    )


def migrate_failed_text(reason: str) -> str:
    return f"❌ {reason}\n\n→ /migrate"


PLAYLISTS_START = (
    "📀 Копирую самый короткий плейлист Яндекса\n"
    "\n"
    "• до 10 треков\n"
    "• в Spotify как «YaSpotSurfer: <имя>»\n"
    "• лайки и sandbox лайков не трогаю\n"
    "\n"
    "📌 Если треков ещё не было в /plan — будут search "
    f"(~{SPOTIFY_DAILY_SEARCH_SOFT_CAP}/сутки).\n"
    "\n"
    "→ /status · /cancel"
)
PLAYLISTS_ALREADY_RUNNING = (
    "⏳ Уже идёт другая долгая операция.\n"
    "→ Подожди или останови: /cancel"
)


def playlists_done_text(
    *,
    playlist_count: int,
    entries: tuple | list,
    cancelled: bool,
) -> str:
    head = "⏹ Копирование плейлистов остановлено" if cancelled else "✅ Плейлисты: готово"
    lines = [head, "", f"Скопировано сейчас: {playlist_count}", ""]
    for entry in entries:
        name = entry.get("spotify_playlist_name") or "—"
        counts = entry.get("counts") or {}
        lines.append(
            f"• {name}\n"
            f"  💾 {counts.get('saved', 0)} · "
            f"📎 {counts.get('already', 0)} · "
            f"⏭ {counts.get('skipped', 0)}"
        )
    if cancelled:
        lines.append("")
        lines.append("➡️ Снова /playlists — продолжит с checkpoint.")
    lines.append("")
    lines.append("ℹ️ /status")
    return "\n".join(lines)


def playlists_failed_text(reason: str) -> str:
    return f"❌ {reason}\n\n→ /playlists"
