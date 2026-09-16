# Матрица требований виджета «Табель»

Источник: требования проекта, фактический код, mock-контракты и live read-only spike
от 2026-09-16. Статус «mock» означает, что поведение проверено изолированным
ответом API, а не тестовым аккаунтом amoCRM. Он не является доказательством
доступности поля в конкретном аккаунте.

| Область | Требование | Фактическое состояние | Контракт фазы 0 | Статус проверки |
|---|---|---|---|---|
| Установка | Совместимый `widget.zip` для amoMarket | В репозитории есть исходный `widget/`, архива нет | Перед публикацией собрать архив из `widget/` и загрузить в тестовый аккаунт | Не проверено live |
| Manifest | Расширенные настройки виджета | `locations` содержит только `advanced_settings`; `advanced.title` есть | Location допустим для собственной страницы настроек; не добавлять неиспользуемые locations | Локально подтверждено |
| Scopes | Минимальные OAuth-права | В `manifest.json` scopes не задаются и локально не известны | Не выдумывать scopes; зафиксировать их после установки OAuth-интеграции | Не проверено live |
| Контекст | Account, user и права берутся из amoCRM | `GET /api/v4/account` — 200; `GET /api/v4/users?limit=1&page=1` — 200; widget SDK fallback всё ещё demo-only | SDK-значения — только UI-контекст; backend доверяет server-side OAuth token, account и users API | Account/user source fields live подтверждены; policy mapping нет |
| OAuth | Authorization code, access и refresh token | Live access token принят API; refresh grant — 200 и возвращает обе token-пары | JSON grants; обязательные `access_token`, `refresh_token`, `expires_in`; 401 означает refresh/re-auth | Refresh flow live подтверждён; redirect/scopes не повторялись |
| Роли | Admin/ROP/employee для видимости | Users response содержит объект `rights` и поле `role_id`; local RBAC отдельно | Роль не извлекается из SDK payload; mapping требует явной policy | Rights fields live подтверждены; mapping нет |
| Активность | Только события amoCRM и звонки | Controlled `[TEST CODEX]` actions дали 11 events через `GET /api/v4/events?limit=250&page=1` — 200 | Observed shape: string event ID; integer author/timestamp/entity ID; string entity/type; `_links.self`, `_embedded.entity`; adapter mock ещё ожидает integer ID | Ограниченный live field shape/types подтверждён; полный каталог не известен |
| Мышь/клавиатура | Не создают подтверждённую активность без CRM-события | В текущем UI встречается локальный tracking | Такой input не может создавать `confirmed` interval | Зафиксировано контрактом |
| Звонки | Направление, длительность, автор и карточка | `GET /api/v4/calls?limit=1&page=1` — 405 | Неподтверждённый payload хранится как `incomplete_event`; direction/duration/author/card остаются `null` | Reader endpoint/fields не подтверждены |
| Пагинация и задержка | Не терять повторные/задержанные CRM-события | Users list live содержит `_page`, `_page_count`, `_total_items`; при `limit=1` наблюдались metadata 1/1/1. Events response содержит только `_page` и `_links` без next; `page=2` дал 204 | Параметры cursor/page и окно задержки не определены до live spike | Users pagination metadata наблюдались; events: один текущий page и пустой `page=2`; general traversal не проверен. Для 10 target events нет дублей/новых ID за 0/2/6 с |
| Статусы | Работаю, Перерыв, Закончил(а) | Есть legacy `/sessions/*`, не совпадающий с целевым URL и idempotency | Целевой transition contract приведён в `api-contract.md`; его реализация — следующая фаза | Контракт описан |
| Команда и timeline | Видимость по роли и 7-дневная лента | Есть разрозненные team endpoints и frontend demo data | Целевые team/timeline JSON описаны в `api-contract.md`; доступ проверяется backend после identity | Контракт описан |
| Отчёт и Excel | До 3 месяцев; без activity в Excel | Есть legacy reports/excel routes, целевой export не реализован | Целевой report/export contract описан; диапазон > 3 месяцев — `REPORT_RANGE_LIMIT` | Контракт описан |

## Проверяемые границы

- `backend/tests/integration/test_amocrm_contract.py` проверяет обмен authorization code,
  refresh token, отсутствие access token, 401 от account endpoint, полное CRM-событие и
  неполный звонок.
- Адаптер не принимает `account_id` или `user_id`, переданные browser widget, как доказательство
  личности.
- Переход от mock-контракта к live-тесту требует сохранить обезличенный ответ и обновить
  таблицу только с реально присутствующими полями.
- Live spike фазы 0 не выводил и не сохранял token, secret, user values, email, phone,
  name или полный response payload; в документах оставлены только HTTP status, имена
  полей, типы и счётчики.

## Известное расхождение с кодом

Уже существующие routes (`/api/v1/sessions/*`, legacy reports/excel) не реализуют целевой
контракт из `docs/api-contract.md`. Это явно зафиксировано, чтобы следующие фазы не считали
старые endpoint-ы готовой интеграцией amoCRM.
