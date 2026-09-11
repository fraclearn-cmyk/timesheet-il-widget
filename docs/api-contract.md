# API-контракт виджета

Статус: целевой JSON-контракт, зафиксированный в фазе 0. Он задаёт границу следующих
фаз, но не означает, что legacy endpoint-ы уже соответствуют ему. Identity создаётся
только из server-side OAuth context; параметры account/user из widget browser не являются
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
локальная policy mapping; её источник в amoCRM не подтверждён до live spike.

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

`GET /api/v1/settings` и `PUT /api/v1/settings` работают с настройками аккаунта;
`GET /api/v1/settings/users`, `PUT /api/v1/settings/users/{amocrm_user_id}` — с
настройкой сотрудника:

```json
{
  "timezone": "Europe/Minsk",
  "default_workday_start": "09:00:00",
  "default_workday_end": "18:00:00",
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
