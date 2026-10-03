# Развёртывание и восстановление

Инструкция относится к текущей схеме PostgreSQL с единственной головой Alembic `014` и стандартному `docker-compose.yml`. Все команды выполняются из корня репозитория. Файл `.env` хранится только на целевой машине или в secret store.

Локальное наличие workflow и Compose-файла не означает, что GitHub CI, Docker build/up или live amoCRM уже прошли. Перед выпуском запишите фактический результат каждого внешнего gate.

## 1. Предварительные условия

- Docker Engine и Compose v2;
- PostgreSQL 15 с постоянным volume и отдельным backup storage;
- HTTPS ingress для backend;
- заполненный `.env` по [CONFIGURATION.md](CONFIGURATION.md);
- согласованное окно обновления и ответственный за восстановление;
- доступ к журналам по `request_id` без вывода секретов.

Создайте окружение и проверьте структуру Compose:

```powershell
Copy-Item backend/.env.example .env
# заполнить .env вне Git
docker compose --env-file .env config --quiet
```

## 2. Обязательный backup

Перед обновлением кода или схемы снимите custom-format dump и сохраните его вне сервера приложения. Команду перенаправления выполняйте в shell, который сохраняет бинарный stdout без перекодирования:

```bash
docker compose --env-file .env exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > timesheet-before-release.dump
```

Проверьте, что файл не пуст, и протестируйте восстановление в отдельную базу. Наличие dump без пробного restore не считается подтверждённым backup.

## 3. Schema preflight для ранее stamped `010`

В ранней локальной версии ревизию `010` могли отметить применённой без фактического создания `users.hide_widget`. Entrypoint backend сразу выполняет `alembic upgrade head`, поэтому preflight проводят **до запуска нового backend**.

Поднимите только PostgreSQL:

```powershell
docker compose --env-file .env up -d db
docker compose --env-file .env ps db
```

Проверьте записанную ревизию и обязательные объекты `010`:

```bash
docker compose --env-file .env exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' <<'SQL'
SELECT version_num FROM alembic_version;

WITH expected(table_name, column_name) AS (
  VALUES
    ('users', 'amocrm_group_id'),
    ('users', 'hide_widget'),
    ('widget_groups', 'name_key'),
    ('widget_groups', 'allow_restart_session'),
    ('widget_settings', 'support_phone'),
    ('widget_settings', 'allowed_statuses'),
    ('widget_settings', 'default_allow_restart_session'),
    ('widget_settings', 'revision')
)
SELECT e.table_name, e.column_name
FROM expected e
LEFT JOIN information_schema.columns c
  ON c.table_schema = 'public'
 AND c.table_name = e.table_name
 AND c.column_name = e.column_name
WHERE c.column_name IS NULL;
SQL
```

Второй запрос должен вернуть ноль строк. Если база отмечена как `010` или выше, но хотя бы один объект отсутствует, остановите выпуск. Не повторяйте изменённую `010`, не запускайте текущий backend и не ставьте новый stamp. Нужна отдельная проверенная forward repair migration с переносом исторического `hide_widget` из membership данных либо восстановление согласованного чистого dump. Такое исправление готовят и испытывают отдельно.

Для чистой базы этот специальный риск отсутствует: последовательность `001..014` создаёт объекты обычным способом.

## 4. Сборка и миграция до `014`

После backup и успешного preflight:

```powershell
docker compose --env-file .env build backend
docker compose --env-file .env up -d
docker compose --env-file .env ps
docker compose --env-file .env exec backend python -m alembic heads
docker compose --env-file .env exec backend python -m alembic current
```

Entrypoint контейнера выполняет `python -m alembic upgrade head` до Uvicorn. Обе Alembic-команды должны показывать единственную `014 (head)`. При ошибке миграции backend не стартует.

Не запускайте несколько новых экземпляров, которые одновременно впервые накатывают схему. Примените миграцию одной release-задачей, проверьте `014`, затем масштабируйте API.

## 5. Liveness и readiness

После запуска дождитесь healthy-состояния и проверьте адреса через тот же HTTPS ingress, которым будет пользоваться виджет:

```powershell
curl.exe -fsS https://timesheet.example.com/health/live
curl.exe -fsS https://timesheet.example.com/health/ready
```

- `/health/live` возвращает `200`, если процесс жив; доступность базы он не доказывает.
- `/health/ready` возвращает `200` только при доступной PostgreSQL и точном совпадении единственной текущей миграции с головой кода.
- `503` readiness означает: экземпляр нельзя подключать к пользовательскому трафику.

Ожидаемый readiness payload:

```json
{"status":"ready","checks":{"database":"ready","schema":"ready"}}
```

## 6. Проверка целевой среды

Зафиксируйте результаты после развёртывания:

1. GitHub Actions workflow `.github/workflows/ci.yml` завершился успешно на фактическом commit.
2. Целевые `docker compose build`, `up`, `ps`, Alembic `heads/current`, liveness и readiness успешны.
3. Backup создан, а restore проверен в отдельной базе.
4. В тестовом аккаунте amoCRM подтверждены OAuth redirect, одноразовый `X-Auth-Token`, CORS и реальные роли.
5. Администратор сохраняет snapshot групп, timezone, расписания, `track_time`, `hide_widget` и restart policy.
6. Сотрудник проходит start → break → resume → finish без ложного статуса при отказе backend.
7. Руководитель не видит чужую группу; администратор видит свой аккаунт, табель и безопасный Excel.
8. Для 40 аккаунтов проверены изоляция, latency, число `429`, очередь ingestion, OAuth errors и соединения PostgreSQL.
9. Event catalog, pagination/delivery latency и источник звонков отмечены только в пределах реально наблюдавшихся данных.

Ограниченный controlled live checklist находится в [amocrm-integration-limits.md](amocrm-integration-limits.md). Локальные mocks не закрывают этот gate.

## 7. Журналы и request ID

Backend пишет структурированные JSON-события. Каждый ответ содержит `X-Request-Id`; безопасная JSON-ошибка повторяет то же значение в `error.request_id`. Для разбора инцидента:

1. возьмите request ID из ответа пользователя;
2. найдите совпадающее поле в централизованном журнале;
3. сопоставьте время, route, status и соседние события ingestion/database;
4. не просите пользователя присылать token или полный заголовок авторизации.

Не сохраняйте access/refresh token, authorization code, пароли, cookie, webhook URL/key, полные auth headers или сырые webhook payload. Uvicorn access log в Compose отключён, чтобы opaque webhook path не попал в обычный журнал.

## 8. Сбой и восстановление

### PostgreSQL недоступна

Уберите backend из балансировщика по `503 /health/ready`, восстановите PostgreSQL, проверьте `SELECT 1`, `alembic current` и readiness. Не переводите traffic по одному liveness.

### Ошибка amoCRM, `429` или `5xx`

Ingestion сохраняет подтверждённый checkpoint и использует ограниченный retry/backoff. После восстановления OAuth и сети worker продолжает с последней необработанной позиции; истёкший lease может забрать другой worker. Не сдвигайте watermark вручную. Account-scoped dedup подавляет повторную доставку.

### Ошибка OAuth

Проверьте connection и разрешённый refresh/re-auth flow. Не подменяйте identity browser ID. При потере `SECRET_KEY` существующие зашифрованные token нельзя расшифровать — требуется контролируемая повторная авторизация.

### Повреждение или потеря базы

Остановите backend, восстановите dump в новую пустую базу PostgreSQL 15 и подключите отдельный проверочный backend:

```bash
docker compose --env-file .env stop backend
docker compose --env-file .env exec -T db sh -c 'createdb -U "$POSTGRES_USER" timesheet_restore'
docker compose --env-file .env exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d timesheet_restore --exit-on-error' < timesheet-before-release.dump
```

Укажите проверочному backend новую `DATABASE_URL`, затем выполните `alembic current`, `/health/ready` и выборочную сверку минимум двух tenant scopes, рабочих сессий, настроек и отчёта. Production переключайте только после этой проверки.

## 9. Rollback выпуска

Сначала остановите поступление новых записей и сохраните диагностические логи. Автоматический `alembic downgrade` не является штатным rollback: миграции `010..013` намеренно отказываются удалять появившиеся production-данные, а старый image может не поддерживать схему `014`.

Безопасная стратегия:

1. если предыдущий image явно совместим со схемой `014`, откатите только image и повторите health/user checks;
2. если совместимость не доказана, восстановите предрелизный dump в новую базу и запустите соответствующий ему image;
3. не запускайте старый image против новой базы «для проверки» без отдельного compatibility test;
4. после переключения сохраните неисправную среду только для анализа без пользовательского traffic.

## 10. Несколько workers и 40 аккаунтов

Для 40 аккаунтов начните с `INGESTION_MAX_CONCURRENT_ACCOUNTS=8`, одного scheduler-capable backend и sizing из эксплуатационной документации: ориентир 2 CPU/2–4 ГиБ RAM для backend и 2 CPU/4 ГиБ RAM/SSD для PostgreSQL. Это стартовые числа, которые подтверждаются или меняются production-метриками.

Process-local rate limits не складываются между workers. Перед горизонтальным масштабированием настройте shared rate/concurrency limit на доверенном ingress/API gateway. После аутентификации ключ должен сохранять account/user isolation; общий NAT не должен превращать 40 tenant contexts в одну квоту.

Дополнительные эксплуатационные детали находятся в [operations.md](operations.md), точные настройки — в [CONFIGURATION.md](CONFIGURATION.md), API и ошибки — в [API.md](API.md).
