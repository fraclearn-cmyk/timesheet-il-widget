# Ограничения интеграции amoCRM

Статус на 2026-09-11: live spike не выполнен. В доступной локальной среде нет
авторизованной amoCRM-сессии и заполненных OAuth client credentials. В этом документе
«неизвестно» не заменяется предположением.

## Подтверждено локально и mock-контрактом

- `widget/manifest.json` использует единственную location `advanced_settings`. Она
  соответствует собственной странице расширенных настроек Web SDK.
- В виджете читаются `AMOCRM.constant('account').id` и
  `AMOCRM.constant('user').{id,name}`. Эти значения доступны UI, но текущий fallback
  подставляет demo account/user и поэтому не пригоден для серверной аутентификации.
- OAuth adapter фазы 0 отправляет server-side `authorization_code` либо
  `refresh_token` grant на `{account_url}/oauth2/access_token`; успешный mock-ответ
  требует `access_token`, `refresh_token`, `expires_in`. Значения токенов не логируются.
- Нет access token — `AmoCRMTokenMissing`; 401 при `GET /api/v4/account` —
  `AmoCRMTokenExpired`, то есть нужен refresh/re-auth, а не доверие к ID из браузера.
- Полное CRM-событие становится `confirmed` только с `id`, `type`, `created_at`,
  `created_by`, `entity_id`, `entity_type`. Пропуски и неизвестный звонок —
  `incomplete_event` с сохранённым raw payload.

## Не подтверждено без тестового аккаунта

| Тема | Что нельзя утверждать до live spike | Безопасный fallback |
|---|---|---|
| OAuth redirect | Реальный delivery authorization code, redirect URI и точный набор scopes текущей интеграции | Не включать OAuth flow в production и не принимать browser ID как identity |
| Account/user/role | Поля account API, user role/rights и их связь с local RBAC | Роль не присваивается автоматически; deny по умолчанию для privileged actions |
| Event analytics | Endpoint, event types, author, timestamp, entity/link, cursor/page, latency и duplicate delivery | Хранить только полные события; остальные `incomplete_event`; не устанавливать polling/dedup window на догадке |
| Calls | Reader API и фактические direction, duration, author, associated card/link | Не выводить duration/direction и не создавать confirmed interval из opaque call payload |
| Browser signals | Доступность события всей страницы из iframe и связь mouse/keyboard с CRM action | Локальные click/keyboard не считаются CRM-активностью |
| Manifest scopes | Передаются ли scopes и permissions через manifest для этого типа виджета | Не добавлять фиктивные manifest fields; проверить настройки OAuth-интеграции в аккаунте |

## Официальные источники, использованные для mock-границы

- [Web SDK: расширенные настройки](https://www.amocrm.ru/developers/content/web_sdk/settings)
  описывает `advanced_settings` и callback `advancedSettings`.
- [Структура виджета](https://www.amocrm.ru/developers/content/integrations/structure)
  описывает контекстные переменные `#ACCOUNT_ID#` и `#USER_ID#`; это не server-side
  удостоверение личности.
- [Web SDK locations](https://www.amocrm.ru/developers/content/web_sdk/start) перечисляет
  доступные locations; только используемая location оставлена в manifest.
- [Возможности телефонии](https://www.amocrm.ru/developers/content/telephony/capabilities-2)
  показывает notification payload, но не подтверждает универсальный API чтения истории
  звонков для данного виджета.

## Обязательная программа live spike

1. Установить архив в тестовый аккаунт и открыть `advanced_settings`.
2. Пройти OAuth без раскрытия code/token в журнале; зафиксировать только имена полей,
   HTTP code и обезличенную форму ответа.
3. Проверить account/user context и документированный источник ролей.
4. Выполнить изменения сделки, задачи, контакта, компании, примечания и email; сверить
   author, timestamp, entity, URL, pagination/cursor, задержку и повторную доставку.
5. Выполнить входящий и исходящий звонок; проверить direction, duration, author и
   привязанную карточку.
6. Повторить в состояниях «Работаю», «Перерыв», «Закончил(а)» и проверить, что browser
   mouse/keyboard без amoCRM события не меняют confirmed timeline.

До выполнения этой программы завершение фазы — `DONE_WITH_CONCERNS`, а не live-validated
интеграция.
