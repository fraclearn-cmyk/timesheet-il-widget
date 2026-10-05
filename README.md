# Табель IL для amoCRM

Виджет ведёт рабочий статус сотрудников в amoCRM, показывает руководителям состояние команды и подтверждённую CRM-активность, а администраторам даёт настройки групп и безопасный Excel-экспорт табеля. Backend изолирует данные по аккаунтам; локальные проверки рассчитаны минимум на 40 аккаунтов с повторяющимися внешними ID.

## Роли и основные сценарии

- **Сотрудник** видит свой подтверждённый статус и выполняет команды «Начать работу», «Перерыв», «Продолжить» и «Завершить». Видимость виджета и разрешение повторного старта задаёт администратор.
- **Руководитель** видит активных участников назначенных ему групп, открывает их семидневную ленту активности и формирует табель только в доступной области.
- **Администратор** управляет группами, часовыми поясами, расписанием, учётом и видимостью сотрудников; видит весь свой аккаунт и формирует Excel-отчёты.

Браузер не назначает себе аккаунт или роль. Рабочий виджет передаёт одноразовый `X-Auth-Token`, а backend проверяет его и актуальное состояние amoCRM.

## Состав проекта

- `backend/` — FastAPI, SQLAlchemy, Alembic и PostgreSQL;
- `frontend/widget/` — файлы устанавливаемого виджета amoCRM;
- `frontend/tests/` — Node и Playwright проверки интерфейса;
- `docs/` — API, конфигурация, эксплуатация и границы интеграции;
- `build_widget.ps1` и `validate_widget_zip.py` — сборка и проверка `widget.zip`.

## Быстрый запуск через Docker Compose

Требуются Docker Engine и Compose v2. Скопируйте пример окружения в корень проекта и заполните обязательные значения:

```powershell
Copy-Item backend/.env.example .env
docker compose --env-file .env config --quiet
docker compose --env-file .env build backend
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

Backend перед запуском автоматически выполняет `alembic upgrade head`. После старта проверьте:

```text
GET https://<ваш-домен>/health/live
GET https://<ваш-домен>/health/ready
```

`/health/live` подтверждает только работу процесса. `/health/ready` возвращает `200`, когда PostgreSQL доступна и схема находится на единственной актуальной ревизии `014`. Полный порядок обновления, резервного копирования и восстановления описан в [руководстве по развёртыванию](docs/DEPLOYMENT.md).

## Локальная разработка и проверка

Требуются Python 3.12, Node.js 22+ и PostgreSQL 15 для полного backend gate.

```powershell
python -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
npm ci
npx playwright install chrome
```

Создайте `backend/.env` для локального backend. Для production-подобного запуска используйте PostgreSQL; допустимые переменные и ограничения перечислены в [CONFIGURATION.md](docs/CONFIGURATION.md).

На Windows подготовлен локальный запуск без Docker. Он использует переносимый PostgreSQL 15 в `tmp/`, применяет миграции до актуальной головы и запускает API только на localhost. Реальный сбор событий amoCRM при таком запуске отключён:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
# Swagger: http://127.0.0.1:8000/api/docs
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

Переносимый PostgreSQL копируется в путь без кириллицы `%LOCALAPPDATA%\TimesheetIL\pgsql`, потому что Windows-сборка PostgreSQL не инициализирует кластер из каталога проекта `D:\табель`. Локальная база и журналы сохраняются рядом, в `%LOCALAPPDATA%\TimesheetIL\local-runtime`.

Основные проверки из корня проекта:

```powershell
$env:TEST_POSTGRES_ADMIN_URL='postgresql://<test-user>@127.0.0.1:5432/postgres'
Set-Location backend
..\.venv312\Scripts\python.exe -m alembic heads
..\.venv312\Scripts\python.exe -m pytest -q --tb=short
Set-Location ..
& node --test frontend/tests/*.test.js
npx playwright test frontend/tests --workers=1 --reporter=line
.\.venv312\Scripts\python.exe -m unittest test_widget_package.py
.\build_widget.ps1
.\.venv312\Scripts\python.exe validate_widget_zip.py widget.zip
```

`alembic heads` должен вывести ровно `014 (head)`. PostgreSQL-тесты нельзя считать выполненными, если они были пропущены из-за отсутствующего `TEST_POSTGRES_ADMIN_URL`.

## Установка виджета и пользовательская проверка

1. Соберите и проверьте `widget.zip` командами выше.
2. Установите архив в тестовый аккаунт amoCRM.
3. В настройках виджета задайте HTTPS URL backend с базовым путём `/api/v1/`.
4. Администратором сохраните группы, руководителей, часовые пояса, расписание, `track_time`, `hide_widget` и разрешение повторного старта.
5. Проверьте цикл сотрудника: старт → перерыв → продолжение → завершение.
6. Руководителем проверьте только назначенную группу и ленту выбранного сотрудника.
7. Администратором проверьте табель, фильтры и скачивание Excel.

Локальные тесты не заменяют проверку реального OAuth redirect, одноразового токена, CORS, полного каталога событий, доставки и источника звонков в целевом аккаунте amoCRM. Точные известные границы собраны в [amocrm-integration-limits.md](docs/amocrm-integration-limits.md).

## Документация

- [Конфигурация](docs/CONFIGURATION.md) — переменные окружения, секреты и настройки на 40 аккаунтов;
- [Развёртывание](docs/DEPLOYMENT.md) — backup, миграции, Docker, health, rollback и recovery;
- [Варианты размещения](docs/HOSTING_OPTIONS.md) — локальный запуск, бесплатные серверы и расчёт Beget;
- [API](docs/API.md) — аутентификация, роли, рабочий статус, мониторинг, табель и ошибки;
- [Ограничения интеграции amoCRM](docs/amocrm-integration-limits.md) — подтверждённые факты и обязательные live gates;
- [Процесс разработки](docs/development-workflow.md) — команды проверок и порядок обновления статусов;
- [План проекта](Plan.md) — состояние фаз и фактические результаты.

Swagger UI доступен у запущенного backend по `/api/docs`.

## Статус проверки выпуска

Автоматические локальные сценарии и CI workflow находятся в репозитории. Фактический запуск GitHub CI, `docker compose build/up` в целевой среде и controlled live-проверка amoCRM должны быть зафиксированы отдельно перед production-выпуском.
