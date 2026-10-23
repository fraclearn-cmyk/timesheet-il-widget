# Timesheet Retention and Manager Period Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Хранить отчётные данные табеля 365 дней, дать администратору доступ ко всему сохранённому году и разрешить ему задавать глубину просмотра общего табеля для руководителя каждой группы.

**Architecture:** Настройка `report_history_days` живёт в `widget_groups` рядом с назначением руководителя. Один серверный расчёт границ периода применяется к экранному отчёту и Excel; frontend получает те же границы из каталога команды. Ежедневный worker пакетно удаляет закрытые отчётные данные старше 365 дней, сохраняя открытые смены и конфигурацию.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL/SQLite tests, JavaScript AMD, JSDOM, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-23-timesheet-retention-and-manager-period-design.md`

## Global Constraints

- Нормализованные отчётные данные хранятся 365 календарных дней; сырые ingestion payload остаются на существующем сроке 30 дней.
- `report_history_days` имеет целое значение `1..365`, по умолчанию `365`.
- Администратор видит весь сохранённый год; руководитель — только назначенные группы и их разрешённый период.
- Для «Всех групп» руководителя применяется минимальный `report_history_days` среди доступных групп.
- Экран и Excel используют одно серверное ограничение; frontend не является границей безопасности.
- Очистка выполняется ограниченными пакетами и не удаляет открытые смены.

## Review Focus

- Граница ровно 365 дней сохраняется, 366-й день удаляется и недоступен.
- Руководитель с двумя группами не получает старые строки более разрешающей группы через режим «Все группы».
- Подмена дат или `group_id` в запросе к отчёту и Excel не обходит ограничения.
- Открытая старая смена и её связанные строки не удаляются.
- Повторный запуск пакетной очистки безопасен и не затрагивает другой аккаунт.

---

### Task 1: Настройка периода и миграция

**Files:**
- Create: `backend/migrations/versions/016_report_history_retention.py`
- Modify: `backend/app/models/widget_group.py`
- Modify: `backend/app/schemas/settings_snapshot.py`
- Modify: `backend/app/services/settings_snapshot_service.py`
- Modify: `frontend/settings/settings.js`
- Test: `backend/tests/integration/test_migrations.py`
- Test: `backend/tests/api/test_settings.py`
- Test: `frontend/tests/settings-controller.test.js`

**Interfaces:**
- Produces: `WidgetGroup.report_history_days: int`; `SettingsGroup.report_history_days`; `SettingsGroupUpdate.report_history_days`.

- [x] **Step 1:** Добавить падающие migration/API/frontend-тесты значения по умолчанию `365`, границ `1..365`, сохранения и сериализации поля.
- [x] **Step 2:** Запустить целевые тесты и подтвердить ожидаемые падения из-за отсутствующего поля.
- [x] **Step 3:** Добавить миграцию, модель, схемы, сервис снимка и числовое поле «Период табеля руководителя, дней» в карточку группы.
- [x] **Step 4:** Запустить целевые и связанные тесты до зелёного результата.
- [x] **Step 5:** Обновить `Plan.md` и зафиксировать задачу коммитом.

### Task 2: Единые серверные границы отчёта

**Files:**
- Create: `backend/app/core/report_access_period.py`
- Modify: `backend/app/services/timesheet_report_service.py`
- Modify: `backend/app/services/team_service.py`
- Modify: `backend/app/schemas/team.py`
- Test: `backend/tests/api/test_reports.py`
- Test: `backend/tests/api/test_team.py`

**Interfaces:**
- Consumes: `WidgetGroup.report_history_days`.
- Produces: `ReportAccessPeriod(min_date, max_date, history_days)` и серверную проверку `require_report_period(...)`; каталог команды возвращает общие и групповые границы.

- [x] **Step 1:** Добавить падающие тесты полного года администратора, периода руководителя выбранной группы, минимального периода «Всех групп» и запрета чужой группы.
- [x] **Step 2:** Подтвердить RED на целевых backend-тестах.
- [x] **Step 3:** Реализовать единый расчёт и применить его перед выборкой `list_rows` и `export_rows`; добавить метаданные периода в ответ каталога.
- [x] **Step 4:** Запустить целевые и полный backend-набор до зелёного результата.
- [x] **Step 5:** Обновить `Plan.md` и зафиксировать задачу коммитом.

### Task 3: Ограничение дат в общем табеле

**Files:**
- Modify: `frontend/reports/controller.js`
- Test: `frontend/tests/reports.test.js`
- Test: `frontend/tests/reports.spec.js`
- Test: `frontend/tests/widget-lifecycle.test.js`

**Interfaces:**
- Consumes: границы периода из каталога команды и `groups[].report_history_days`.
- Produces: поля дат с корректными `min`/`max`, автоматическое приведение периода после смены группы и понятное сообщение сервера.

- [x] **Step 1:** Добавить падающие Node/Playwright-тесты администратора, руководителя, смены группы и режима «Все группы».
- [x] **Step 2:** Подтвердить RED.
- [x] **Step 3:** Реализовать применение границ без доверия к браузерной роли и без изменения существующей пагинации/Excel payload.
- [x] **Step 4:** Запустить все frontend- и браузерные тесты до зелёного результата.
- [x] **Step 5:** Обновить `Plan.md` и зафиксировать задачу коммитом.

### Task 4: Годовая пакетная очистка

**Files:**
- Create: `backend/app/services/report_retention_service.py`
- Modify: `backend/app/services/ingestion_worker.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_report_retention.py`
- Test: `backend/tests/integration/test_ingestion_worker.py`

**Interfaces:**
- Produces: `ReportRetentionService.cleanup(now: datetime, batch_size: int) -> int`; worker запускает её ежедневно отдельно от 30-дневной raw cleanup.

- [x] **Step 1:** Добавить падающие тесты границы 365/366 дней, каскадных строк, старой открытой смены, аккаунтной изоляции, ограниченного пакета и повторного запуска.
- [x] **Step 2:** Подтвердить RED.
- [x] **Step 3:** Реализовать удаление закрытых `WorkSession` и нормализованных CRM/call/служебных данных старше границы пакетами; подключить ежедневный вызов worker.
- [x] **Step 4:** Запустить целевые и полный backend-набор до зелёного результата.
- [x] **Step 5:** Обновить `Plan.md` и зафиксировать задачу коммитом.

### Task 5: Выпуск и проверка ролей

**Files:**
- Modify: `docs/api-contract.md`
- Modify: `docs/release-checklist.md`
- Modify: `Plan.md`
- Modify: `widget/manifest.json`
- Modify: `widget/script.js`
- Modify: `validate_widget_zip.py`
- Modify: `test_widget_package.py`

**Interfaces:**
- Consumes: завершённые задачи 1–4.
- Produces: проверенный пакет следующей версии и доказательства проверки администратора/руководителя.

- [x] **Step 1:** Обновить документацию API, эксплуатации и автоматического обновления статусов в `Plan.md`.
- [x] **Step 2:** Повысить версию пакета и обновить пакетные тесты через RED→GREEN.
- [x] **Step 3:** Выполнить полные backend, frontend, Playwright, migration, package и diff проверки.
- [ ] **Step 4:** Передать полный diff независимому ревьюеру, исправить существенные замечания через RED→GREEN.
- [ ] **Step 5:** Собрать архив, применить миграцию локально, загрузить виджет и проверить роли в amoCRM; отметить фактический результат в `Plan.md` и отправить коммиты в GitHub.
