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
