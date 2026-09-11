# Матрица требований виджета «Табель»

Источник: требования проекта, фактический код и mock-контракты фазы 0 от
2026-09-11. Статус «mock» означает, что поведение проверено изолированным
ответом API, а не тестовым аккаунтом amoCRM. Он не является доказательством
доступности поля в конкретном аккаунте.

| Область | Требование | Фактическое состояние | Контракт фазы 0 | Статус проверки |
|---|---|---|---|---|
| Установка | Совместимый `widget.zip` для amoMarket | В репозитории есть исходный `widget/`, архива нет | Перед публикацией собрать архив из `widget/` и загрузить в тестовый аккаунт | Не проверено live |
| Manifest | Расширенные настройки виджета | `locations` содержит только `advanced_settings`; `advanced.title` есть | Location допустим для собственной страницы настроек; не добавлять неиспользуемые locations | Локально подтверждено |
| Scopes | Минимальные OAuth-права | В `manifest.json` scopes не задаются и локально не известны | Не выдумывать scopes; зафиксировать их после установки OAuth-интеграции | Не проверено live |
| Контекст | Account, user и права берутся из amoCRM | `widget/script.js` читает `AMOCRM.constant('account'/'user')`, но при ошибке подставляет demo ID | SDK-значения — только UI-контекст; backend доверяет лишь server-side OAuth token и проверенному API-ответу | SDK чтение локально; полномочия не проверены live |
| OAuth | Authorization code, access и refresh token | Реального клиента не было; в фазе 0 добавлен строгий adapter | `authorization_code` и `refresh_token` grants, обязательные `access_token`, `refresh_token`, `expires_in`; 401 означает refresh/re-auth | Mock-контракт |
| Роли | Admin/ROP/employee для видимости | Локальный RBAC есть, но его связь с amoCRM не подтверждена | Роль не извлекается из непроверенного SDK payload; необходима отдельная подтверждённая mapping policy | Не проверено live |
| Активность | Только события amoCRM и звонки | Модели есть, ingestion нет | Полный event нормализуется только при ID, type, timestamp, author и entity; иначе `incomplete_event` | Mock-контракт |
| Мышь/клавиатура | Не создают подтверждённую активность без CRM-события | В текущем UI встречается локальный tracking | Такой input не может создавать `confirmed` interval | Зафиксировано контрактом |
| Звонки | Направление, длительность, автор и карточка | Нет подтверждённого reader API/fixture аккаунта | Неподтверждённый payload хранится как `incomplete_event`; direction/duration/author/card остаются `null` | Mock safety fallback |
| Пагинация и задержка | Не терять повторные/задержанные CRM-события | Нет ingestion или live-замеров | Параметры cursor/page и окно задержки не определены до live spike | Не проверено live |
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

## Известное расхождение с кодом

Уже существующие routes (`/api/v1/sessions/*`, legacy reports/excel) не реализуют целевой
контракт из `docs/api-contract.md`. Это явно зафиксировано, чтобы следующие фазы не считали
старые endpoint-ы готовой интеграцией amoCRM.
