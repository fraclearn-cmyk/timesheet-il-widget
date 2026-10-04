# Release checklist

Дата подготовки: 2026-10-04

Заполняйте этот список для конкретного commit и конкретной среды. Ссылки на «последний успешный запуск» без SHA выпуска не подходят. Не помещайте секреты, token, authorization code, cookie, полный webhook URL или дамп пользовательских данных в evidence.

## Карточка выпуска

- Release commit: `________________`
- Версия/тег: `________________`
- Целевая среда: `________________`
- Ответственный: `________________`
- Окно выпуска: `________________`
- Предыдущий совместимый image/commit: `________________`
- Путь к закрытому backup storage: `________________` (без credentials)

## Правило решения

**GO** допустим, только если все пункты с пометкой **обязательно** отмечены `[x]`, каждый evidence slot заполнен проверяемым SHA/URL/временем/результатом, а открытых Critical/Important дефектов нет.

**NO-GO** обязателен, если отсутствует проверенный restore, schema preflight не согласуется с записанной ревизией, Alembic имеет не одну голову `014`, CI относится к другому commit, readiness не проходит, обнаружено смешивание аккаунтов/секретов или controlled live amoCRM не подтверждает identity и основные callbacks.

Неподтверждённый пункт не считается успешным. На момент создания документа внешние пункты ниже намеренно не отмечены.

## 1. Код и локальный gate

- [ ] **Обязательно:** release commit зафиксирован и рабочее дерево чистое, кроме явно исключённых локальных артефактов.
  - Evidence (`git rev-parse HEAD`, `git status --short`): `________________`
- [ ] **Обязательно:** Task 5 выполнил свежий полный PostgreSQL backend suite с `TEST_POSTGRES_ADMIN_URL`, все Node и Playwright тесты, package/ZIP, migration regression, Black, compileall и `git diff --check`.
  - Evidence (команды, counts, дата): `________________`
- [ ] **Обязательно:** независимый review полного Phase 9 diff не содержит открытых Critical/Important замечаний.
  - Evidence (review/commit): `________________`

## 2. Backup и schema preflight

- [ ] **Обязательно:** создан custom-format backup **до** запуска нового backend; файл непустой и хранится вне сервера приложения.
  - Evidence (UTC time, size, checksum, storage reference): `________________`
- [ ] **Обязательно:** restore этого backup проверен в отдельной пустой PostgreSQL 15 базе.
  - Evidence (restore command/result, sample verification): `________________`
- [ ] **Обязательно:** выполнен schema preflight из [DEPLOYMENT.md](DEPLOYMENT.md) до автоматического `upgrade head`.
  - Recorded revision: `________________`
  - Missing expected `010` objects query result (должно быть 0 строк): `________________`
- [ ] **Обязательно для базы, ранее stamped `010`:** проверены не только имена колонок, но и свойства, созданные миграцией `010`.
  - `users.amocrm_group_id`: integer, nullable; `users.hide_widget`: boolean, `NOT NULL`, default `false`.
  - `widget_groups.name_key`: character varying(765), `NOT NULL`; `allow_restart_session`: boolean, `NOT NULL`, default `false`.
  - `widget_settings.support_phone`: character varying(64), nullable; `allowed_statuses`: JSON, `NOT NULL`, default `["working","break","finished"]`; `default_allow_restart_session`: boolean, `NOT NULL`, default `false`; `revision`: integer, `NOT NULL`, default `1`.
  - Evidence (`information_schema.columns`: type, length, nullability, default): `________________`
- [ ] **Обязательно для базы, ранее stamped `010`:** PostgreSQL содержит уникальное ограничение `uq_widget_groups_account_name_key` ровно на `(account_id, name_key)`.
  - Evidence (`pg_constraint` + `pg_get_constraintdef`): `________________`
- [ ] Если stamped `010` не соответствует схеме, выпуск остановлен; подготовлена отдельная forward repair migration или выбран согласованный чистый restore. Повторный stamp и запуск текущего backend запрещены.
  - Decision/repair reference или `N/A, schema consistent`: `________________`

## 3. Миграция до единственной головы `014`

- [ ] **Обязательно:** граф кода имеет ровно одну голову `014`.
  - Evidence: `docker compose --env-file .env run --rm --entrypoint python backend -m alembic heads`
  - Result: `________________`
- [ ] **Обязательно:** одна release-задача применила `alembic upgrade head`; параллельный первый upgrade несколькими экземплярами не запускался.
  - Evidence: `________________`
- [ ] **Обязательно:** целевая база показывает `014 (head)` через `alembic current`.
  - Evidence: `________________`

## 4. Секреты и production-конфигурация

- [ ] **Обязательно:** заполнены уникальные `POSTGRES_PASSWORD`, `AMOCRM_CLIENT_SECRET`, `SECRET_KEY` (не менее 32 символов) и точный HTTPS `AMOCRM_REDIRECT_URI`; значения не записаны в этот документ.
  - Secret-store references/rotation date: `________________`
- [ ] **Обязательно:** `.env`, дампы и token отсутствуют в Git и ZIP; `DEBUG=false`, production использует PostgreSQL.
  - Evidence: `________________`
- [ ] **Обязательно:** `docker compose --env-file .env config --quiet` проходит; итоговая конфигурация проверена ответственным без публикации развёрнутых секретов.
  - Evidence: `________________`
- [ ] Если API работает в нескольких workers/containers, shared ingress rate/concurrency limits настроены с account/user key после доверенной аутентификации.
  - Evidence или `N/A, one worker`: `________________`

## 5. GitHub CI

Проверенный release candidate: `8b99846af9b806d1446f86d2bb746e28207bfaea`. Push run `37218960639` и PR run `37218963078` завершились `success` 2026-10-04; выполнены PostgreSQL 15, Alembic `014`, backend, Node, Playwright Chrome, package/ZIP, Black, compileall, diff, Compose config и Docker image build. Чекбоксы ниже остаются открытыми до выбора окончательного release commit и переноса его SHA/URL в deployment record.

- [ ] **Обязательно:** реальный `.github/workflows/ci.yml` завершился успешно на точном release commit.
  - Run URL: `________________`
  - Workflow SHA: `________________`
  - Conclusion/time: `________________`
- [ ] **Обязательно:** в run действительно выполнены PostgreSQL 15, `014`, backend, Node, Playwright, package/ZIP, Black, compileall, diff, Compose config и Docker image build; skipped/allowed failures разобраны.
  - Evidence: `________________`

## 6. Docker и health целевой среды

- [ ] **Обязательно:** `docker compose --env-file .env build backend` успешно собрал image из `backend/Dockerfile`.
  - Image digest: `________________`
- [ ] **Обязательно:** `docker compose --env-file .env up -d` и `docker compose ... ps` показывают стабильные healthy services.
  - Evidence/time: `________________`
- [ ] **Обязательно:** через production HTTPS ingress `/health/live` возвращает `200`.
  - Evidence: `________________`
- [ ] **Обязательно:** `/health/ready` возвращает `200` и `{"status":"ready","checks":{"database":"ready","schema":"ready"}}`.
  - Evidence: `________________`
- [ ] Контрольный отказ PostgreSQL убирает экземпляр из traffic по readiness `503`; восстановление БД возвращает readiness без ручного сдвига watermark.
  - Evidence: `________________`

## 7. Масштаб и изоляция 40 аккаунтов

- [ ] **Обязательно:** начальная настройка проверена для 40 аккаунтов: `INGESTION_MAX_CONCURRENT_ACCOUNTS=8`, poll interval и размеры rate-limit buckets соответствуют [CONFIGURATION.md](CONFIGURATION.md).
  - Evidence/config revision: `________________`
- [ ] **Обязательно:** одинаковые external user/event IDs в двух и более tenant scopes не смешивают статус, события, checkpoint, catalog, отчёты и XLSX.
  - Evidence: `________________`
- [ ] Под production-нагрузкой измерены `/api/v1/team/status` latency/p95, число `429`, ingestion lag/queue, OAuth errors и PostgreSQL pool usage. Локальный p95 <250 ms является только базовым контрактом и не заменяет этот замер.
  - Window/dashboard/query/result: `________________`
- [ ] Общий NAT не объединяет завершённые account/user quotas; pre-auth concurrency остаётся ограниченной.
  - Evidence: `________________`

## 8. Controlled live amoCRM

Последняя попытка: `2026-10-04`, read-only `GET /api/v4/account`, `/users`, `/events`, `/calls` — сетевой timeout до HTTP-ответа. CRM-данные и token pair не изменялись; все пункты раздела остаются незакрытыми. Перед refresh сначала восстановить сетевую доступность account URL.

- [ ] **Обязательно:** exact OAuth redirect, configured scopes/permissions, authorization-code exchange, refresh и одноразовый `X-Auth-Token` подтверждены без записи секретов.
  - Account/test window/evidence: `________________`
- [ ] **Обязательно:** реальные `rights`/`role_id` сопоставлены с Admin/руководитель/сотрудник; чужая группа и привилегированные действия запрещены backend.
  - Evidence: `________________`
- [ ] **Обязательно:** native callbacks `render/init/bind_actions/settings/onSave/destroy`, повторное открытие и ожидание async save работают в реальном iframe.
  - Evidence: `________________`
- [ ] **Обязательно:** `$authorizedAjax`, settings persistence, CORS origin/headers, стили, clipping и focus проверены в реальном аккаунте.
  - Evidence: `________________`
- [ ] **Обязательно:** сотрудник проходит start → break → resume → finish → разрешённый restart; при сбое backend нет ложного «Работаю».
  - Evidence: `________________`
- [ ] **Обязательно:** руководитель видит только свою группу; администратор сохраняет группы/timezone/расписание/flags и получает monitoring/report/XLSX.
  - Evidence: `________________`
- [ ] **Обязательно:** каталог проверен контролируемыми действиями: перечислены наблюдавшиеся event types, пройдена реальная pagination и измерена delivery latency. Не заявлять «полный каталог», если его полнота не доказана.
  - Evidence (types/pages/timestamps): `________________`
- [ ] Readable calls source подтверждён вместе с author/direction/duration/card либо выпуск явно принимает отсутствие подтверждённых звонков как известное ограничение.
  - Evidence/accepted limitation owner: `________________`

Подробный сценарий и безопасные границы: [amocrm-integration-limits.md](amocrm-integration-limits.md).

## 9. Артефакт виджета

- [ ] **Обязательно:** архив собран из release commit командой `powershell -NoProfile -ExecutionPolicy Bypass -File .\build_widget.ps1`.
  - Build log/commit: `________________`
- [ ] **Обязательно:** `python .\validate_widget_zip.py .\widget.zip` успешен; архив содержит ровно 25 разрешённых runtime-файлов, валидные JSON/PNG и не содержит credential-like literals.
  - Validator result: `________________`
- [ ] **Обязательно:** SHA-256 рассчитан после валидации и совпадает с загружаемым файлом.
  - Command: `Get-FileHash -Algorithm SHA256 .\widget.zip`
  - SHA-256: `________________`
- [ ] **Обязательно:** установленный в amoCRM архив сопоставлен с этим SHA-256 и release commit.
  - Evidence: `________________`

## 10. Rollback и восстановление

- [ ] **Обязательно:** предыдущий image проверен на совместимость со схемой `014` либо rollback заранее выбран через восстановление предрелизного dump в новую базу.
  - Strategy/evidence: `________________`
- [ ] Ответственный умеет остановить backend/traffic, сохранить логи, восстановить dump, проверить `alembic current`, readiness и минимум два tenant scopes.
  - Drill/time/result: `________________`
- [ ] Recovery amoCRM 429/5xx/timeout, OAuth rotation, checkpoint, lease takeover и replay наблюдается без потери/дублей; watermark вручную не меняется.
  - Evidence: `________________`
- [ ] Контакты и критерии отмены выпуска согласованы.
  - Evidence: `________________`

## Решение

- [ ] **GO** — все обязательные пункты подтверждены, Critical/Important = 0.
- [ ] **NO-GO** — выпуск остановлен.

Решение: `________________`

Причина: `________________`

Ответственный и время: `________________`
