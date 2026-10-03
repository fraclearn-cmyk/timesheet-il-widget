# API виджета табеля

Базовый путь пользовательского API — `/api/v1`; Swagger UI запущенного backend доступен по `/api/docs`. На защищённых маршрутах аккаунт, пользователь и роль берутся из проверенного серверного `RequestContext`; query-параметры и данные браузера не являются основанием для доступа. Opaque webhook `/api/v1/webhooks/amocrm/{hook_id}` является отдельным публичным trigger: он ограничен по размеру и частоте, планирует авторитетный API poll и не принимает browser identity.

Все сохранённые даты выдаются как ISO 8601 UTC с `Z`. Локальные календарные даты, границы рабочего дня и семидневного окна рассчитываются в часовом поясе группы, включая ночные смены и переходы DST.

## Аутентификация и текущий пользователь

Рабочий виджет передаёт одноразовый `X-Auth-Token`. Backend проверяет HS256-подпись секретом интеграции, audience из HTTPS origin `AMOCRM_REDIRECT_URI`, client UUID, issuer и claims аккаунта/пользователя, затем сверяет активное OAuth connection и актуальное состояние amoCRM. Альтернативный `Authorization: Bearer <access-token>` также требует сохранённого активного connection и live-проверки amoCRM. Заголовки `X-User-Id`/`X-Account-Id` разрешены только тестовым adapter-ом и в production не являются способом входа.

`GET /me` возвращает проверенный account, пользователя и доступные возможности:

```json
{
  "account_id": 77,
  "user": {"amocrm_id": 100500, "name": "Анна", "role": "admin"},
  "permissions": {
    "can_configure": true,
    "can_view_all_groups": true,
    "can_view_own_group": true
  }
}
```

## Рабочий статус сотрудника

- `GET /timesheet/my-status` — подтверждённое состояние текущего пользователя;
- `POST /timesheet/start-work` — начать работу;
- `POST /timesheet/start-break` — начать перерыв;
- `POST /timesheet/end-break` — продолжить работу;
- `POST /timesheet/finish-work` — завершить рабочий день.

Каждая команда принимает новый UUID, например `{"idempotency_key":"c4ab45ef-4515-4b5f-84dc-3bead623a9c2"}`. Повтор той же команды с тем же ключом безопасно возвращает сохранённый результат; использование ключа для другого действия даёт `409 IDEMPOTENCY_KEY_REUSED`.

```json
{
  "session_id": 501,
  "status": "working",
  "started_at": "2026-09-29T06:00:00Z",
  "ended_at": null,
  "break_seconds": 0,
  "track_time": true,
  "hide_widget": false,
  "restart_allowed": false,
  "message": "Работа начата."
}
```

`track_time=false` даёт `403 TRACK_TIME_DISABLED`. Неверный переход даёт `409 STATUS_TRANSITION_INVALID`. После завершения новая сессия в тот же локальный business day разрешена только политикой группы/аккаунта.

## Настройки администратора

- `GET /settings/snapshot` — целый account-scoped снимок настроек;
- `PUT /settings/snapshot` — атомарно сохранить снимок с текущей `revision`;
- `GET /settings/users` и `GET /settings/groups` — раздельные read-only списки.

Маршруты доступны только администратору. Снимок связывает account settings, группы и пользователей: timezone, расписание, руководителя, разрешение restart, `track_time`, `hide_widget` и active membership. Клиентские новые группы связываются через `client_key`/`group_ref`; устаревшая revision возвращает конфликт. Точные поля описаны Swagger-схемой `SettingsSnapshotUpdate`.

## Роли

| Возможность | employee | manager | admin |
|---|---:|---:|---:|
| Собственный рабочий статус и команды | да | да | да |
| Снимок команды | только себя | назначенные активные группы и себя | весь текущий аккаунт |
| Детальная активность сотрудника | нет | только участник управляемой активной группы | активный пользователь своего аккаунта |
| Табель и Excel | нет | только управляемые группы | весь учитываемый аккаунт |
| Настройки групп и пользователей | нет | нет | да |

Отображение кнопки в браузере не является авторизацией: каждый доступ повторно проверяется backend.

## `GET /team/status`

Возвращает один account-scoped снимок видимых групп и сотрудников. Endpoint не делает отдельный запрос на каждого сотрудника.

Query-параметры:

- `search` — необязательный поиск по имени, пробелы по краям игнорируются, регистр не учитывается;
- `status` — одно из `working`, `on_break`, `finished`, `not_started`;
- `group_id` — внутренний ID доступной группы.

Видимость:

- `admin` видит всех активных пользователей и группы проверенного аккаунта;
- `manager` видит активных участников групп, которыми он управляет по актуальному снимку роли, а также себя;
- `employee` видит только себя;
- неактивные пользователи и членства, устаревшая роль руководителя и чужой аккаунт исключаются;
- недоступный `group_id` возвращает одинаковый `404 NOT_FOUND` без раскрытия существования группы.

Ответ:

```json
{
  "generated_at": "2026-09-29T09:00:00Z",
  "viewer": { "id": 1, "role": "admin", "can_view_activity": true },
  "groups": [
    {
      "id": 10,
      "name": "Продажи",
      "timezone": "Europe/Moscow",
      "workday_started_at": "2026-09-29T06:00:00Z",
      "workday_ended_at": "2026-09-29T15:00:00Z",
      "employee_count": 1
    }
  ],
  "employees": [
    {
      "id": 42,
      "amocrm_user_id": 100500,
      "account_id": 77,
      "name": "Анна",
      "avatar_url": null,
      "group_id": 10,
      "group_name": "Продажи",
      "timezone": "Europe/Moscow",
      "workday_started_at": "2026-09-29T06:00:00Z",
      "workday_ended_at": "2026-09-29T15:00:00Z",
      "status": "working",
      "status_since": "2026-09-29T06:00:00Z",
      "session_started_at": "2026-09-29T06:00:00Z",
      "session_ended_at": null,
      "work_seconds": 3600,
      "break_seconds": 300,
      "confirmed_seconds": 900,
      "confirmed_events": 3,
      "activity_detail_allowed": true
    }
  ],
  "totals": {
    "employees": 1,
    "working": 1,
    "on_break": 0,
    "finished": 0,
    "not_started": 0,
    "work_seconds": 3600,
    "break_seconds": 300,
    "confirmed_seconds": 900,
    "confirmed_events": 3
  }
}
```

Поле `employees[].id` — внутренний account-scoped ID. Только его можно передавать в detail endpoint. `amocrm_user_id` не заменяет внутренний ID.

## `GET /team/{target_user_id}/activity?from=YYYY-MM-DD&to=YYYY-MM-DD`

Возвращает интервалы активности для включительного диапазона от одной до семи локальных календарных дат. Оба параметра обязательны.

Доступ строже списка статусов:

- `admin` может открыть активного пользователя своего аккаунта;
- `manager` может открыть только активного участника активной группы, которой он управляет по актуальной роли;
- `employee` не может открыть detail, включая собственный;
- собственная строка руководителя без активного членства в управляемой группе также не даёт detail;
- отсутствующая, неактивная, чужая или недоступная цель всегда возвращает одинаковый `404 NOT_FOUND`.

Ответ содержит `target`, необязательную `group`, `timezone`, `from`, `to`, общие `totals` и `days`. Каждый день содержит UTC-границы локальной даты, границы смены, агрегаты и упорядоченные `intervals`.

```json
{
  "target": { "id": 42, "amocrm_user_id": 100500, "name": "Анна", "avatar_url": null },
  "group": { "id": 10, "name": "Продажи" },
  "timezone": "Europe/Moscow",
  "from": "2026-09-23",
  "to": "2026-09-29",
  "totals": { "confirmed_seconds": 900, "confirmed_events": 3, "unconfirmed_seconds": 120 },
  "days": [
    {
      "date": "2026-09-29",
      "started_at": "2026-09-28T21:00:00Z",
      "ended_at": "2026-09-29T21:00:00Z",
      "shift_started_at": "2026-09-29T06:00:00Z",
      "shift_ended_at": "2026-09-29T15:00:00Z",
      "confirmed_seconds": 900,
      "confirmed_events": 3,
      "unconfirmed_seconds": 120,
      "intervals": [
        {
          "id": 501,
          "started_at": "2026-09-29T08:00:00Z",
          "ended_at": "2026-09-29T08:00:00Z",
          "duration_seconds": 0,
          "kind": "confirmed",
          "source": "crm_event",
          "duration_source": "point",
          "event_type": "lead_status_changed",
          "object_type": "lead",
          "object_id": 123,
          "description": "Изменён статус сделки",
          "card_url": null,
          "call_direction": null,
          "call_duration_seconds": null,
          "message": null
        }
      ]
    }
  ]
}
```

Интервалы обрезаются границами запроса и при необходимости делятся по локальным датам. `duration_source=point` всегда остаётся точкой с нулевой длительностью. Только `kind=confirmed` отображается зелёным; `unconfirmed` не увеличивает подтверждённое время. Сырой payload событий в ответ не попадает.

Ошибки диапазона:

- отсутствующая или неверная дата — `422 REQUEST_INVALID`;
- `to < from` — `400 ACTIVITY_RANGE_INVALID`, «Дата окончания должна быть не раньше даты начала.»;
- более семи включительных дат — `400 ACTIVITY_RANGE_TOO_LARGE`, «Можно выбрать не больше 7 календарных дней.».

Стабильный формат ошибки:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Данные не найдены.",
    "request_id": "09b2943d-6d6a-4c07-8998-8e7e6c5d5fe7"
  }
}
```

## Клиентский polling

Виджет вызывает status через `$authorizedAjax`, не отправляет browser `account_id`, `user_id` или роль и загружает detail только для выбранного сотрудника. На dashboard действует один запрос и один timer. Успешный интервал — 30 секунд; после ошибок используется `30 → 60 → 120 → 240 → 300` секунд с jitter до 10%. В скрытой вкладке polling приостанавливается, после возврата запускается обновление, а выбранный сотрудник, открытое окно и zoom сохраняются.

Capacity-контракт проверен для 40 изолированных аккаунтов с повторяющимися внешними ID. Status использует постоянное ограниченное число SQL-запросов, detail загружается только для одного выбранного пользователя, общих tenant-кэшей и блокировок нет.

## Табель и Excel

### `GET /reports/detailed`

Возвращает табель для включительного диапазона локальных календарных дат. Обязательные query-параметры — `date_from` и `date_to`; необязательные — внутренние account-scoped `group_id`, `user_id` и `page` (по умолчанию `1`). Размер страницы всегда равен 10. `items` содержит строки текущей страницы, `total` — число всех строк после фильтров, а `totals` — суммы по всему отфильтрованному набору, а не только по странице.

Строка содержит только табельные поля: внутренний и amoCRM ID сотрудника, имя, группу и её часовой пояс, локальную дату, UTC-время начала и окончания, длительность перерывов, работы и опоздания в секундах, статус `working`, `on_break` или `finished`. Activity intervals, события, звонки, payload и ссылки на карточки в ответ не входят.

```json
{
  "items": [{
    "user_id": 42,
    "amocrm_user_id": 100500,
    "employee_name": "Анна",
    "group_id": 10,
    "group_name": "Продажи",
    "group_timezone": "Europe/Moscow",
    "date": "2026-09-29",
    "started_at": "2026-09-29T06:00:00Z",
    "ended_at": "2026-09-29T15:00:00Z",
    "break_seconds": 3600,
    "work_seconds": 28800,
    "late_seconds": 0,
    "status": "finished"
  }],
  "page": 1,
  "page_size": 10,
  "total": 1,
  "totals": {
    "work_seconds": 28800,
    "break_seconds": 3600,
    "late_seconds": 0,
    "days": 1,
    "employees": 1
  }
}
```

Доступ имеют `admin` и `manager`. Администратор видит учитываемых сотрудников своего аккаунта, руководитель — только учитываемых участников активных групп, которыми он управляет. `employee` получает `403 ACCESS_DENIED`. Недоступные `group_id` и `user_id` скрываются одинаковым `404 NOT_FOUND`; ID из браузера не определяют аккаунт или роль.

Период должен быть не короче одного дня и не выходить за включительную границу трёх календарных месяцев от `date_from` с корректным ограничением конца месяца. Обратный диапазон даёт `422 REPORT_DATE_RANGE_INVALID`, превышение — `422 REPORT_RANGE_LIMIT` с сообщением «Период отчёта не может быть больше 3 месяцев.».

### `POST /reports/export-excel`

Принимает JSON с теми же `date_from`, `date_to`, необязательными внутренними `group_id`, `user_id` и непустым уникальным списком `columns`. Разрешены только `employee`, `date`, `start`, `end`, `break`, `work`, `lateness`, `status`. Доступ и состав строк полностью совпадают с preview.

Ответ — XLSX с `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` и безопасным именем `timesheet_YYYY-MM-DD_YYYY-MM-DD.xlsx`. Время начала и окончания записывается в часовом поясе группы, длительности остаются числовыми Excel-значениями. Текст, начинающийся с `=`, `+`, `-` или `@`, экранируется от выполнения как формулы. Экспорт ограничен 10 000 строками и обрабатывает их пакетами по 250. Каждый запрос деталей ограничен 25 000 сессий или переходов; превышение возвращает контролируемый `413 REPORT_EXPORT_SOURCE_TOO_LARGE`, а превышение числа строк — `REPORT_EXPORT_TOO_LARGE`. Activity, CRM-события, звонки, сырые данные и ссылки не экспортируются.

Интерфейс «Табель» загружает справочник и запросы через `$authorizedAjax`, показывается только администратору и руководителю, поддерживает состояния загрузки, пустого результата, ошибки и повторной попытки. При закрытии окна активные запросы отменяются, обработчики удаляются, временный URL скачивания освобождается.

## Ошибки, request ID и ограничения запросов

Каждый ответ API содержит `X-Request-Id`. Если клиент передал канонический UUID не длиннее 36 символов, сервер сохраняет его; иначе создаёт новый UUID. Нормализованные ошибки повторяют это значение в `error.request_id`, и его можно сообщить администратору для поиска запроса в структурированном журнале. Специальные ошибки `PUT /settings/snapshot` сейчас возвращают `error.code/message/field` без `request_id` в JSON, но тот же correlation ID остаётся в заголовке ответа.

| HTTP | Основной публичный код | Значение |
|---:|---|---|
| `401` | `AMO_WIDGET_TOKEN_INVALID` или `AMOCRM_TOKEN_EXPIRED` | Одноразовый widget token недействителен либо OAuth-подключение надо обновить. |
| `403` | `ACCESS_DENIED` или `TRACK_TIME_DISABLED` | Роль/область не разрешает действие либо учёт сотрудника выключен. |
| `404` | `NOT_FOUND` | Объект отсутствует или скрыт политикой доступа; существование чужого объекта не раскрывается. |
| `409` | `CONFLICT`, `STATUS_TRANSITION_INVALID`, `IDEMPOTENCY_KEY_REUSED` | Состояние уже изменилось, revision устарела или ключ команды использован иначе. |
| `422` | `REQUEST_INVALID` либо route-specific code | Неверные поля, период, список колонок или references. |
| `429` | `RATE_LIMITED` | Повторять только после `Retry-After`. |
| `500` | `INTERNAL_ERROR` | Безопасное общее сообщение; traceback, token и адрес базы не выдаются. |
| `503` | readiness payload | База недоступна или schema не совпадает с текущей головой; экземпляр не готов к traffic. |

Авторизованные лимиты считаются по проверенному аккаунту и пользователю, поэтому 40 аккаунтов за одним NAT не расходуют общую завершённую квоту. До авторизации действует только ограничение одновременной работы: не более 64 запросов с одного сетевого адреса. Публичные и неизвестные маршруты, а также webhook, имеют отдельные ограниченные buckets. Webhook принимает тело не более 64 КиБ и не более 10 запросов в минуту на callback. При `429 RATE_LIMITED` клиент должен выдержать `Retry-After` и не выполнять безграничные повторы.

Эти встроенные счётчики действуют на один Python worker. При нескольких workers или экземплярах общую квоту должен обеспечивать доверенный ingress/API gateway; для авторизованных запросов он обязан сохранять tenant-разделение, а не объединять 40 аккаунтов по одному NAT.

Технические адреса состояния не входят в `/api/v1`: `GET /health` и `GET /health/live` проверяют только живой процесс, а `GET /health/ready` возвращает `200` лишь при доступной PostgreSQL и единственной актуальной голове Alembic. Порядок запуска, backup/restore и действия при сбоях описаны в [DEPLOYMENT.md](DEPLOYMENT.md).

## Текущий индекс маршрутов

Ниже перечислены маршруты, зарегистрированные текущим приложением. Поддерживаемый интерфейс виджета использует `/timesheet`, `/team`, `/settings` и строгие `/reports/detailed`/`export-excel`; остальные маршруты сохранены для существующих модулей и совместимости.

### Identity, табель и команда

```text
GET    /api/v1/me
GET    /api/v1/timesheet/my-status
POST   /api/v1/timesheet/start-work
POST   /api/v1/timesheet/start-break
POST   /api/v1/timesheet/end-break
POST   /api/v1/timesheet/finish-work
GET    /api/v1/team/status
GET    /api/v1/team/stats
GET    /api/v1/team/activity
GET    /api/v1/team/{target_user_id}/activity
GET    /api/v1/team/{target_user_id}/timeline
GET    /api/v1/team/{target_user_id}/timeline/history
POST   /api/v1/team/{target_user_id}/force-finish
```

### Настройки и справочники

```text
GET    /api/v1/settings/snapshot
PUT    /api/v1/settings/snapshot
GET    /api/v1/settings/users
GET    /api/v1/settings/groups
GET    /api/v1/categories
POST   /api/v1/categories
GET    /api/v1/categories/{category_id}
PUT    /api/v1/categories/{category_id}
DELETE /api/v1/categories/{category_id}
GET    /api/v1/departments/
POST   /api/v1/departments/
GET    /api/v1/departments/{department_id}/schedule
PUT    /api/v1/departments/{department_id}/schedule
```

### Отчёты и Excel

```text
GET    /api/v1/reports/detailed
POST   /api/v1/reports/export-excel
```

Следующие legacy report/export routes зарегистрированы и проходят router-wide `RequestContext`/scope dependency, но текущий виджет их не вызывает. Их старые payload/role semantics отличаются от строгого табеля выше; не используйте их для новой интеграции без отдельного security и product review:

```text
GET    /api/v1/reports/daily
GET    /api/v1/reports/weekly
GET    /api/v1/reports/monthly
GET    /api/v1/reports/employee/{user_id}
GET    /api/v1/reports/statistics
POST   /api/v1/reports/generate
GET    /api/v1/reports
GET    /api/v1/reports/{report_id}
DELETE /api/v1/reports/{report_id}
GET    /api/v1/reports/{report_id}/download
POST   /api/v1/excel/department
POST   /api/v1/excel/employee/{employee_id}
POST   /api/v1/excel/late-arrivals
```

### Activity, ingestion и совместимость

```text
POST   /api/v1/activity/start
POST   /api/v1/activity/stop/{activity_session_id}
POST   /api/v1/activity/switch
POST   /api/v1/activity/event
POST   /api/v1/activity/presence
GET    /api/v1/activity/current/{work_session_id}
GET    /api/v1/activity/history/{work_session_id}
GET    /api/v1/activity/events/{activity_session_id}
GET    /api/v1/activity/stats/{work_session_id}
POST   /api/v1/activity/ingestion/webhook/ensure
POST   /api/v1/webhooks/amocrm/{hook_id}
POST   /api/v1/sessions/start
POST   /api/v1/sessions/break/{user_id}
POST   /api/v1/sessions/resume/{user_id}
POST   /api/v1/sessions/finish/{user_id}
GET    /api/v1/sessions/current/{user_id}
GET    /api/v1/sessions/history/{user_id}
GET    /api/v1/sessions/{session_id}
```

KPI routes зарегистрированы под `/api/v1/kpi`: `my`, `user/{target_user_id}`, `department/{dept_id}`, соответствующие `chart/*` и `dashboard/settings` (`GET`/`PUT`). Их точную OpenAPI-схему смотрите в `/api/docs`.
