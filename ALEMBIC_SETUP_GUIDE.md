# 🗄️ Alembic Migration Setup Guide

**Дата:** 10.07.2026  
**Статус:** ✅ Alembic настроен

---

## ✅ ЧТО СОЗДАНО

### Файлы Alembic:
1. **alembic.ini** - Конфигурация Alembic
2. **migrations/env.py** - Environment setup
3. **migrations/script.py.mako** - Template для миграций
4. **migrations/versions/** - Папка для миграций

---

## 🚀 КАК ИСПОЛЬЗОВАТЬ

### 1. Запустить PostgreSQL
```bash
cd d:/виджеты/timesheet-il-widget
docker-compose up -d postgres
```

### 2. Создать первую миграцию (автогенерация)
```bash
cd backend
alembic revision --autogenerate -m "Initial migration"
```

Alembic автоматически создаст миграцию на основе моделей:
- work_sessions
- status_transitions
- activity_sessions
- activity_events
- activity_categories
- widget_settings

### 3. Применить миграцию
```bash
alembic upgrade head
```

### 4. Проверить статус
```bash
alembic current
```

### 5. Откатить миграцию (если нужно)
```bash
alembic downgrade -1
```

---

## 📊 ТАБЛИЦЫ КОТОРЫЕ БУДУТ СОЗДАНЫ

### 1. work_sessions
```sql
CREATE TABLE work_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_name VARCHAR(255) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    status VARCHAR(20) NOT NULL,  -- working, break, finished
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_work_time INTEGER DEFAULT 0,
    total_break_time INTEGER DEFAULT 0,
    break_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_work_sessions_user_id ON work_sessions(user_id);
CREATE INDEX idx_work_sessions_status ON work_sessions(status);
CREATE INDEX idx_work_sessions_account_id ON work_sessions(account_id);
```

### 2. status_transitions
```sql
CREATE TABLE status_transitions (
    id SERIAL PRIMARY KEY,
    work_session_id INTEGER NOT NULL REFERENCES work_sessions(id),
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    transition_time TIMESTAMP NOT NULL,
    duration INTEGER,  -- seconds since last transition
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_status_transitions_work_session_id ON status_transitions(work_session_id);
```

### 3. activity_sessions
```sql
CREATE TABLE activity_sessions (
    id SERIAL PRIMARY KEY,
    work_session_id INTEGER NOT NULL REFERENCES work_sessions(id),
    entity_type VARCHAR(50) NOT NULL,  -- lead, contact, company, task
    entity_id INTEGER NOT NULL,
    entity_name VARCHAR(255),
    is_active SMALLINT DEFAULT 1,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration INTEGER,  -- seconds
    last_activity_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_sessions_work_session_id ON activity_sessions(work_session_id);
CREATE INDEX idx_activity_sessions_entity ON activity_sessions(entity_type, entity_id);
CREATE INDEX idx_activity_sessions_is_active ON activity_sessions(is_active);
```

### 4. activity_events
```sql
CREATE TABLE activity_events (
    id SERIAL PRIMARY KEY,
    activity_session_id INTEGER NOT NULL REFERENCES activity_sessions(id),
    event_type VARCHAR(50) NOT NULL,  -- 11 типов событий
    timestamp TIMESTAMP NOT NULL,
    description TEXT,
    event_data JSONB,  -- flexible JSON data
    category_id INTEGER REFERENCES activity_categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_events_activity_session_id ON activity_events(activity_session_id);
CREATE INDEX idx_activity_events_event_type ON activity_events(event_type);
CREATE INDEX idx_activity_events_category_id ON activity_events(category_id);
```

### 5. activity_categories
```sql
CREATE TABLE activity_categories (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#3498db',
    icon VARCHAR(50),
    is_active SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_categories_account_id ON activity_categories(account_id);
CREATE INDEX idx_activity_categories_is_active ON activity_categories(is_active);
```

### 6. widget_settings
```sql
CREATE TABLE widget_settings (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL UNIQUE,
    auto_pause_on_close SMALLINT DEFAULT 1,
    require_category SMALLINT DEFAULT 0,
    track_idle_time SMALLINT DEFAULT 0,
    idle_threshold_minutes INTEGER DEFAULT 5,
    show_team_stats SMALLINT DEFAULT 1,
    enable_reports SMALLINT DEFAULT 1,
    config JSONB,  -- flexible JSON config
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_widget_settings_account_id ON widget_settings(account_id);
```

---

## 🔧 НАСТРОЙКИ

### Connection String (alembic.ini)
```ini
sqlalchemy.url = postgresql://timesheet:timesheet123@localhost:5432/timesheet_db
```

### Изменить connection string:
1. Откройте `alembic.ini`
2. Найдите строку `sqlalchemy.url`
3. Измените на свой:
```ini
sqlalchemy.url = postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

Или используйте переменную окружения:
```bash
# В .env
DATABASE_URL=postgresql://timesheet:timesheet123@postgres:5432/timesheet_db

# В alembic.ini убрать sqlalchemy.url и использовать env.py
```

---

## 📝 КОМАНДЫ ALEMBIC

### Создание миграций
```bash
# Автогенерация на основе моделей
alembic revision --autogenerate -m "Add new column"

# Пустая миграция (для ручного написания)
alembic revision -m "Custom migration"
```

### Применение миграций
```bash
# Применить все
alembic upgrade head

# Применить одну
alembic upgrade +1

# Применить до конкретной
alembic upgrade <revision_id>
```

### Откат миграций
```bash
# Откатить одну
alembic downgrade -1

# Откатить все
alembic downgrade base

# Откатить до конкретной
alembic downgrade <revision_id>
```

### Информация
```bash
# Текущая версия
alembic current

# История миграций
alembic history

# Показать SQL без применения
alembic upgrade head --sql
```

---

## 🐳 DOCKER WORKFLOW

### Полный запуск с миграциями:

```bash
# 1. Запустить контейнеры
cd d:/виджеты/timesheet-il-widget
docker-compose up -d

# 2. Подождать пока PostgreSQL запустится (5-10 сек)
docker-compose logs postgres

# 3. Зайти в backend контейнер
docker-compose exec backend bash

# 4. Применить миграции
alembic upgrade head

# 5. Выйти из контейнера
exit

# 6. Проверить API
# Открыть http://localhost:8000/docs
```

### Или через docker-compose exec:
```bash
docker-compose exec backend alembic upgrade head
```

---

## ✅ ПРОВЕРКА МИГРАЦИЙ

### 1. Проверить таблицы в PostgreSQL:
```bash
docker-compose exec postgres psql -U timesheet -d timesheet_db -c "\dt"
```

Должны быть таблицы:
- work_sessions
- status_transitions
- activity_sessions
- activity_events
- activity_categories
- widget_settings
- alembic_version

### 2. Проверить структуру таблицы:
```bash
docker-compose exec postgres psql -U timesheet -d timesheet_db -c "\d work_sessions"
```

### 3. Проверить данные:
```bash
docker-compose exec postgres psql -U timesheet -d timesheet_db -c "SELECT * FROM alembic_version;"
```

---

## 🔄 ОБНОВЛЕНИЕ МОДЕЛЕЙ

Если вы изменили модели:

```bash
# 1. Создать новую миграцию
alembic revision --autogenerate -m "Update models"

# 2. Проверить сгенерированный файл
# migrations/versions/xxxxx_update_models.py

# 3. Если всё ок, применить
alembic upgrade head

# 4. Если нужно откатить
alembic downgrade -1
```

---

## ⚠️ ВАЖНО

### Перед применением миграций:
1. ✅ Сделайте backup БД (в production)
2. ✅ Проверьте сгенерированную миграцию
3. ✅ Протестируйте на dev окружении
4. ✅ Убедитесь что PostgreSQL запущен

### При ошибках:
```bash
# Если миграция не удалась
alembic downgrade -1

# Если нужно сбросить всё
docker-compose down -v  # Удалит все данные!
docker-compose up -d
alembic upgrade head
```

---

## 📖 ПРИМЕРЫ МИГРАЦИЙ

### Добавить колонку:
```python
def upgrade():
    op.add_column('work_sessions', 
        sa.Column('new_column', sa.String(255), nullable=True))

def downgrade():
    op.drop_column('work_sessions', 'new_column')
```

### Создать индекс:
```python
def upgrade():
    op.create_index('idx_custom', 'work_sessions', ['user_id', 'status'])

def downgrade():
    op.drop_index('idx_custom')
```

### Изменить тип колонки:
```python
def upgrade():
    op.alter_column('work_sessions', 'user_id',
        type_=sa.BigInteger(),
        existing_type=sa.Integer())

def downgrade():
    op.alter_column('work_sessions', 'user_id',
        type_=sa.Integer(),
        existing_type=sa.BigInteger())
```

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Запустить PostgreSQL:**
   ```bash
   docker-compose up -d postgres
   ```

2. **Создать миграцию:**
   ```bash
   cd backend
   alembic revision --autogenerate -m "Initial migration"
   ```

3. **Применить:**
   ```bash
   alembic upgrade head
   ```

4. **Проверить:**
   ```bash
   alembic current
   docker-compose exec postgres psql -U timesheet -d timesheet_db -c "\dt"
   ```

5. **Запустить API:**
   ```bash
   docker-compose up -d
   # Открыть http://localhost:8000/docs
   ```

---

**Статус:** ✅ Alembic настроен  
**Дата:** 10.07.2026  
**Готово к использованию:** Да

🚀 Теперь можно создавать и применять миграции!
