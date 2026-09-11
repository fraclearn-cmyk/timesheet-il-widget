# Черновой API-контракт виджета

Контракт фиксирует границы между widget, backend и amoCRM. Поля с внешними значениями должны проходить нормализацию и валидацию.

## Контекст пользователя

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

## Рабочий статус

- `GET /api/v1/timesheet/my-status`
- `POST /api/v1/timesheet/start-work`
- `POST /api/v1/timesheet/start-break`
- `POST /api/v1/timesheet/end-break`
- `POST /api/v1/timesheet/finish-work`

Каждый POST принимает `idempotency_key` и возвращает `session_id`, `status`, `started_at`, `ended_at`, `break_seconds` и `message`.

## Настройки

- `GET /api/v1/settings`
- `PUT /api/v1/settings`
- `GET /api/v1/settings/users`
- `PUT /api/v1/settings/users/{amocrm_user_id}`
- `GET /api/v1/settings/groups`
- `POST /api/v1/settings/groups`
- `PUT /api/v1/settings/groups/{group_id}`
- `DELETE /api/v1/settings/groups/{group_id}`

Настройка пользователя:

```json
{
  "track_time": true,
  "hide_widget": false,
  "group_id": 10
}
```

## Мониторинг и активность

- `GET /api/v1/team/status`
- `GET /api/v1/team/{amocrm_user_id}/activity?date_from=&date_to=`

Интервал:

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

## Табель и экспорт

- `GET /api/v1/reports/detailed?date_from=&date_to=&group_id=&user_id=&page=`
- `POST /api/v1/reports/export-excel`

Backend отклоняет период больше 3 месяцев кодом `REPORT_RANGE_LIMIT`. Activity intervals и CRM events не входят в Excel response.

## Ошибки

```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "У вас нет доступа к этому разделу.",
    "request_id": "req_01..."
  }
}
```