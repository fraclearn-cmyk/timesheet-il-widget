# Фаза 0 — отчёт: контракт и технический spike amoCRM

Дата: 2026-09-11

## Итог

Локальная часть фазы завершена. Реальная проверка amoCRM не запускалась: в текущем
workspace нет авторизованной amoCRM-сессии и OAuth client credentials пригодных для
запроса. Поэтому итоговый статус фазы — `DONE_WITH_CONCERNS`.

## Сделано

- Сверены manifest, widget script, legacy backend routes и требования; таблица требований
  теперь отличает локально подтверждённое, mock-контракт и данные, требующие test account.
- Подтверждено, что manifest использует только `advanced_settings`; изменение
  `widget/manifest.json` не требовалось. Scopes в нём не выдумывались.
- Добавлен минимальный adapter `app.integrations.amocrm_contract`:
  authorization-code grant, refresh-token grant, отказ без access token, 401 как
  просроченный token, строгая нормализация CRM event и fallback `incomplete_event`.
- Добавлены mock-контрактные тесты. Неполный call payload не создаёт confirmed activity;
  local mouse/keyboard также не объявлены CRM-активностью.
- Зафиксирован целевой JSON-контракт для `/me`, settings, status transitions, team,
  timeline, detailed report и Excel export. Legacy routes явно отмечены как не равные
  этому контракту.
- Добавлена программа безопасного live spike без логирования code/token.

## TDD: RED → GREEN

| Цикл | RED команда и ожидаемый результат | GREEN команда и результат |
|---|---|---|
| Первичный OAuth/event contract | `Push-Location backend; & 'D:\\табель\\.venv312\\Scripts\\python.exe' -m pytest -q tests\\integration\\test_amocrm_contract.py` — `ModuleNotFoundError: app.integrations.amocrm_contract` | Та же команда после минимального adapter — `5 passed` |
| Refresh token | Та же команда после добавления теста — `AttributeError: AmoCRMAuthClient has no attribute refresh_access_token` | Та же команда после реализации refresh grant — `6 passed` |

Пути в командных примерах RED исполнялись из `D:\табель\backend`; фактический interpreter:
`D:\табель\.venv312\Scripts\python.exe`.

## Финальная проверка

- `Push-Location backend; D:\табель\.venv312\Scripts\python.exe -m pytest -q` →
  `6 passed in 0.47s`.
- `Push-Location backend; D:\табель\.venv312\Scripts\python.exe -m black --check app\integrations tests\integration`
  → после форматирования проходит.
- `Push-Location backend; D:\табель\.venv312\Scripts\python.exe -m flake8 --ignore=E501,W503 app\integrations tests\integration`
  → проходит. `E501` и `W503` исключены только потому, что установленный Black форматирует
  строки до 88 символов и ставит break перед бинарным оператором, а project flake8 использует
  несовместимые defaults 79 и W503; других нарушений нет.
- `git diff --check` → exit code 0.

## Изменённые файлы

- `backend/app/integrations/__init__.py`
- `backend/app/integrations/amocrm_contract.py`
- `backend/tests/integration/test_amocrm_contract.py`
- `docs/requirements-matrix.md`
- `docs/amocrm-integration-limits.md`
- `docs/api-contract.md`

`Plan.md`, `.env`, manifest и файлы последующих фаз не изменялись.

## Self-review

- Контрактные тесты проверяют итог adapter-а; mock transport отклоняет неправильные
  boundary request payloads, а не служит предметом отдельной проверки.
- OAuth client получает credentials через dependency injection и не пишет их в логи.
- Недоступные fields не заполнены заглушками: неполный event/call остаётся
  `incomplete_event` с исходным payload.
- Документация различает target contract и уже существующие legacy endpoints, исключая
  ложное предположение, что target API реализован.

## Concerns: непроверенное live

1. Установка архива и открытие `advanced_settings` в реальном test account.
2. OAuth redirect, реальный authorization code/refresh rotation и scopes интеграции.
3. Account/user fields, источник amoCRM roles/rights и mapping в local RBAC.
4. Endpoint/типы analytics events, author/timestamp/entity/link, pagination, latency и
   повторная доставка.
5. Call reader API и реальные direction, duration, author, associated card/link для
   входящего и исходящего звонка.
6. Доступность событий всей страницы из iframe и отсутствие CRM event для mouse/keyboard.

До успешного live spike все перечисленные данные остаются mock-only или unavailable,
как указано в `docs/amocrm-integration-limits.md`.

## Fix round 1

### Изменения

- OAuth authorization-code и refresh-token grants теперь отправляют JSON body с
  `Content-Type: application/json`; mock проверяет весь payload, включая redirect URI.
- Tenant URL нормализуется только как server-side origin `https://<tenant>.amocrm.ru`,
  `https://<tenant>.amocrm.com` или `https://<tenant>.kommo.com`, без path, query,
  credentials и port. Невалидный URL блокируется до обращения к transport, поэтому
  client secret не покидает разрешённый tenant.
- CRM event получает `confirmed` только для mock-validated пары
  `lead_status_changed`/`leads`, положительных integer ID/timestamp/author и строкового
  self link. Неизвестный type, неверный ID/timestamp/link и неподтверждённая сущность
  возвращают `incomplete_event` без исключения.
- API-контракт закрепляет server-side re-check действующих OAuth/account/amoCRM прав на
  каждом запросе privileged route, timezone на уровне группы, UTC storage/API и
  нейтральные `unconfirmed/browser_input` и `idle/no_confirmed_crm_event` интервалы.

### RED

1. `Push-Location backend; & 'D:\табель\.venv312\Scripts\python.exe' -m pytest -q tests\integration\test_amocrm_contract.py`
   → `12 failed, 4 passed`: mock отверг form-encoded OAuth payload; untrusted URL не
   отклонялся; malformed/unknown events ошибочно подтверждались или выбрасывали `ValueError`.
2. `Push-Location backend; & 'D:\табель\.venv312\Scripts\python.exe' -m pytest -q tests\integration\test_amocrm_contract.py -k malformed`
   → `8 failed, 10 deselected`: новый случай invalid ID/link также не переходил в fallback.
3. `Push-Location backend; & 'D:\табель\.venv312\Scripts\python.exe' -m pytest -q tests\integration\test_amocrm_contract.py -k untrusted`
   → `1 failed, 4 passed, 14 deselected`: malformed port выдавал parser error вместо
   controlled tenant-rejection, хотя transport не вызывался.

### GREEN

`Push-Location backend; & 'D:\табель\.venv312\Scripts\python.exe' -m pytest -q tests\integration\test_amocrm_contract.py`
→ `19 passed in 0.63s` после минимальных исправлений. Полная финальная верификация
(включая full pytest, Black, flake8 и `git diff --check`) выполняется перед коммитом.

### Итоговый вывод

Открытые Critical/Important замечания Fix round 1 закрыты локальными контрактными тестами
и явными правилами API. Live проверки amoCRM по-прежнему отсутствуют: allowlist и единственная
подтверждаемая event shape являются безопасным mock-contract, а не доказательством полного
набора tenant-specific fields или прав.

## Fix round 2

### Изменения

- `normalize_timeline_event` теперь признаёт ссылку объекта безопасной только как HTTPS URL
  разрешённого amoCRM/Kommo tenant без query/fragment, ведущий ровно на карточку текущей
  сущности (`/{entity_type}/detail/{entity_id}`). Строковая, но malformed или чужая ссылка
  даёт `incomplete_event`, не исключение.

### RED

`Push-Location backend; & 'D:\табель\.venv312\Scripts\python.exe' -m pytest -q tests\integration\test_amocrm_contract.py -k malformed`
→ `2 failed, 8 passed, 11 deselected`: `href="not a URL"` и URL внешнего host ошибочно
создавали `confirmed` event.

### GREEN

`Push-Location backend; & 'D:\табель\.venv312\Scripts\python.exe' -m pytest -q tests\integration\test_amocrm_contract.py`
→ `21 passed in 0.52s` после минимальной URL-проверки. Полная проверка и `git diff --check`
выполнены перед коммитом.

### Итоговый вывод

Строковый `href` больше не достаточен для confirmed activity: event привязан к безопасной
карточке на разрешённом tenant. Live-format ссылок по-прежнему требует отдельного spike.

## Live spike (2026-09-16)

### Safety boundary

- Использован только root `.env`, который игнорируется Git. Значения account URL, token,
  client credential и redirect URI не печатались, не коммитились и не добавлялись в файлы.
- Выполнены только HTTP `GET` и один разрешённый OAuth refresh `POST`; CRM entities не
  создавались, не изменялись и не удалялись, звонки не инициировались.
- Все результаты ниже ограничены HTTP status, content type, field names, primitive shapes,
  counts и presence; не сохранены user values, email, name, phone, full payload или token.

### Выполненные live команды

1. `D:\табель\.venv312\Scripts\python.exe -` — безопасная проверка presence шести OAuth
   environment variables (только `present`/`missing`).
2. `D:\табель\.venv312\Scripts\python.exe -` — read-only `GET` account, users (`limit=1`),
   events (`limit=1`) и calls (`limit=1`) с sanitised field-shape output.
3. `D:\табель\.venv312\Scripts\python.exe -` — users pagination/`rights` shape только с
   именами keys, типами и счётчиками.
4. `D:\табель\.venv312\Scripts\python.exe -` — refresh token grant c JSON body; после
   проверки обеих token fields обновление `AMOCRM_ACCESS_TOKEN` и `AMOCRM_REFRESH_TOKEN`
   сделано в temp file и одним `os.replace` в `.env`; затем read-only account re-check.

Inline scripts намеренно не сохранены: их единственная цель — безопасная одноразовая проверка
локально доступных credentials без создания ещё одного пути работы с секретами.

### Подтверждено live

| Проверка | Результат |
|---|---|
| Account context | `GET /api/v4/account` → 200, `application/hal+json`; source fields включают account/current-user/audit metadata и `_links` |
| Users и rights | `GET /api/v4/users?limit=1&page=1` → 200; один элемент; user keys `_links,email,id,lang,name,rights`; `rights` — object с entity/access, group/admin/role и status keys |
| Users pagination | `_page`, `_page_count`, `_total_items` присутствуют как integer; observed meta 1/1/1. Обход нескольких страниц и page behavior не проверены |
| Refresh | `POST /oauth2/access_token` (`refresh_token`) → 200, JSON keys `access_token,expires_in,refresh_token,server_time,token_type`; оба tokens атомарно обновлены; новый access token дал account 200 |
| Events availability | `GET /api/v4/events?limit=1&page=1` → 204, body отсутствует |
| Calls availability | `GET /api/v4/calls?limit=1&page=1` → 405 |

### Не подтверждено / намеренно не выполнялось

- Authorization-code redirect и OAuth scopes: code очищен, flow не воспроизводился.
- Mapping amoCRM `rights`/`role_id` к local Admin/ROP/employee.
- Event records: type, author, timestamp, entity, link, event pagination, latency и
  duplicate delivery; live endpoint вернул 204.
- Call reader contract и direction/duration/author/card; calls GET вернул 405.
- Widget installation/`advanced_settings`, browser-wide event capture и mouse/keyboard
  boundary в real iframe.
- Изменения CRM-сущностей и входящие/исходящие calls не выполнялись без отдельного разрешения.

### Документы и self-review

- `docs/requirements-matrix.md`, `docs/amocrm-integration-limits.md` и
  `docs/api-contract.md` обновлены только подтверждёнными live status/field-shape facts.
- `Plan.md` и tracked code не менялись; отдельный live helper не добавлялся, потому что
  одноразовые scripts безопаснее не хранить рядом с production code.
- Проверен `git status`: `.env` не staged и не включён в commit. Документация не содержит
  значения secret/token/PII или raw responses.

## Fix round 3

### Изменения

- Уточнён единственный live pagination вывод: `GET /api/v4/users?limit=1&page=1` показал
  metadata `_page`, `_page_count`, `_total_items` со значениями 1/1/1, но не проверял
  переход на вторую страницу. Во всех соответствующих документах это теперь описано как
  «pagination metadata наблюдались; обход нескольких страниц и page behavior не проверены».

### Проверки

- `rg -n -i "pagination|пагинац|_page|_total_items|page behavior|travers" docs .superpowers\sdd\Plan\phase-0-report.md`
  — проверена согласованность всех pagination-формулировок.
- `git diff --check` — exit code 0 перед коммитом.

### Итоговый вывод

Metadata shape подтверждён одним read-only response; утверждений о multi-page traversal
или pagination behavior в документации больше нет.

## Live spike: controlled analytics follow-up (2026-09-16)

### Разрешённые изменения

По явному разрешению пользователя создан один временный набор с префиксом `[TEST CODEX]`:

| Тип | Количество | Обезличенный reference |
|---|---:|---|
| Contact | 1 | `contact:sha256:55ce2261e6fa` |
| Company | 1 | `company:sha256:7ff1a67661c7` |
| Lead, связанная с contact/company | 1 | `lead:sha256:6dbcc46c3951` |
| Task на test lead | 1 | `task:sha256:3955a981da3d` |
| Common note на test lead | 1 | `common_note:sha256:3a9acbf97939` |
| Изменение только test lead | 1 PATCH | rename field `name`, reference test lead выше |

Numeric IDs держались только в памяти; таблица содержит односторонние opaque references.
Объекты можно найти в тестовом аккаунте по префиксу `[TEST CODEX]`. Ничего не удалялось;
существующие CRM entities не менялись; phone notes и calls не создавались. Первая попытка
создать task вернула HTTP 400 и не продолжила сценарий; после read-only получения task type
shape task был успешно создан HTTP 200. Error body не читался и не сохранялся.

### Observed events

- После создания/связи/note/update `GET /api/v4/events?limit=250&page=1` вернул HTTP 200
  с 11 target events в первом immediate poll. Observed types: `contact_added`,
  `company_added`, `lead_added`, `entity_linked`, `task_added`, `common_note_added`,
  `name_field_changed`. Это ровно наблюдённый набор для test actions, не полный catalog
  amoCRM.
- Event top-level response fields: `_embedded`, `_links`, `_page`; event fields:
  `_embedded`, `_links`, `account_id`, `created_at`, `created_by`, `entity_id`,
  `entity_type`, `id`, `oauth_client_uuid`, `type`, `value_after`, `value_before`.
  Shapes: `id`/`type` string; author/timestamp/entity ID integer; entity type string;
  before/after array. Presence подтверждены для author, timestamp, entity, `_links.self`
  и `_embedded.entity`; raw values/payload не записывались.
- Corrected read-only dedup polls для contact/company/lead показали 10 target events,
  10 unique nonempty **string** event IDs, 0 duplicates и 0 новых IDs в polls через 0/2/6
  секунд. Первичный 11-й event относится к created task (`task_added`); он не входил в
  последующий entity filter. Это не подтверждает общую доставку, latency или dedup guarantee.
- Events появились в первом immediate poll после lead update; точная server-side latency не
  измерена. Response дал `_page` и `_links` без `next`; `_page_count`/`_total_items`
  отсутствовали. Read-only `page=2` вернул HTTP 204 — это не доказывает general pagination.
- `GET /api/v4/calls?limit=1&page=1` остаётся HTTP 405. Calls и phone notes намеренно не
  создавались, поэтому call direction/duration/author/card не подтверждены.

### Контрактная граница

Live event `id` имеет тип string. Текущий phase-0 mock normalizer допускает только positive
integer ID, поэтому live payload пока должен оставаться `incomplete_event`; это documented
mismatch для следующей integration change, а не основание подменить данные.

### Safety, self-review и remaining concerns

- Использовались только ignored root `.env` credentials. Не выведены и не добавлены в Git
  token, secret, account URL, real user values, email, phone или raw payload.
- Документы обновлены лишь status, field names, primitive shapes, counts, opaque references
  и observed type names. `Plan.md` не менялся; отдельный live helper не сохранялся.
- Остались unobserved: полный event catalog, non-test actions (включая email), delivery/latency
  guarantees, general pagination, role mapping, authorization-code redirect/scopes, widget
  iframe behavior и call reader/events.

### Verification

- `Push-Location backend; D:\табель\.venv312\Scripts\python.exe -m pytest -q` →
  `21 passed`.
- UTF-8 doc consistency check подтвердил presence observed-type, string-ID и calls-405
  facts во всех релевантных документах.
- Secret scan сравнил значения из ignored `.env` с tracked diff только в памяти → pass.
- `git diff --check` → exit code 0.
