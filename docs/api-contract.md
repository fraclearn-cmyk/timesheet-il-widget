# API-контракт виджета

Статус: целевой JSON-контракт, зафиксированный в фазе 0. Он задаёт границу следующих
фаз, но не означает, что legacy endpoint-ы уже соответствуют ему. Identity создаётся
из проверенного server-side OAuth context и, для widget-запросов, проверенного
одноразового JWT amoCRM; параметры account/user из widget browser не являются
доказательством личности.

Все ошибки имеют форму:

```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "У вас нет доступа к этому разделу.",
    "request_id": "req_01..."
  }
}
```

Для отсутствующего OAuth token применяется `AMOCRM_TOKEN_MISSING`, для отклонённого или
просроченного token — `AMOCRM_TOKEN_EXPIRED`; оба не могут подменяться browser ID.
Live refresh grant подтверждён как JSON response HTTP 200 с полями `access_token`,
`refresh_token`, `expires_in`, `server_time`, `token_type`. При rotation backend должен
атомарно сохранить обе token-пары до использования нового access token.

## Авторизация запросов виджета

На `GET/PUT /api/v1/settings/snapshot` виджет вызывает Web SDK
`this.$authorizedAjax({url, method, ...})`. По [официальной механике Web SDK](https://www.amocrm.ru/developers/content/web_sdk/mechanics)
amoCRM сама добавляет `X-Auth-Token`; backend разрешает CORS для доверенного origin
аккаунта. Виджет не копирует заголовок вручную и не передаёт браузерный OAuth
`access_token`/`refresh_token`. По [описанию одноразового токена](https://www.amocrm.ru/developers/content/oauth/disposable-tokens)
это JWT с подписью HS256 на секретном ключе интеграции: проверяются `iss`, `aud`,
`jti`, `iat`, `nbf`, `exp`, `account_id`, `user_id`, `client_uuid`; issuer должен быть
доверенным tenant origin, audience — настроенным адресом backend, UUID интеграции —
ожидаемым. Затем backend сверяет аккаунт с OAuth connection, актуального пользователя
и его права на каждом привилегированном запросе. Отсутствие/некорректность токена
не заменяется `AMOCRM.constant(...)`, browser ID или сохранённой ролью.

`GET /api/v1/settings/snapshot` возвращает `revision`, `settings`, полный список
`groups` и `users`. `PUT` атомарно принимает те же четыре верхнеуровневых поля:
`revision` защищает от устаревшей записи; новая группа задаётся `client_key`,
существующая — `id`; пользователь ссылается на неё через `client:<key>` либо
`id:<id>`. Ответ `PUT` — новый канонический snapshot, который UI принимает без
догадок о созданных ID. `track_time` и `hide_widget` независимы. Сервер повторно
проверяет права, полноту списка пользователей, tenant scope и инварианты группы.

## Контекст

`GET /api/v1/me`

```json
{
  "account_id": 123,
  "user": {
    "amocrm_id": 456,
    "name": "Иван Иванов",
    "role": "employee"
  },
  "permissions": {
    "can_configure": false,
    "can_view_all_groups": false,
    "can_view_own_group": false
  }
}
```

`account_id` и `amocrm_id` получают из проверенного OAuth/account context. `role` —
локальная policy mapping. Начальный read-only этап controlled live spike подтвердил HTTP 200 для `/api/v4/account`
и `/api/v4/users`, а также source fields `current_user_id`, user `id` и object `rights`.
`rights` содержит entity/access flags, `group_id`, `is_admin`, `role_id` и `status_rights`;
значения не сохранялись. Это не подтверждает mapping amoCRM rights в локальный role.
Backend повторно проверяет действующий OAuth token, account context и актуальные права
amoCRM на **каждом** запросе. Любой privileged route (настройки, группы, team, timeline,
reports и export) обязан выполнять эту server-side проверку до local RBAC policy; browser
`account_id`, `user_id`, `role` и ранее закэшированные права не могут её заменить.

## Рабочие статусы

`GET /api/v1/timesheet/my-status` возвращает:

```json
{
  "session_id": "ws_123",
  "status": "working",
  "started_at": "2026-09-11T08:00:00Z",
  "ended_at": null,
  "break_seconds": 0
}
```

`POST /api/v1/timesheet/start-work`, `/start-break`, `/end-break`, `/finish-work`
принимают `{ "idempotency_key": "uuid" }` и возвращают поля выше плюс `message`.
Допустимые статусы: `not_started`, `working`, `on_break`, `finished`. Неразрешённый
переход возвращает `STATUS_TRANSITION_INVALID`; повтор с тем же idempotency key возвращает
первый результат.

## Настройки

`GET /api/v1/settings` и `PUT /api/v1/settings` работают с настройками аккаунта и групп;
`GET /api/v1/settings/users`, `PUT /api/v1/settings/users/{amocrm_user_id}` — с
настройкой сотрудника:

```json
{
  "groups": [
    {
      "id": 10,
      "timezone": "Europe/Minsk",
      "workday_start": "09:00:00",
      "workday_end": "18:00:00"
    }
  ],
  "users": []
}
```

```json
{
  "track_time": true,
  "hide_widget": false,
  "group_id": 10
}
```

Группы обслуживают `GET/POST /api/v1/settings/groups`,
`PUT/DELETE /api/v1/settings/groups/{group_id}`. `hide_widget` не отключает `track_time`.
Все timestamps в хранилище и JSON передаются в UTC (`Z`). Calendar date, границы
`date_from/date_to`, timeline и строки отчёта вычисляются и отображаются в timezone группы,
а не в timezone аккаунта, браузера или пользователя; локальные границы периода сначала
конвертируются в UTC.

## Команда и timeline

`GET /api/v1/team/status` возвращает только сотрудников, видимых по policy роли.

```json
{
  "items": [
    {
      "amocrm_user_id": 456,
      "name": "Иван Иванов",
      "group_id": 10,
      "status": "working",
      "last_confirmed_activity_at": "2026-09-11T08:24:00Z"
    }
  ],
  "page": 1,
  "total": 1
}
```

`GET /api/v1/team/{amocrm_user_id}/activity?date_from=&date_to=` возвращает интервалы:

```json
{
  "started_at": "2026-09-11T08:10:00Z",
  "ended_at": "2026-09-11T08:24:00Z",
  "kind": "confirmed",
  "source": "crm_event",
  "event_type": "lead_status_changed",
  "object_type": "lead",
  "object_id": 1001,
  "duration_source": "calculated"
}
```

`kind=confirmed` разрешён только для полноатрибутированного CRM event или live-validated
call. Неизвестные данные хранятся как `incomplete_event` и не окрашивают timeline как
подтверждённую активность.

Controlled `[TEST CODEX]` actions дали HTTP 200 для `GET /api/v4/events?limit=250&page=1`.
Наблюдались только `contact_added`, `company_added`, `lead_added`, `entity_linked`,
`task_added`, `common_note_added`, `name_field_changed`; это не полный catalog amoCRM.
Observed event shape содержит string `id`/`type`, integer `created_at`/`created_by`/
`entity_id`, string `entity_type`, array `value_before`/`value_after`, а также
`_links.self` и `_embedded.entity`. Author, timestamp, entity и link реально присутствовали.

Normalizer принимает observed shape с opaque string `id` (локальная защитная граница:
1–128 ASCII символов `A-Z`, `a-z`, `0-9`, `_`, `-`; не заявленный формат всех amoCRM IDs).
`created_at`, `created_by`, `entity_id` — positive integer, timestamp должен представляться
как UTC datetime. Разрешены только наблюдённые пары: `contact_added`/`contact`,
`company_added`/`company`, `lead_added`/`lead`, `entity_linked`/`contact|company|lead`,
`task_added`/`task`, `common_note_added`/`lead`, `name_field_changed`/`lead`.

`object_url` берётся из `_embedded.entity._links.self.href`: это реально наблюдённый
API URL `/api/v4/{contacts|companies|leads|tasks}/{entity_id}`, **не URL UI-карточки**.
Embedded `id` должен совпадать с `entity_id`; plural resource path соответствует singular
`entity_type`. Top-level `_links.self.href` ведёт на `/api/v4/events/{id}` и не используется
как ссылка объекта. Обе ссылки обязаны быть HTTPS на одном разрешённом amoCRM/Kommo tenant,
с точным path, без credentials, port, query, fragment или URL-normalization tricks.
Adapter не привязывает tenant к OAuth account: вызывающий ingestion обязан получать payload
из проверенного server-side account context. UI card routing требует отдельного подтверждения.

Сохранена отдельная mock-only совместимость: positive integer `id`,
`lead_status_changed`/`leads`, отсутствие `_embedded`, top-level self строго
`/leads/detail/{entity_id}`. Этот mock не подтверждает live поддержку такого type.
Любая неизвестная пара, некорректный ID/author/timestamp/entity или ссылка даёт
`incomplete_event`, не исключение. Синтетическая fixture воспроизводит только нужную
проекцию подтверждённых field names/types, не содержит live payload или реальных IDs.
Read-only re-check 11 test events дал 2 `confirmed`, 9 `incomplete_event` из-за
nonpositive `created_by`; string IDs и entity links у всех 11 валидны. Integer author field
сам по себе не подтверждает личность сотрудника, поэтому fallback сохраняется.

Events response показал `_page` и `_links` без `next`; `page=2` дал 204. Это не доказывает
general multi-page traversal. Для 10 target events на contact/company/lead не наблюдалось
duplicate/new string ID в three polls за 0/2/6 секунд; это не является delivery guarantee.
Live `GET /api/v4/calls?limit=1&page=1` вернул 405, так что call reader contract и
`source=call` остаются недоступными до отдельной проверки.

Mouse/keyboard без CRM event образует только нейтральный интервал, например:

```json
{
  "started_at": "2026-09-11T08:24:00Z",
  "ended_at": "2026-09-11T08:29:00Z",
  "kind": "unconfirmed",
  "source": "browser_input",
  "duration_source": "observed"
}
```

`kind=unconfirmed`, `source=browser_input` и `kind=idle`,
`source=no_confirmed_crm_event` отображаются нейтрально, не как подтверждённая (зелёная)
работа, и не увеличивают `work_seconds` в timeline, reports или export. Только
`kind=confirmed`, `source=crm_event|call` может учитываться как подтверждённая работа.

## Отчёт и экспорт

`GET /api/v1/reports/detailed?date_from=&date_to=&group_id=&user_id=&page=` возвращает
пагинированный табель:

```json
{
  "items": [
    {
      "amocrm_user_id": 456,
      "date": "2026-09-11",
      "started_at": "2026-09-11T08:00:00Z",
      "ended_at": "2026-09-11T17:00:00Z",
      "work_seconds": 28800,
      "break_seconds": 3600,
      "late_seconds": 0,
      "status": "finished"
    }
  ],
  "page": 1,
  "total": 1
}
```

Период более трёх месяцев возвращает `REPORT_RANGE_LIMIT`.
`POST /api/v1/reports/export-excel` возвращает XLSX табель с
`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`;
activity intervals и raw CRM events в XLSX не включаются.

## Фактическое состояние реализации

Существующие `/api/v1/sessions/*`, `/api/v1/reports/*` и `/api/v1/excel/*` — legacy routes
с другим URL, параметрами и частью доверенных headers. Они не могут считаться реализацией
этого контракта до отдельных endpoint/integration tests в следующих фазах.
