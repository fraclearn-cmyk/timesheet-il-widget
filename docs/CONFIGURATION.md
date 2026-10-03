# Конфигурация

Текущий backend читает настройки из переменных окружения и, при прямом запуске из каталога `backend`, из файла `backend/.env`. Для Docker Compose пример `backend/.env.example` копируют в корневой `.env` и передают через `--env-file .env`.

Не добавляйте `.env`, дампы базы, OAuth token, authorization code или webhook URL с секретным ключом в Git и журналы.

## Обязательные значения

| Переменная | Требование | Назначение |
|---|---|---|
| `POSTGRES_DB` | Непустое значение для Compose | Имя базы, создаваемой контейнером PostgreSQL. |
| `POSTGRES_USER` | Непустое значение для Compose | Пользователь PostgreSQL. |
| `POSTGRES_PASSWORD` | Сильный уникальный секрет для Compose | Пароль PostgreSQL. |
| `DATABASE_URL` | В production только `postgresql://...` | Строка подключения backend. В Compose хостом служит `db`, например `postgresql://timesheet:<пароль>@db/timesheet`. |
| `AMOCRM_CLIENT_ID` | Не менее 10 символов | UUID/ID зарегистрированной интеграции amoCRM; участвует в проверке одноразового токена. |
| `AMOCRM_CLIENT_SECRET` | Не менее 10 символов; хранить как секрет | Секрет интеграции и ключ проверки `X-Auth-Token`. |
| `AMOCRM_REDIRECT_URI` | Абсолютный HTTPS URL без credentials | Redirect URI интеграции. Его HTTPS origin используется как audience одноразового токена. |
| `SECRET_KEY` | Не менее 32 символов; уникален для среды | Шифрование сохранённых OAuth token. Значение с `change_this` запрещено в production. |

Смена `SECRET_KEY` без контролируемой ротации сделает существующие зашифрованные OAuth token нечитаемыми. Сначала подготовьте повторную авторизацию или миграцию секретов.

## Необязательные значения backend

| Переменная | По умолчанию | Ограничение и смысл |
|---|---:|---|
| `APP_NAME` | `Timesheet IL API` | Имя приложения при прямом запуске backend. Текущий Compose не переопределяет его. |
| `BACKEND_PORT` | `8000` | Порт хоста, публикуемый Compose. |
| `ENVIRONMENT` | `production` | Compose жёстко задаёт `production`; при нём SQLite и MySQL запрещены. |
| `DEBUG` | `false` | Compose жёстко отключает debug. Не включайте в production. |
| `ALGORITHM` | `HS256` | Алгоритм служебной подписи. Текущий одноразовый widget token также ожидает HS256-контракт amoCRM. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Срок служебного access token в минутах. |
| `POLLING_INTERVAL` | `15` | Базовая прикладная настройка polling в секундах. Dashboard имеет собственный ограниченный backoff. |
| `INACTIVITY_TIMEOUT` | `300` | Таймаут неактивности в секундах. Browser presence не превращается в подтверждённую CRM-активность. |
| `EVENT_POLL_INTERVAL_SECONDS` | `60` | Интервал ingestion, допустимо `15..60`. |
| `RAW_EVENT_RETENTION_DAYS` | `30` | Фиксировано: любое другое значение отклоняется при старте. |
| `INGESTION_WORKER_ENABLED` | `true` | Запускает фоновый ingestion worker вместе с API. |
| `INGESTION_MAX_CONCURRENT_ACCOUNTS` | `8` | Допустимо `1..8`; для 40 аккаунтов рекомендуемое значение — `8`. |
| `PUBLIC_BASE_URL` | пусто | HTTPS origin backend без path/query/fragment. Пусто означает polling-only; при значении доступна настройка webhook. |
| `ALLOWED_ORIGINS` | пустой список | Дополнительные origins через запятую. Доверенные tenant origins amoCRM/Kommo уже допускаются регулярным выражением приложения. |
| `RATE_LIMIT_CALLS` | `60` | Запросов на один проверенный account/user за период в одном Python worker. |
| `RATE_LIMIT_PERIOD` | `60` | Длина окна rate limit в секундах. |
| `RATE_LIMIT_MAX_BUCKETS` | `4096` | Число buckets в памяти процесса, допустимо `40..65536`. |
| `AUTHENTICATION_MAX_CONCURRENT_PER_IP` | `64` | Одновременная дорогая работа до завершения аутентификации с одного socket IP, допустимо `40..1024`. |
| `LOG_LEVEL` | `INFO` | Уровень структурированного журнала при прямом запуске backend. |

Текущий `docker-compose.yml` передаёт основные app/ingestion/CORS значения, но не передаёт `APP_NAME`, `RATE_LIMIT_CALLS`, `RATE_LIMIT_PERIOD`, `RATE_LIMIT_MAX_BUCKETS`, `AUTHENTICATION_MAX_CONCURRENT_PER_IP` и `LOG_LEVEL`. В стандартном Compose-запуске поэтому действуют их значения по умолчанию. Чтобы изменить их, добавьте явное отображение в отдельный Compose override и проверьте итог через `docker compose ... config`; одного изменения `.env` недостаточно.

## Настройка на 40 аккаунтов

Начальная production-конфигурация:

```env
EVENT_POLL_INTERVAL_SECONDS=60
RAW_EVENT_RETENTION_DAYS=30
INGESTION_WORKER_ENABLED=true
INGESTION_MAX_CONCURRENT_ACCOUNTS=8
RATE_LIMIT_CALLS=60
RATE_LIMIT_PERIOD=60
RATE_LIMIT_MAX_BUCKETS=4096
AUTHENTICATION_MAX_CONCURRENT_PER_IP=64
```

Восемь ingestion slots обрабатывают 40 готовых аккаунтов справедливыми волнами. Это проверенная локальная исходная настройка, а не гарантия времени ответа amoCRM. Изменяйте её только по production-метрикам базы, HTTP-клиента и очереди.

Авторизованный limiter использует проверенный ключ account/user, поэтому 40 аккаунтов за одним NAT не объединяются в одну завершённую квоту. Ограничение до авторизации использует socket peer и сдерживает только одновременную дорогую работу.

Все эти счётчики находятся в памяти одного Python worker. При нескольких Uvicorn workers или нескольких контейнерах общая квота не координируется. Настройте shared limit на доверенном ingress/API gateway и сохраняйте tenant-разделение после проверки identity. Не доверяйте клиентским `X-Forwarded-For` без собственной нормализации на ingress.

## Аккаунты, группы, расписание и видимость

Эти значения хранятся в PostgreSQL и изменяются администратором через `GET/PUT /api/v1/settings/snapshot`, а не через `.env`:

- `settings.support_phone` — необязательный телефон поддержки;
- `settings.allowed_statuses` — непустой набор из `working`, `break`, `finished`;
- `settings.default_allow_restart_session` — значение повторного старта по умолчанию;
- `groups[].timezone` — IANA timezone, например `Europe/Moscow`;
- `groups[].work_start_time` и `work_end_time` — границы смены; время окончания раньше начала означает ночную смену;
- `groups[].manager_amocrm_user_id` — руководитель с актуальным снимком роли amoCRM;
- `groups[].allow_restart_session` — разрешение новой сессии в тот же business day;
- `users[].track_time` — включён ли табель для сотрудника;
- `users[].hide_widget` — скрывать ли рабочий интерфейс;
- `users[].group_ref` — активная группа пользователя.

Сохранение выполняется целым снимком с `revision`. Устаревшая revision даёт конфликт, а неизвестные user/group references отклоняются. Часовой пояс группы определяет business date, границы отчёта, ночные смены и DST; не заменяйте его системным часовым поясом сервера.

## URL виджета и CORS

В native настройке установленного виджета `api_url` должен указывать на публичный HTTPS backend с базовым путём `/api/v1/`, например:

```text
https://timesheet.example.com/api/v1/
```

`PUBLIC_BASE_URL` задаёт только origin, например `https://timesheet.example.com`. Не помещайте туда `/api/v1`, credentials, query или fragment.

Production CORS разрешает HTTPS tenant subdomains `*.amocrm.ru`, `*.amocrm.com` и `*.kommo.com`, а также явные `ALLOWED_ORIGINS`. Проверьте фактический origin iframe в controlled live smoke; локальный jsdom/Playwright не доказывает реальную доставку CORS-заголовков amoCRM.

## Проверка конфигурации

Без вывода секретов выполните:

```powershell
docker compose --env-file .env config --quiet
docker compose --env-file .env run --rm --entrypoint python backend -m alembic heads
```

Переопределение entrypoint во второй команде позволяет прочитать граф миграций без автоматического `upgrade head`. Для проверки подключения и текущей версии целевой базы всё равно сначала выполните backup и schema preflight из [DEPLOYMENT.md](DEPLOYMENT.md). Не печатайте объект `settings` целиком.

Подробнее об эксплуатации и внешних gates: [DEPLOYMENT.md](DEPLOYMENT.md), [API.md](API.md), [amocrm-integration-limits.md](amocrm-integration-limits.md).
