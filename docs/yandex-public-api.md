# Yandex Music — official public API (A0 трек 2)

Дата: 2026-08-22.  
Вопрос: можно ли для Telegram-бота читать библиотеку пользователя **официальным** API и токеном своего OAuth-приложения (`music:api-public`)?

Context7 в этой сессии недоступен. Источники: [Яндекс ID](https://yandex.ru/dev/id/doc/ru/), публичный паспорт OAuth-приложения, каталог [yandex.ru/dev](https://yandex.ru/dev/), документация `yandex-music`, live A0 трек 1.

Токены в этот файл не копировать.

---

## Короткий вывод

**Нет. Usable official Music API для стороннего бота (liked tracks / playlists / ISRC) не найдено.**

- Свой token со scope `music:api-public` — валидный Яндекс OAuth token.
- Он годится для **Яндекс ID** (`login.yandex.ru/info`), не для библиотеки Музыки.
- `api.music.yandex.net` принимает только token official Music client (`music:read` / `music:write` / `music:content`).
- В каталоге Яндекса для разработчиков нет продукта «Yandex Music Web API» с методом «получить лайки пользователя».

Личный CLI продолжает unofficial implicit token. Публичный бот на том же пути — ToS-риск; легальной альтернативы сейчас нет.

---

## 1. Что вообще официально документировано

### Яндекс ID / OAuth

Документация: [yandex.ru/dev/id](https://yandex.ru/dev/id/doc/ru/).

Официальный обмен token → профиль:

```text
GET https://login.yandex.ru/info?format=json
Authorization: OAuth <token>
```

Это API **профиля** (id, логин, имя, email — по scopes приложения), не каталог и не библиотека Музыки.

Проверка у себя (логин не печатается):

```bash
uv run yandex-spike probe-id
```

### Каталог yandex.ru/dev и «музыка»

Поиск по официальному dev-порталу даёт навыки Алисы (TTS-звуки), не API библиотеки Яндекс Музыки.

Отдельного SDK «Yandex Music Official» для third-party нет.

---

## 2. Scope своего приложения vs official Music app

Публичный паспорт official-like client  
`GET https://oauth.yandex.ru/client/23cabbbdc6cd418abb4b39c32c41195d/info`  
(это не секрет: endpoint описан в [документации OAuth](https://yandex.ru/dev/id/doc/ru/codes/code-url)):

| Поле | Значение |
|------|----------|
| name | Яндекс.Музыка |
| is_yandex | true |
| callback | `https://music.yandex.ru/` |
| music scopes | `music:content`, `music:read`, `music:write` |

Локализованные подписи official app:

- `music:content` — каталог Яндекс.Музыки
- `music:read` — чтение плейлистов
- `music:write` — изменение плейлистов

Своё приложение YaSpotSurfer регистрировали со scope **`music:api-public`** (лейбл в кабинете: «Использование API Яндекс.Музыки»). Это **другой** scope: его нет в паспорте official app.

Повторить паспорт своего приложения (подставьте client_id, не коммитьте ответ, если не хотите светить id):

```text
https://oauth.yandex.ru/client/<YANDEX_CLIENT_ID>/info
```

Или:

```bash
uv run yandex-spike oauth-app-info
```

(команда смотрит только official-like client_id, без секретов).

Неизвестно точно, для какого внутреннего/партнёрского API заведён `music:api-public`: публичного каталога методов под него нет. Уверенно можно сказать только: **на `api.music.yandex.net` этот token не принимается** (live HTTP 403, A0 трек 1).

---

## 3. Кандидатные host и что с ними стало

| Host | Статус | Результат |
|------|--------|-----------|
| `oauth.yandex.ru` | официальный | свой app успешно меняет code→token |
| `login.yandex.ru` | официальный Яндекс ID | ожидаемо принимает любой валидный OAuth token |
| `api.music.yandex.net` | private client API | own-app 403; official-like 200 |
| community «Open API» swagger | неофициальный | тот же `api.music.yandex.net` |

Другого документированного host вида `api.music.yandex.ru/public/...` не найдено.

---

## 4. Последствия для этапов B и C

| Сценарий | Решение |
|----------|---------|
| Личный CLI (A) | unofficial official-like token, файл `.data/yandex-token-music.json` |
| Публичный Telegram-бот | **нет легального read-API**. Варианты: бот только для себя / закрытая бета с дисклеймером; ждать официальный API; не выпускать бота |
| Matching / ISRC | только через unofficial Music API (A1+) |

Архитектуру не менять: весь Yandex остаётся за `YandexMusicProvider`, чтобы смена API не протекла в matching.

---

## 5. Чего этот шаг намеренно не делает

- не чинит snapshot библиотеки (A1);
- не вызывает liked/playlists;
- не предлагает password-grant или копирование client_secret official app в наш код.
