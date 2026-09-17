# Модель данных: фаза 1

`User.id` — внутренний PK. `User.amocrm_user_id` и
`User.amocrm_account_id` — внешние идентификаторы; уникальна именно их пара.
Одинаковый внешний user ID в разных аккаунтах допустим.

| Модель / поле | Значение |
|---|---|
| WorkSession.amocrm_user_id / amocrm_account_id | Внешняя пара; составной FK к User |
| GroupMember.user_id, WidgetGroup.manager_user_id | Внутренний User.id; FK также проверяет аккаунт |
| ActivityInterval.user_id | Внутренний User.id; account_id — внешний аккаунт |
| CrmEvent.user_id, CallEvent.user_id | Nullable внутренний User.id после attribution |
| CrmEvent.author_amocrm_user_id, CallEvent.author_amocrm_user_id | Исходный внешний author; NULL, 0, отрицательное число не подтверждают сотрудника |
| CrmEvent.external_id | Opaque string ID; уникален внутри аккаунта |
| CallEvent.source_event_id | Внешний string ID исходного звонка |
| WorkComment.work_session_id | Внутренний WorkSession.id |
| WorkComment.author_id, WorkSession.forced_finish_by | Legacy внутренний User.id автора/администратора; эти поля пока без FK |

Legacy JSON `WorkSessionCreate/Response.user_id` сохранён только как явно
описанный устаревающий alias внешнего amoCRM user ID. В ORM WorkSession нет
поля `user_id`, `account_id`, `status` или `session_id`: используются
`amocrm_user_id`, `amocrm_account_id`, `current_status`, `id`.
SessionService переводит legacy аргументы в эти поля. Если legacy route не
передаёт аккаунт, неоднозначный внешний user ID отклоняется.
Это разрешение идентификатора, не авторизация: OAuth/RBAC реализуется в фазе 2.

## Группы

Группа содержит аккаунт, manager reference, IANA timezone, начало/конец графика
и `is_active`. У членства есть собственный `is_active`, отдельно от `track_time`,
`hide_widget` и активности группы. Частичный unique index на `(account_id,user_id)`
с условием `is_active` допускает любую историю неактивных членств, но не два
активных. Операция выключения группы сама по себе не переписывает её членства.

## Время и подтверждение

`active_duration`, `unconfirmed_duration`, `break_duration`, `idle_duration`
хранят неотрицательные целые секунды, NOT NULL, default 0 при INSERT.
Ноль означает отсутствие накопленного времени. `CallEvent.duration_seconds=NULL`
означает неизвестную длительность; её нельзя превращать в подтверждённый звонок.

Legacy `total_work_time/total_break_time` сохранены для совместимости старых
отчётов. `total_work_time` не является доказательством подтверждённой CRM-работы.
Миграция переносит его в `unconfirmed_duration`, перерывы — в `break_duration`,
а `active_duration/idle_duration` оставляет нулевыми. Автоматический расчёт
новых счётчиков и перевод отчётов на них относятся к следующим фазам.

В БД сохраняются naive UTC timestamps согласно существующей схеме.
Factory нормализует timezone-aware timestamps в UTC. График группы — локальный
`Time` вместе с `timezone`. Persisted статусы: `working`, `break`, `finished`;
`StatusTransition` использует тот же словарь. Целевой API `on_break` пока не внедрён.

Создавать интервалы следует через `ActivityInterval.from_evidence`.
`source=unconfirmed_input` всегда создаёт `kind=unconfirmed`.
`crm_event/call` требует подходящую модель evidence, совпадение аккаунта,
внутреннего пользователя и внешнего автора, положительную attribution,
`WORKING` и отсутствие пересечения с перерывом/завершением. Неполный CRM event
и звонок без измеренной длительности не подтверждают активность.
Прямой SQL не проверяет историю статусов: её проверяет доменная factory;
DDL дополнительно ограничивает source/kind, время, account attribution и durations.

## Миграция 005

005 следует за единственной head 004. Она добавляет account-scoped связи,
явно переименовывает внешний WorkSession.user_id, исправляет membership,
CRM attribution, durations и недостающую Department.timezone.
Исходный author старых CRM/call rows сохраняется отдельно; internal attribution
разрешается только по положительному внешнему автору и совпадающему аккаунту.
Системные/неизвестные авторы остаются без пользователя и без complete CRM status.

Legacy WorkSession без соответствующего внешнего User останавливает upgrade
транзакционно с сообщением `unmapped legacy work_sessions`; пользователь/аккаунт
не выдумывается. Нарушающие новые FK/check constraints данные также требуют
предварительного исправления оператором. Рабочая база в этой фазе не мигрировалась.

Downgrade до 004 разрешён только для представимых в ней данных: операция
отказывается удалять membership history, объединять аккаунты, терять отдельные
duration counters, неизвестного автора/направление звонка или timezone.
Перед production deployment необходим обычный backup и проверка данных.

Единственное изменение старой истории: из 001 убран дублирующий `index=True`
на WorkSession.user_id, поскольку явный `op.create_index` уже создаёт этот
индекс. Без этого чистый PostgreSQL upgrade падал с DuplicateTable.

## Проверки

Из `backend`, Python 3.12:

```powershell
$env:TEST_POSTGRES_ADMIN_URL = '<URL отдельного PostgreSQL test server>'
..\.venv312\Scripts\python.exe -m pytest -q
```

Migration fixture создаёт UUID database с префиксом `timesheet_phase1_test_`,
выполняет Alembic и удаляет только созданную ею БД. Без явного
`TEST_POSTGRES_ADMIN_URL` эти тесты пропускаются. Остальные тесты не используют
application database или реальные amoCRM credentials.
