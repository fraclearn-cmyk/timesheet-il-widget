# Ограничения интеграции amoCRM

Статус на 2026-09-16: выполнен безопасный live read-only spike. Ни token, ни secret,
ни пользовательские значения, ни полный payload не записывались в repository, report или
console output. В этом документе «неизвестно» не заменяется предположением.

## Подтверждено live read-only spike

- `GET /api/v4/account` вернул HTTP 200 с `application/hal+json`. Подтверждены только
  имена source fields: `_links`, `id`, `current_user_id`, lifecycle/account settings fields
  и audit fields; их значения не сохранены.
- `GET /api/v4/users?limit=1&page=1` вернул HTTP 200 с одним элементом и meta fields
  `_page`, `_page_count`, `_total_items` (все integer; observed page/count/items: 1/1/1).
  User shape содержит `_links`, `email`, `id`, `lang`, `name`, `rights`; значения не
  сохранялись. Наблюдалась только metadata одной страницы; обход нескольких страниц и page behavior не проверены.
- `rights` — object. Наблюдались keys для entity permissions, `group_id`, `is_admin`,
  `role_id`, activity/report access и `status_rights`; примитивные types/containers
  подтверждены без значений. Это доказывает доступность rights fields, но не mapping
  amoCRM rights в local Admin/ROP/employee policy.
- `POST /oauth2/access_token` c `grant_type=refresh_token` вернул HTTP 200 JSON с
  `access_token`, `refresh_token`, `expires_in`, `server_time`, `token_type`. Оба token
  были заменены одним атомарным `os.replace` в игнорируемом root `.env`; новый access token
  повторно дал HTTP 200 для account read.
- `GET /api/v4/events?limit=1&page=1` вернул HTTP 204 без JSON body. Поэтому не
  подтверждены event types, author, timestamp, entity, link или events pagination.
- `GET /api/v4/calls?limit=1&page=1` вернул HTTP 405. Reader contract звонков и его
  fields не подтверждены.

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

## Не подтверждено после live read-only spike

| Тема | Что нельзя утверждать до live spike | Безопасный fallback |
|---|---|---|
| OAuth redirect/scopes | Одноразовый authorization code уже очищен; redirect delivery и configured scopes в этом запуске не воспроизводились | Не принимать browser ID как identity; хранить и обновлять server-side token only |
| Account/user/role | Local Admin/ROP/employee mapping по live `rights` и `role_id` | Роль не присваивается автоматически; deny по умолчанию для privileged actions |
| Event analytics | Events endpoint дал 204: нет record/type/author/timestamp/entity/link, events pagination, latency и duplicate delivery | Хранить только полные события; остальные `incomplete_event`; не устанавливать polling/dedup window на догадке |
| Calls | `GET /api/v4/calls` дал 405; reader API, direction, duration, author, associated card/link не известны | Не выводить duration/direction и не создавать confirmed interval из opaque call payload |
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

## Оставшаяся программа live spike

1. Установить архив в тестовый аккаунт и открыть `advanced_settings`.
2. При следующем отдельно разрешённом authorization-code flow проверить redirect delivery
   и scopes без раскрытия code/token. Refresh flow уже подтверждён.
3. Определить и утвердить mapping live `rights`/`role_id` к local policy.
4. Только с отдельным разрешением выполнить изменения сделки, задачи, контакта, компании,
   примечания и email; сверить
   author, timestamp, entity, URL, pagination/cursor, задержку и повторную доставку.
5. Только с отдельным разрешением выполнить входящий и исходящий звонок; проверить direction, duration, author и
   привязанную карточку.
6. Повторить в состояниях «Работаю», «Перерыв», «Закончил(а)» и проверить, что browser
   mouse/keyboard без amoCRM события не меняют confirmed timeline.

До выполнения этой программы завершение фазы — `DONE_WITH_CONCERNS`, а не полностью
live-validated интеграция.
