# Yandex Music auth — исследование A0 (трек 1)

Дата фиксации: 2026-08-22.  
Библиотека: `yandex-music==3.0.0`.  
Context7 на момент работы недоступен (только `mcp_auth`); сверка шла по исходникам установленной библиотеки, [документации yandex-music](https://ym.marshal.dev/token/) и [Яндекс ID / OAuth](https://yandex.ru/dev/id/doc/ru/).

Токены, `Authorization` и содержимое `.env` в этот файл не копировать.

---

## 1. Что вызывает `Client.init()`

`Client.init()` живёт в `AccountMixin` и делает:

1. `GET {base_url}/account/status`
2. кладёт ответ в `client.me`
3. если есть `me.account`, выставляет `client.account_uid`

`base_url` по умолчанию:

```text
https://api.music.yandex.net
```

Итоговый URL:

```text
GET https://api.music.yandex.net/account/status
```

401/403 библиотека превращает в `UnauthorizedError`.

---

## 2. Какие заголовки шлёт библиотека

`yandex_music.utils.request_base.RequestBase`:

```text
X-Yandex-Music-Client: YandexMusicAndroid/24023621
User-Agent: Yandex-Music-API
Authorization: OAuth <access_token>
Accept-Language: ru
```

Формат авторизации — именно `OAuth <token>`, не `Bearer`.

Таймаут HTTP по умолчанию — 5 секунд (это уже ловили на `device_auth()`).

---

## 3. Какие auth flow ожидает `yandex-music` 3.0.0

Библиотека **не** умеет authorization code flow своего приложения. Она ждёт готовый Music-совместимый `access_token` в конструкторе `Client(token)`.

Встроенные способы получить такой токен (документация библиотеки):

1. **OAuth Device Flow** — `Client.device_auth()`  
   `POST https://oauth.yandex.ru/device/code` и `POST https://oauth.yandex.ru/token`  
   с **встроенным client_id официального Android-приложения**  
   `23cabbbdc6cd418abb4b39c32c41195d`.
2. **Implicit OAuth в браузере** с тем же client_id:  
   `https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d`  
   редирект вида `https://music.yandex.ru/#access_token=...`.  
   Fragment на сервер не уходит — токен только из адресной строки.
3. Сторонние «доставалки» токена официального клиента.

Цитата документации библиотеки: **«Своё OAuth-приложение создать нельзя»** — в смысле «нельзя получить токен, который примет Music API».

Уже проверено ранее (ТЗ §11–14, не повторять):

- `device_auth()` у нас упирается в timeout 5s / `invalid_client` на чужом device flow;
- сеть до `oauth.yandex.ru` жива;
- authorization code + localhost у official-like client не работает (чужой `redirect_uri`);
- implicit с этим client_id **выдаёт** `#access_token`.

---

## 4. Чем свой token отличается от нужного Music API

Своё приложение YaSpotSurfer:

- scope `music:api-public`;
- authorization code + `http://127.0.0.1:8765/callback`;
- `POST /token` успешно отдаёт `access_token` (и обычно `refresh_token`);
- тот же token на `GET https://api.music.yandex.net/account/status` → **401**.

Вывод: это валидный **Яндекс ID / OAuth token своего client_id**, но не token, который принимает **private** host `api.music.yandex.net`.

Гипотеза (подтверждается документацией библиотеки, live-проверка implicit — командой `auth-implicit`):

```text
токен своего приложения  ≠  токен official Music client
```

Сравнивать токены только через fingerprint (`probe`): длина, JWT-подобность, наличие refresh, `expires_in`. Сами значения не логировать.

Два файла специально разделены:

| Файл | Источник | Ожидание |
|------|----------|----------|
| `.data/yandex-token.json` | своё приложение | OAuth ок, Music API 401 |
| `.data/yandex-token-music.json` | implicit official-like | кандидат в рабочий Music token |

---

## 5. Официальный endpoint для `music:api-public`

Публичная документация [Яндекс ID](https://yandex.ru/dev/id/doc/ru/) описывает OAuth и API профиля (логин, имя, email). Отдельного документированного host «Yandex Music Public API», который принимает token своего приложения и отдаёт liked tracks / playlists, **не найдено**.

`api.music.yandex.net` — reverse-engineered private API клиентов Музыки. Scope `music:api-public` в кабинете OAuth существует, но на этот host наш token не принимается.

Полный разбор, есть ли вообще usable official Music API для бота — **этап A0 трек 2**, этот документ его не закрывает.

---

## 6. Можно ли использовать implicit token official client

Для **личного CLI** — технически да, это штатный обходной путь библиотеки.

Риски:

- ToS / использование чужого OAuth client_id;
- token может отзываться, Device/implicit могут ломаться;
- для публичного Telegram-бота это плохая юридическая основа.

Правило проекта: unofficial token — только локальный CLI; для бота параллельно ищем official API (трек 2). Не коммитить token. Не логировать `Authorization`.

---

## 7. Как проверять локально

```bash
uv run yandex-spike probe
uv run yandex-spike auth-implicit
```

`probe` печатает только fingerprint и результат `GET /account/status` + `Client.init()`. Повторный live-запуск `probe` на реальном own-app token в сессии A0 не делался; 401 на этом токене зафиксирован ранее (ТЗ §16).

`auth-implicit` открывает браузер; нужно вставить полный redirect URL с `#access_token=...` (страница редиректит быстро — при необходимости Network throttling в DevTools).

`auth-app` — старый flow своего приложения, для сравнения. На `Client.init()` ожидается 401.

Выгрузка библиотеки в этом шаге **не делается**: в `get_library_snapshot()` ещё есть баги (`client.me()` и `users_playlists()` без `kind`) — это A1.
