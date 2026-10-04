# Отчёт о приёмке Phase 9

Дата среза: 2026-10-04

Проверяемая база: `d445ec6`

Последний проверенный commit перед этим отчётом: `ac00863`

Этот документ разделяет три вида доказательств:

- **LOCAL PASS** — проверено автоматическими тестами или чтением текущего репозитория;
- **NOT RUN (external)** — требует GitHub runner, Docker в целевой среде или тестового аккаунта amoCRM;
- **PARTIAL** — локальный защитный контракт подтверждён, но реальное поведение внешней системы ещё не проверено.

Локальные fixtures и mock-ответы не считаются доказательством полного контракта amoCRM. Числа ниже взяты только из зафиксированных результатов в `Plan.md` и соответствующих коммитов. Свежий полный gate всей фазы выполняется отдельно в Task 5.

## Сопоставление восьми пунктов Phase 9

### 1. Сценарий сотрудника

**Статус: LOCAL PASS.**

- Автоматическое доказательство: `backend/tests/e2e/test_user_scenarios.py::test_employee_hidden_visible_lifecycle_and_same_day_restart` проверяет независимые `track_time`/`hide_widget`, start → break → resume → finish и повторный start только при разрешении группы. `frontend/tests/e2e.spec.js` проверяет тот же stateful UI, очистку и восстановление без ложного статуса «Работаю».
- Commit: `a005cc6` (backend), `09b21f5` и исправление review `50cdb2c` (browser). Зафиксированный результат Task 1: `5 passed`, relevant-набор `185 passed`, review-набор `70 passed`; Task 2: общий Node `112 passed`, Playwright `27 passed`.
- Ручной локальный сценарий (**NOT RUN в Task 4**): открыть fixture-сценарий сотрудника, включить/скрыть интерфейс и пройти пять команд в указанном порядке; после `destroy/init` при недоступном backend элементы управления не должны показываться как работающие.
- Внешнее доказательство: **NOT RUN** — тот же сценарий внутри реального iframe amoCRM с `$authorizedAjax`, реальными callbacks и CORS.

### 2. Сценарий руководителя

**Статус: LOCAL PASS.**

- Автоматическое доказательство: `test_manager_is_limited_to_assigned_group_and_employee_detail` проверяет только назначенную группу, запрет собственного detailed activity и отказ для чужой группы/сотрудника. Browser-тест `manager and admin affordances cannot manufacture access outside server scope` проверяет, что подделанная DOM-кнопка не создаёт запрос; серверная policy остаётся источником прав.
- Commit: `a005cc6`, `09b21f5`, `50cdb2c`; результаты входят в те же подтверждённые Task 1/2 наборы.
- Ручной локальный сценарий (**NOT RUN в Task 4**): войти fixture-руководителем, открыть мониторинг и отчёты, убедиться, что доступны только участники его группы, а ручная подстановка чужого ID завершается отказом backend.
- Внешнее доказательство: **NOT RUN** — mapping реальных `rights`/`role_id` amoCRM в локальную роль руководителя.

### 3. Сценарий администратора

**Статус: LOCAL PASS.**

- Автоматическое доказательство: `test_admin_configuration_monitoring_report_and_safe_excel` связывает пользователей, группы, расписание, политику restart, мониторинг, detailed report и XLSX; формулоподобное имя сохраняется как текст. `test_same_external_user_is_isolated_across_all_40_tenant_apis` создаёт 40 независимых tenant-сессий при одинаковом внешнем user ID.
- Commit: `a005cc6`; зафиксированный Task 1 E2E результат — `5 passed`.
- Ручной локальный сценарий (**NOT RUN в Task 4**): сохранить snapshot с revision, открыть мониторинг и отчёт, скачать XLSX и проверить, что формула не исполняется, а данные соседнего аккаунта отсутствуют.
- Внешнее доказательство: **NOT RUN** — реальные настройки amoMarket, callback сохранения и server-side role mapping в тестовом аккаунте.

### 4. Активность за семь дней, tooltip, zoom, пустые интервалы и fullscreen

**Статус: LOCAL PASS.**

- Автоматическое доказательство: browser-наборы `frontend/tests/monitoring.spec.js`, `activity-tracker.spec.js` и общий Phase 9 Playwright gate проверяют семидневное окно, tooltip, zoom, пустые участки, fullscreen и Escape. Phase 9 browser acceptance также проверяет manager/admin affordances и clean lifecycle.
- Commit: основная реализация `773e844`, `b43883f`; Phase 9 повторная приёмка `09b21f5` и `50cdb2c`. Зафиксированный общий результат Task 2 — Playwright `27 passed`.
- Ручной локальный сценарий (**NOT RUN в Task 4**): открыть fixture-мониторинг, выбрать сотрудника, навести курсор на зелёный интервал, изменить масштаб, проверить gap, полноэкранный режим и закрытие по Escape.
- Внешнее доказательство: **NOT RUN** — размеры, clipping, фокус и стили внутри реального iframe amoCRM.

### 5. События, звонки, дубликаты, задержка и неизвестные типы

**Статус: PARTIAL LOCAL; обязательный live gate NOT RUN. Пункт в `Plan.md` должен оставаться незакрытым.**

- Автоматическое доказательство локального защитного контракта: `test_phase5_pipeline_is_deduplicated_bounded_and_fail_closed`, тесты catalog/checkpoint/replay в `test_activity_ingestion.py`, recovery/replay для 40 аккаунтов в `test_failure_recovery.py`, а также worker-тесты для 40 аккаунтов. Они проверяют account-scoped catalog, неизвестный тип как incomplete, complete/incomplete call fixtures, дедупликацию, pagination checkpoint, replay и изоляцию.
- Commit/evidence: базовая pipeline-приёмка завершена в `c53f271`; recovery — `5d6200a`; Phase 9 повторная консолидация — `c48bcba`. Зафиксированный Task 2 PostgreSQL-набор ingestion/replay/calls/unknown/40-account — `73 passed`.
- Ручной локальный сценарий (**NOT RUN в Task 4**): просмотреть сохранённые строки raw/normalized для fixture неизвестного события и неполного звонка; повторная доставка не должна создавать вторую запись или сдвигать checkpoint через ошибочную страницу.
- Внешнее доказательство: **NOT RUN** — полный текущий каталог типов, реальная pagination, фактическая delivery latency и читаемый источник звонков. Ранее наблюдались только 7 типов/11 тестовых событий на одной странице, а `GET /api/v4/calls` вернул `405`; это не закрывает пункт.

### 6. Русские ошибки и безопасные технические логи

**Статус: LOCAL PASS.**

- Автоматическое доказательство: `test_acceptance_failure_matrix_has_safe_correlated_contracts` проверяет буквальные русские сообщения для 401/403/409/422/429/500, `Retry-After`, совпадение `X-Request-Id` с логом, отсутствие секрета и safe readiness 503. Дополнительные контракты находятся в `test_request_observability.py` и `test_security.py`.
- Commit: `a005cc6`; инфраструктура ошибок/логов — `b5f1be9`. Результат входит в Task 1 E2E `5 passed` и relevant `185 passed`.
- Ручной локальный сценарий (**NOT RUN в Task 4**): вызвать безопасную ошибку, сверить ID в заголовке, JSON-теле и структурированном логе; token, пароль, webhook URL и traceback не должны появиться.
- Внешнее доказательство: **NOT RUN** — поиск того же request ID в production log collector через HTTPS ingress.

### 7. README, API, configuration и deployment

**Статус: LOCAL PASS.**

- Доказательство: обновлены `README.md`, `docs/API.md`, созданы `docs/CONFIGURATION.md` и `docs/DEPLOYMENT.md`; описаны актуальные маршруты, роли, настройки, backup, stamped `010` preflight, миграция до `014`, Docker/readiness, rollback и 40-account границы.
- Commit: `19d6571`; фиксация завершения Task 3 — `ac00863`.
- Проверка репозитория: 62 документированных route были сопоставлены OpenAPI, env/settings coverage полное, broken links — `0` (зафиксировано в `Plan.md`).
- Ручная проверка репозитория (**PASS**): относительные ссылки этого отчёта и release checklist разрешаются в существующие файлы; test IDs и health routes сопоставлены текущему коду. Docker-команды относятся к внешнему gate.
- Внешнее доказательство: **NOT RUN** — команды Docker и целевой deployment из документа ещё не выполнены.

### 8. Release checklist и ограничения amoCRM

**Статус: LOCAL PASS для документа; внешние release gates остаются NOT RUN.**

- Доказательство: `docs/release-checklist.md` содержит decision rule и отдельные evidence slots для backup/restore, stamped `010` preflight, единственной головы `014`, 40 аккаунтов, секретов, GitHub CI, Docker/readiness, controlled live amoCRM, rollback/recovery и ZIP hash/content.
- Источник ограничений: `docs/amocrm-integration-limits.md` и `docs/DEPLOYMENT.md`; актуализация конфигурации/deployment — `19d6571`.
- Ручная проверка документа (**PASS**): checklist не содержит заранее отмеченных пунктов, а правило решения запрещает `GO` без заполненных обязательных evidence slots.
- Внешнее доказательство: **NOT RUN** — CI runner, target Docker и controlled live amoCRM.

## Известные ограничения amoCRM

1. **OAuth, scopes и роли.** Refresh token локально покрыт тестами, но точный production redirect, configured scopes/permissions, одноразовый `X-Auth-Token` и mapping реальных `rights`/`role_id` в Admin/руководителя/сотрудника должны быть подтверждены в контролируемом аккаунте. До этого browser ID не считается identity, а привилегированные действия закрываются по умолчанию.
2. **Callbacks, настройки, CORS и iframe.** Локально реализованы native settings и lifecycle, но реальная последовательность `render/init/bind_actions/settings/onSave/destroy`, ожидание асинхронного `onSave`, `$authorizedAjax`, origin/CORS, стили, clipping и focus внутри iframe не проверены.
3. **Каталог событий, pagination и latency.** Наблюдение 7 типов/11 событий не доказывает полный каталог. Полная pagination, неизвестные production-типы и фактическое время доставки должны измеряться на контролируемых действиях с записью page/link/timestamps; локальный p95 API не является latency amoCRM.
4. **Звонки.** Читаемый источник звонков не подтверждён: ранее `/api/v4/calls` вернул `405`. Пока не доказаны endpoint и поля author/direction/duration/card, opaque call payload остаётся incomplete и не создаёт подтверждённый рабочий интервал.

## Сводка release gates

| Gate | Статус на дату отчёта | Где записать доказательство |
|---|---|---|
| Локальные Phase 9 Task 1–3 | **PASS** | `Plan.md`, commits `a005cc6..ac00863` |
| Свежий полный Phase 9 gate | **NOT RUN в Task 4** | Task 5 и итоговый раздел `Plan.md` |
| GitHub Actions на выпускаемом commit | **NOT RUN (external)** | `docs/release-checklist.md` |
| Docker build/up/readiness целевой среды | **NOT RUN (external)** | `docs/release-checklist.md` |
| Controlled live amoCRM | **NOT RUN (external)** | `docs/release-checklist.md` |

Локальный результат разрешает продолжить к общему Task 5 gate. Production-выпуск пока не разрешён.
