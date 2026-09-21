# amoCRM Widget Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать безопасные нативные настройки виджета amoCRM с двумя вкладками, единым атомарным сохранением пользователей и групп и восстановлением состояния с backend.

**Architecture:** Виджет монтирует изолированный settings-controller только в `advancedSettings`, а запросы выполняет через официальный `this.$authorizedAjax()`, который добавляет одноразовый `X-Auth-Token`. Backend проверяет HS256 JWT, его issuer/audience/client UUID/срок и затем применяет существующий `AccessPolicy`; единый snapshot читается и сохраняется account-scoped транзакцией с optimistic revision.

**Tech Stack:** Python 3.12, FastAPI 0.110, SQLAlchemy 2.0, Alembic 1.13, Pydantic 2.6, python-jose 3.3, PostgreSQL/SQLite tests, AMD JavaScript, jQuery, Node.js test runner, jsdom.

**Spec:** `docs/superpowers/specs/2026-09-19-amocrm-settings-design.md`

## Global Constraints

- Интерфейс существует только в `advanced_settings`; рабочий `init` не монтирует редактор настроек.
- Ровно две вкладки: «Пользователи» и «Настройки»; обе сохраняются одной нативно оформленной кнопкой.
- `frontend/admin.html` остаётся неподключённым прототипом и не изменяется.
- Группы учёта независимы от групп amoCRM; `rights.group_id` используется только для визуальной группировки списка.
- Браузер не получает OAuth access/refresh token и не доказывает полномочия значениями `account_id`, `user_id` или `role`.
- Widget-to-backend запросы используют официальный `$authorizedAjax()` и проверяемый `X-Auth-Token`; разрешённые CORS origins ограничены доменами amoCRM/Kommo и настроенными origins.
- `track_time=true` требует одну активную группу; `hide_widget` никогда не меняет `track_time`.
- Группы и memberships с историей не удаляются физически; они деактивируются.
- Время хранится в UTC, расписание группы задаётся локальным временем и валидным IANA timezone.
- Ошибка в любой части snapshot откатывает всю транзакцию и возвращает стабильный `code`, русское `message` и `field` при ошибке поля.
- Секреты, OAuth tokens, `X-Auth-Token` и полные персональные payload не логируются и не попадают в Git.
- Миграция фазы имеет номер `010`; её upgrade/downgrade проверяются на реальном PostgreSQL.
- Каждый task выполняется через TDD, отдельный implementer-agent и отдельный reviewer-agent; следующий task начинается только после исправления замечаний текущего.

## Review Focus

1. Подделанный, просроченный, выпущенный для другого audience/issuer/client UUID `X-Auth-Token` должен дать `401` без обращения к settings service — тестируется в Task 1.
2. Два администратора сохраняют разные версии: устаревшая `revision` должна дать `409 SETTINGS_VERSION_CONFLICT` и не затереть более свежие данные — тестируется в Task 4.
3. Два новых названия, различающиеся пробелами/регистром (` Sales ` и `sales`), должны дать `409 GROUP_DUPLICATE` внутри аккаунта, но быть разрешены в разных аккаунтах — тестируется в Tasks 2 и 4.
4. Опасный текст в имени/email/названии группы (`<img onerror=...>`) должен отображаться как текст и не создавать HTML-узлы — тестируется в Task 5.
5. `429` с `Retry-After` и любая ошибка сохранения должны оставить несохранённые значения на экране и повторная попытка должна отправить тот же snapshot — тестируется в Task 6.

---

## File Map

- `backend/app/core/widget_auth.py` — строгая проверка одноразового JWT amoCRM и построение verified `RequestContext`.
- `backend/app/schemas/settings_snapshot.py` — единственный публичный контракт snapshot, групп и пользователей.
- `backend/app/services/settings_snapshot_service.py` — чтение, нормализация, проверка и атомарное сохранение snapshot.
- `backend/app/api/v1/settings.py` — `GET/PUT /api/v1/settings/snapshot`.
- `backend/app/api/v1/users.py` — read-only `GET /api/v1/settings/users`.
- `backend/app/api/v1/groups.py` — read-only `GET /api/v1/settings/groups`.
- `frontend/settings/settings.html` — доступная разметка двух вкладок и одной кнопки.
- `frontend/settings/settings.js` — локальное состояние, безопасный render, validation, load/save и errors.
- `frontend/settings/settings.css` — стили только под `.timesheet-settings`.
- `widget/script.js` — amoCRM lifecycle adapter; бизнес-логика формы остаётся во frontend module.
- `build_widget.ps1` — воспроизводимая упаковка settings assets.

### Task 1: Проверяемая авторизация браузерного виджета

**Files:**
- Create: `backend/app/core/widget_auth.py`
- Modify: `backend/app/api/v1/dependencies.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/integration/test_widget_auth.py`

**Interfaces:**
- Consumes: `RequestContext(account_id: int, user: User, privileges_verified: bool)` и `OAuthConnection.account_url`.
- Produces: `decode_widget_token(token: str, *, secret: str, audience: str, client_uuid: str) -> WidgetTokenClaims`; `get_request_context()` принимает либо verified `X-Auth-Token`, либо существующий server OAuth Bearer flow.

- [ ] **Step 1: Написать failing tests для допустимого и недопустимых токенов**

```python
@pytest.mark.parametrize("mutation", ["expired", "wrong_audience", "wrong_issuer", "wrong_client"])
def test_widget_token_rejects_untrusted_claims(client, signed_widget_token, mutation):
    token = signed_widget_token(mutation=mutation)
    response = client.get("/api/v1/settings/20", headers={"X-Auth-Token": token})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMO_WIDGET_TOKEN_INVALID"

def test_widget_token_builds_verified_context(client, signed_widget_token, admin_user):
    response = client.get(
        "/api/v1/settings/20",
        headers={"X-Auth-Token": signed_widget_token(user_id=admin_user.amocrm_user_id)},
    )
    assert response.status_code != 401
```

- [ ] **Step 2: Запустить tests и увидеть ожидаемое падение**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/integration/test_widget_auth.py -q`

Expected: FAIL при импорте `app.core.widget_auth` или `401` для valid token.

- [ ] **Step 3: Реализовать строгую проверку JWT и dependency branch**

```python
@dataclass(frozen=True)
class WidgetTokenClaims:
    account_id: int
    user_id: int
    issuer: str
    token_id: str

def decode_widget_token(token: str, *, secret: str, audience: str, client_uuid: str) -> WidgetTokenClaims:
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=audience,
        options={"require_exp": True, "require_iat": True, "require_nbf": True, "require_jti": True},
    )
    if payload.get("client_uuid") != client_uuid:
        raise WidgetTokenInvalid()
    return WidgetTokenClaims(
        account_id=positive_int(payload.get("account_id")),
        user_id=positive_int(payload.get("user_id")),
        issuer=trusted_amocrm_origin(payload.get("iss")),
        token_id=str(UUID(payload["jti"])),
    )
```

В `get_request_context()` при наличии `X-Auth-Token`: проверить подпись секретом `AMOCRM_CLIENT_SECRET`, audience равным origin из `AMOCRM_REDIRECT_URI`, точное совпадение issuer с `OAuthConnection.account_url`, `client_uuid == AMOCRM_CLIENT_ID`, активную connection и активного user; затем обновить live rights существующим server-side OAuth клиентом и только после этого вернуть `privileges_verified=True`. Никакого fallback на browser IDs.

- [ ] **Step 4: Проверить valid, forged, expired и Bearer regression paths**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/integration/test_widget_auth.py tests/integration/test_request_context.py -q`

Expected: PASS; valid widget JWT создаёт context, четыре подделки дают нормализованный `401`, Bearer tests не меняются.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/widget_auth.py backend/app/api/v1/dependencies.py backend/app/core/config.py backend/tests/integration/test_widget_auth.py .env.example
git commit -m "feat: verify amoCRM widget request tokens"
```

### Task 2: Модель данных и миграция 010

**Files:**
- Create: `backend/migrations/versions/010_widget_settings_snapshot.py`
- Modify: `backend/app/models/widget_settings.py`
- Modify: `backend/app/models/widget_group.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/services/user_sync_service.py`
- Modify: `backend/tests/integration/test_migrations.py`
- Modify: `backend/tests/integration/test_user_sync.py`
- Modify: `backend/tests/unit/test_models.py`

**Interfaces:**
- Consumes: observed `User.amocrm_rights["group_id"]`, existing historical `WidgetGroup`/`GroupMember` rows.
- Produces: `WidgetSettings.support_phone`, `allowed_statuses`, `default_allow_restart_session`, `revision`; `WidgetGroup.name_key`, `allow_restart_session`; `User.amocrm_group_id`.

- [ ] **Step 1: Добавить failing model и migration tests**

```python
def test_group_name_key_is_unique_per_account(db):
    db.add_all([
        WidgetGroup(account_id=7, name=" Sales ", name_key="sales"),
        WidgetGroup(account_id=7, name="sales", name_key="sales"),
    ])
    with pytest.raises(IntegrityError):
        db.commit()

def test_same_group_name_key_is_allowed_in_different_accounts(db):
    db.add_all([
        WidgetGroup(account_id=7, name="Sales", name_key="sales"),
        WidgetGroup(account_id=8, name="sales", name_key="sales"),
    ])
    db.commit()
```

Расширить real-PostgreSQL migration test: upgrade до `010`, проверить defaults/revision/unique `(account_id,name_key)`, downgrade и повторный upgrade без потери существующих групп и memberships.

- [ ] **Step 2: Запустить узкие tests и подтвердить отсутствие колонок/revision 010**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_models.py tests/integration/test_user_sync.py -q`

Expected: FAIL на неизвестных model attributes.

- [ ] **Step 3: Добавить колонки и безопасный backfill**

```python
support_phone = Column(String(64), nullable=True)
allowed_statuses = Column(JSON, nullable=False, default=lambda: ["working", "break", "finished"])
default_allow_restart_session = Column(Boolean, nullable=False, default=False)
revision = Column(Integer, nullable=False, default=1)

name_key = Column(String(255), nullable=False)
allow_restart_session = Column(Boolean, nullable=False, default=False)

amocrm_group_id = Column(Integer, nullable=True)
```

В migration заполнить `name_key = lower(trim(name))`; если внутри одного аккаунта уже есть коллизия, остановить upgrade с понятным исключением до добавления unique constraint. Downgrade разрешён только пока новые колонки содержат defaults и revision равна `1`; иначе он останавливается до удаления данных фазы 3. `UserSyncService` сохраняет только integer `rights.group_id`, иначе `None`; имя amoCRM-группы не выдумывать, UI использует `Группа amoCRM #<id>`.

- [ ] **Step 4: Запустить model/user-sync tests и реальный PostgreSQL migration cycle**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_models.py tests/integration/test_user_sync.py -q`

Run with disposable PostgreSQL: `$env:TEST_POSTGRES_ADMIN_URL='postgresql://postgres:postgres@127.0.0.1:<port>/postgres'; ..\.venv312\Scripts\python.exe -m pytest tests/integration/test_migrations.py -q`

Expected: PASS; `alembic heads` показывает ровно `010 (head)`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models backend/app/services/user_sync_service.py backend/migrations/versions/010_widget_settings_snapshot.py backend/tests
git commit -m "feat: persist phase 3 settings snapshot"
```

### Task 3: Контракты чтения admin snapshot

**Files:**
- Create: `backend/app/schemas/settings_snapshot.py`
- Create: `backend/app/services/settings_snapshot_service.py`
- Create: `backend/app/api/v1/users.py`
- Create: `backend/app/api/v1/groups.py`
- Modify: `backend/app/api/v1/settings.py`
- Modify: `backend/app/services/__init__.py`
- Modify: `backend/app/main.py`
- Delete: `backend/app/services/settings_service.py`
- Test: `backend/tests/api/test_settings.py`
- Test: `backend/tests/api/test_groups.py`
- Modify: `backend/tests/integration/test_request_context.py`
- Modify: `backend/tests/integration/test_authorized_routes.py`

**Interfaces:**
- Consumes: verified `RequestContext`, Task 2 columns and current active/historical memberships.
- Produces: `SettingsSnapshotService.load(context) -> SettingsSnapshotResponse`; `GET /api/v1/settings/snapshot`, `/settings/users`, `/settings/groups`.

- [ ] **Step 1: Зафиксировать response schema и admin/account tests**

```python
def test_admin_snapshot_is_account_scoped(scoped_client):
    response = scoped_client("admin").get("/api/v1/settings/snapshot")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"revision", "settings", "groups", "users"}
    assert {u["amocrm_user_id"] for u in body["users"]} == {101, 102, 103}
    assert all(group["account_id"] == 10 for group in body["groups"])

@pytest.mark.parametrize("actor", ["employee", "manager"])
def test_snapshot_requires_live_admin(scoped_client, actor):
    response = scoped_client(actor).get("/api/v1/settings/snapshot")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"
```

- [ ] **Step 2: Запустить tests и получить 404/import failure**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/api/test_settings.py tests/api/test_groups.py -q`

Expected: FAIL, новые routers/schema/service отсутствуют.

- [ ] **Step 3: Реализовать строгие Pydantic contracts**

```python
class SettingsSnapshotResponse(BaseModel):
    revision: int = Field(ge=1)
    settings: AccountSettings
    groups: list[SettingsGroup]
    users: list[SettingsUser]

class SettingsUser(BaseModel):
    amocrm_user_id: int
    name: str
    email: str | None
    avatar_url: str | None
    amocrm_group_id: int | None
    amocrm_group_label: str
    is_active: bool
    track_time: bool
    hide_widget: bool
    group_id: int | None
```

`load()` создаёт default `WidgetSettings` только внутри write endpoint; GET возвращает in-memory defaults с revision `1`, сортирует amoCRM groups/users стабильно, включает неактивных пользователей только если у них есть historical membership. Все три endpoints вызывают `AccessPolicy(db, context).is_admin()` до query. Старые `/{account_id}` и `/reset` handlers и несовместимый `SettingsService` удаляются; security regression tests переводятся на `/snapshot`, где account берётся только из verified context.

- [ ] **Step 4: Проверить response shape, denial и account isolation**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/api/test_settings.py tests/api/test_groups.py tests/integration/test_authorized_routes.py -q`

Expected: PASS без утечки чужих users/groups и без регрессии старых routes.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/schemas/settings_snapshot.py backend/app/services/settings_snapshot_service.py backend/app/services/__init__.py backend/app/api/v1/settings.py backend/app/api/v1/users.py backend/app/api/v1/groups.py backend/app/main.py backend/tests/api backend/tests/integration/test_request_context.py backend/tests/integration/test_authorized_routes.py
git rm backend/app/services/settings_service.py
git commit -m "feat: expose admin settings snapshot"
```

### Task 4: Атомарное и идемпотентное сохранение snapshot

**Files:**
- Modify: `backend/app/schemas/settings_snapshot.py`
- Modify: `backend/app/services/settings_snapshot_service.py`
- Modify: `backend/app/api/v1/settings.py`
- Test: `backend/tests/api/test_settings.py`
- Test: `backend/tests/api/test_groups.py`

**Interfaces:**
- Consumes: `SettingsSnapshotUpdate(revision, settings, groups, users)`; new groups use `client_key: str`, persisted groups use `id: int`.
- Produces: `SettingsSnapshotService.save(context, payload) -> SettingsSnapshotResponse`; `PUT /api/v1/settings/snapshot`.

- [ ] **Step 1: Написать failing transaction/conflict/idempotency tests**

```python
def test_save_is_atomic_when_one_user_has_no_group(admin_client, db, valid_snapshot):
    before = dump_account_state(db, 10)
    valid_snapshot["users"][0].update(track_time=True, group_ref=None)
    response = admin_client.put("/api/v1/settings/snapshot", json=valid_snapshot)
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "TRACKED_USER_GROUP_REQUIRED",
        "message": "Для учёта сотруднику нужно назначить группу.",
        "field": "users.0.group_ref",
    }
    assert dump_account_state(db, 10) == before

def test_stale_revision_does_not_overwrite(admin_client, valid_snapshot):
    first = admin_client.put("/api/v1/settings/snapshot", json=valid_snapshot)
    second = admin_client.put("/api/v1/settings/snapshot", json=valid_snapshot)
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SETTINGS_VERSION_CONFLICT"
```

Также добавить tests: duplicate normalized name; same name across accounts; duplicate/unknown IDs; inactive/foreign manager; invalid IANA timezone; `work_start_time == work_end_time`; second active membership; repeated canonical payload with returned revision does not create rows; `hide_widget` independent; deactivation preserves historical rows.

- [ ] **Step 2: Запустить save tests и увидеть method/route failures**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/api/test_settings.py tests/api/test_groups.py -q`

Expected: FAIL на `PUT /snapshot` или отсутствующем `save()`.

- [ ] **Step 3: Реализовать validate-then-apply в одной транзакции**

```python
def save(self, context: RequestContext, payload: SettingsSnapshotUpdate) -> SettingsSnapshotResponse:
    self._require_admin(context)
    current = self._settings_for_update(context.account_id)
    if payload.revision != current.revision:
        raise SettingsConflict("SETTINGS_VERSION_CONFLICT", "Настройки уже изменены другим администратором.")
    normalized = self._validate_snapshot(context.account_id, payload)
    try:
        self._apply_settings(current, normalized.settings)
        group_ids = self._upsert_groups(context.account_id, normalized.groups)
        self._replace_active_memberships(context.account_id, normalized.users, group_ids)
        current.revision += 1
        self._db.commit()
    except Exception:
        self._db.rollback()
        raise
    return self.load(context)
```

Validation выполняется до mutation: unique IDs/client keys, `casefold(trim(name))`, `ZoneInfo(timezone)`, manager принадлежит аккаунту/активен/имеет observed role, active tracked user имеет ровно одну active group. Existing group omission означает deactivation, не delete. Existing membership закрывается через `is_active=False`; повторный canonical payload создаёт максимум одну новую active row и сохраняет старые historical rows.

- [ ] **Step 4: Запустить save suite и проверить rollback вручную через assertions**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest tests/api/test_settings.py tests/api/test_groups.py -q`

Expected: PASS; все `409` содержат stable code/message/field, а state до и после ошибочного save одинаков.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/schemas/settings_snapshot.py backend/app/services/settings_snapshot_service.py backend/app/api/v1/settings.py backend/tests/api/test_settings.py backend/tests/api/test_groups.py
git commit -m "feat: save settings snapshot atomically"
```

### Task 5: Settings controller и нативный UI двух вкладок

**Files:**
- Create: `package.json`
- Create: `frontend/settings/settings.html`
- Create: `frontend/settings/settings.js`
- Create: `frontend/settings/settings.css`
- Create: `frontend/tests/settings-controller.test.js`

**Interfaces:**
- Consumes: Task 3/4 snapshot JSON and injected transport `{load(): Promise<snapshot>, save(payload): Promise<snapshot>}`.
- Produces: `SettingsController.mount(root, transport)`, `.serialize()`, `.validate()`, `.save()`, `.destroy()`.

- [ ] **Step 1: Добавить Node/jsdom setup и failing UI/state tests**

```javascript
test('mount renders exactly two tabs and escapes server text', async () => {
  const root = document.querySelector('#list_page_holder');
  const controller = SettingsController.mount(root, fakeTransport({
    users: [{ name: '<img src=x onerror=alert(1)>', email: 'x@example.test' }]
  }));
  await controller.ready;
  assert.deepEqual([...root.querySelectorAll('[role=tab]')].map(x => x.textContent), ['Пользователи', 'Настройки']);
  assert.equal(root.querySelector('img[src="x"]'), null);
  assert.match(root.textContent, /<img src=x/);
});

test('hide_widget does not change track_time', async () => {
  const controller = await mountedController();
  controller.setUser(101, { track_time: true, group_ref: 'id:10' });
  controller.setUser(101, { hide_widget: true });
  assert.deepEqual(controller.serialize().users[0], {
    amocrm_user_id: 101, track_time: true, hide_widget: true, group_ref: 'id:10'
  });
});
```

- [ ] **Step 2: Установить pinned test dependencies и увидеть failing tests**

`package.json` задаёт `"engines": {"node": ">=22"}`, script `"test:settings": "node --test frontend/tests/settings-controller.test.js"` и exact dev dependency `"jsdom": "26.1.0"`; строка `package-lock.json` удаляется из `.gitignore`, lockfile коммитится.

Run: `npm install`

Run: `npm run test:settings`

Expected: FAIL, settings module/markup отсутствуют.

- [ ] **Step 3: Реализовать controller и безопасный DOM render**

```javascript
function text(tag, className, value) {
  var node = document.createElement(tag);
  node.className = className;
  node.textContent = value == null ? '' : String(value);
  return node;
}

function validate(state) {
  var errors = [];
  state.users.forEach(function (user, index) {
    if (user.track_time && !user.group_ref) {
      errors.push({ code: 'TRACKED_USER_GROUP_REQUIRED', field: 'users.' + index + '.group_ref' });
    }
  });
  return errors;
}
```

Render: loading/denied/error state, search by normalized name/email, headings by `amocrm_group_label`, disabled assignments for inactive users, group editor fields, account fields and exactly one `.button-input_blue.timesheet-settings__save`. Все значения вставляются через `textContent`/DOM properties; CSS selectors начинаются с `.timesheet-settings`.

- [ ] **Step 4: Проверить tabs, search, grouping, validation, XSS и независимые flags**

Run: `npm run test:settings`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add package.json package-lock.json frontend/settings frontend/tests/settings-controller.test.js .gitignore
git commit -m "feat: build native amoCRM settings editor"
```

### Task 6: amoCRM lifecycle, authorized transport и обработка ошибок

**Files:**
- Modify: `package.json`
- Modify: `widget/manifest.json`
- Modify: `widget/script.js`
- Modify: `widget/styles.css`
- Create: `frontend/tests/widget-lifecycle.test.js`
- Modify: `frontend/tests/settings-controller.test.js`

**Interfaces:**
- Consumes: `SettingsController` из Task 5 и amoCRM `self.$authorizedAjax(options)`.
- Produces: `createSettingsTransport(widget)`; callbacks `settings`, `advancedSettings`, `onSave`, `init`, `destroy` with separated ownership.

- [ ] **Step 1: Написать failing lifecycle/transport/error tests**

```javascript
test('init never mounts settings editor', () => {
  const widget = makeWidget({ area: 'lcard' });
  widget.callbacks.init();
  assert.equal(settingsController.mount.mock.calls.length, 0);
});

test('advancedSettings loads through authorizedAjax and one button saves both tabs', async () => {
  const widget = makeWidget({ area: 'advanced_settings' });
  widget.callbacks.advancedSettings();
  await flushPromises();
  document.querySelector('.timesheet-settings__save').click();
  assert.equal(widget.$authorizedAjax.mock.calls[0][0].method, 'GET');
  assert.equal(widget.$authorizedAjax.mock.calls[1][0].method, 'PUT');
  assert.deepEqual(JSON.parse(widget.$authorizedAjax.mock.calls[1][0].data), controller.serialize());
});

test('rate limit preserves draft and exposes retry delay', async () => {
  const controller = await mountedController({ saveRejects: { status: 429, retryAfter: '30' } });
  controller.setSupportPhone('+375 29 000-00-00');
  await assert.rejects(controller.save());
  assert.equal(controller.serialize().settings.support_phone, '+375 29 000-00-00');
  assert.match(document.body.textContent, /30 секунд/);
});
```

- [ ] **Step 2: Запустить lifecycle tests и увидеть stubs/unauthorized transport failure**

Run: `npm run test:settings -- frontend/tests/widget-lifecycle.test.js`

Expected: FAIL, `advancedSettings`/`onSave` ещё возвращают stubs.

- [ ] **Step 3: Реализовать adapter без OAuth token в браузере**

```javascript
function createSettingsTransport(widget) {
  return {
    load: function () {
      return toPromise(widget.$authorizedAjax({
        url: apiUrl(widget) + '/settings/snapshot', method: 'GET', dataType: 'json'
      }));
    },
    save: function (payload) {
      return toPromise(widget.$authorizedAjax({
        url: apiUrl(widget) + '/settings/snapshot', method: 'PUT',
        contentType: 'application/json', dataType: 'json', data: JSON.stringify(payload)
      }));
    }
  };
}
```

`advancedSettings` монтирует assets в `#list_page_holder`; кнопка и `onSave` вызывают один `controller.save()`. `settings` оставляет стандартный install form. `destroy` снимает handlers и settings DOM, не смешивая их с working overlay. Mapping ошибок: 401 — переподключение, 403 — read-denied, 404 — reload conflict, 409 — field/global error, 429 — retry message с bounded `Retry-After`; draft не заменяется при failure, canonical snapshot заменяет baseline только после success.

Обновить `test:settings`, добавив `frontend/tests/widget-lifecycle.test.js` вторым явным путём, чтобы command одинаково работал в PowerShell и CI без shell glob expansion.

- [ ] **Step 4: Запустить весь frontend suite**

Run: `npm run test:settings`

Expected: PASS; `init` не создаёт `.timesheet-settings`, обе вкладки сохраняются одним request, ошибки не стирают draft.

- [ ] **Step 5: Commit**

```powershell
git add package.json widget/manifest.json widget/script.js widget/styles.css frontend/tests
git commit -m "feat: connect amoCRM settings lifecycle"
```

### Task 7: Сборка, browser smoke и проверка всей фазы

**Files:**
- Modify: `package.json`
- Modify: `build_widget.ps1`
- Modify: `validate_widget_zip.py`
- Create: `frontend/tests/settings-smoke.test.js`
- Modify: `docs/api-contract.md`
- Modify: `docs/amocrm-integration-limits.md`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: все backend/frontend/widget artifacts Tasks 1–6.
- Produces: проверяемый `widget.zip` build artifact (ignored by Git), phase-3 local-completion evidence in `Plan.md`.

- [ ] **Step 1: Добавить failing package/browser smoke assertions**

```javascript
test('advanced settings smoke saves a canonical snapshot', async () => {
  const app = await bootAmoHarness({ initialSnapshot });
  await app.openAdvancedSettings();
  app.changeUser(101, { track_time: true, group_ref: 'client:sales' });
  app.createGroup({ client_key: 'sales', name: 'Sales', timezone: 'Europe/Minsk' });
  await app.clickSave();
  assert.equal(app.requests.at(-1).method, 'PUT');
  assert.equal(app.visibleTabs().join(','), 'Пользователи,Настройки');
  assert.equal(app.settingsEditorInWorkingArea(), false);
});
```

Validator обязан ожидать `manifest.json`, `script.js`, `styles.css`, `settings/settings.html`, `settings/settings.js`, `settings/settings.css`, обе i18n и обязательные images.

Добавить `frontend/tests/settings-smoke.test.js` третьим явным путём в `test:settings`.

- [ ] **Step 2: Запустить smoke/validator и подтвердить отсутствие settings assets в ZIP**

Run: `npm run test:settings`

Run: `powershell -ExecutionPolicy Bypass -File .\build_widget.ps1 -ApiUrl "https://storage-turkey-multitask.ngrok-free.dev/api/v1"`

Run: `.\.venv312\Scripts\python.exe .\validate_widget_zip.py .\widget.zip`

Expected before implementation: validator FAIL из-за отсутствующих `settings/*`.

- [ ] **Step 3: Обновить reproducible builder, validator и docs**

Builder копирует `frontend/settings/*` в staging `settings/`, подставляет API URL только в staging copy, создаёт архив, всегда удаляет только проверенный staging directory в workspace. Source files не переписываются. Validator проверяет UTF-8/JSON, отсутствие `.env`, secrets и source maps, ровно заявленные locations и все runtime files.

Документация фиксирует `$authorizedAjax`/`X-Auth-Token`, HS256 claims и то, что browser IDs/OAuth tokens не являются widget credentials, на основании официальных страниц amoCRM:

- `https://www.amocrm.ru/developers/content/web_sdk/mechanics`
- `https://www.amocrm.ru/developers/content/oauth/disposable-tokens`

- [ ] **Step 4: Выполнить phase gate**

Run: `cd backend; ..\.venv312\Scripts\python.exe -m pytest -q`

Run: `npm run test:settings`

Run: `git diff --check`

Run: real PostgreSQL migration suite с `TEST_POSTGRES_ADMIN_URL`, затем `cd backend; ..\.venv312\Scripts\alembic.exe heads`.

Run: build + `validate_widget_zip.py` из Step 2.

Expected: все suites PASS; Alembic имеет один `010 (head)`; архив не содержит секретов и содержит весь runtime.

- [ ] **Step 5: Провести независимый whole-phase review и исправить все Critical/Important замечания**

Reviewer сверяет spec, Review Focus, account isolation, transaction rollback, UI lifecycle, package contents и отсутствие credentials. После каждого исправления повторить затронутый test и полный phase gate.

- [ ] **Step 6: Обновить `Plan.md` фактическими результатами**

Отметить все локальные пункты фазы 3 `[x]`, статус «Локально реализована» с датой и командами, заполнить «Факт», добавить отчёт: что сделано; созданные/изменённые файлы; что пользователь уже может проверить; блокеры/риски. Complete live amoCRM smoke и детальный acceptance checklist отложены до локальной реализации всех фаз и не должны быть выданы за выполненные.

- [ ] **Step 7: Commit and push phase**

```powershell
git add package.json build_widget.ps1 validate_widget_zip.py frontend/tests/settings-smoke.test.js docs/api-contract.md docs/amocrm-integration-limits.md Plan.md
git commit -m "docs: complete phase 3 widget settings"
git push origin main
```

## Ручная проверка после автоматических gate

1. Собрать ZIP командой из Task 7 и загрузить его в тестовую интеграцию amoCRM.
2. Открыть расширенные настройки: видны только «Пользователи» и «Настройки».
3. Создать тестовую группу, назначить пользователя, включить `track_time` и отдельно `hide_widget`, нажать единственную синюю кнопку сохранения.
4. Перезагрузить страницу и убедиться, что canonical значения восстановились.
5. Открыть рабочую область amoCRM и убедиться, что settings editor там отсутствует.
6. Проверить под employee/manager, что форма настроек закрыта сообщением о недостатке доступа.
