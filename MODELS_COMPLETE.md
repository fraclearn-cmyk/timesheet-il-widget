# ✅ МОДЕЛИ БД СОЗДАНЫ

**Дата:** 09.07.2026  
**Статус:** Модели готовы (100%)  
**Следующее:** Настройка Alembic + миграции

---

## 🎉 СОЗДАНО 6 МОДЕЛЕЙ SQLAlchemy

### 1. WorkSession (work_sessions)
**Основная таблица рабочих сессий**

```python
- id: Integer (PK)
- user_id: Integer (amoCRM user ID) 
- user_name: String(255)
- department: String(255)
- start_time: DateTime
- end_time: DateTime
- current_status: Enum(working/break/finished)
- total_work_time: Integer (seconds)
- total_break_time: Integer (seconds)
- break_count: Integer
- created_at, updated_at: DateTime
```

**Relationships:**
- → status_transitions (1:M)
- → activity_sessions (1:M)

---

### 2. StatusTransition (status_transitions)
**История переходов статусов**

```python
- id: Integer (PK)
- work_session_id: Integer (FK → work_sessions)
- from_status: String(50) (nullable)
- to_status: String(50)
- timestamp: DateTime
- duration: Integer (seconds)
- reason: String(255)
- notes: String(1000)
```

**Relationships:**
- ← work_session (M:1)

---

### 3. ActivitySession (activity_sessions)
**Сессии работы с карточками**

```python
- id: Integer (PK)
- work_session_id: Integer (FK → work_sessions)
- entity_type: Enum(lead/contact/company/task)
- entity_id: Integer
- entity_name: String(500)
- start_time: DateTime
- end_time: DateTime
- duration: Integer (seconds)
- is_active: Integer (1/0)
- last_activity_time: DateTime
- created_at, updated_at: DateTime
```

**Relationships:**
- ← work_session (M:1)
- → activity_events (1:M)

---

### 4. ActivityEvent (activity_events)
**События amoCRM**

```python
- id: Integer (PK)
- activity_session_id: Integer (FK → activity_sessions)
- event_type: Enum(call_incoming, call_outgoing, task_created, ...)
- event_data: JSON
- timestamp: DateTime
- description: String(1000)
- category_id: Integer (FK → activity_categories)
- created_at: DateTime
```

**Event Types (11 типов):**
- call_incoming, call_outgoing
- task_created, task_completed
- note_added
- email_sent, email_received
- card_opened, card_closed, card_updated
- status_changed

**Relationships:**
- ← activity_session (M:1)
- ← category (M:1)

---

### 5. ActivityCategory (activity_categories)
**Категории событий с цветами**

```python
- id: Integer (PK)
- name: String(100) (unique)
- display_name: String(200)
- color: String(50) (hex or CSS color)
- icon: String(50)
- description: String(500)
- is_active: Boolean
- sort_order: Integer
```

**Примеры категорий:**
- leads (Сделки) → зелёный 🟢
- contacts (Контакты) → жёлтый 🟡
- companies (Компании) → синий 🔵
- calls (Звонки) → красный 📞
- tasks (Задачи) → фиолетовый 📝
- messages (Переписка) → оранжевый 💬
- breaks (Перерывы) → серый ⏸️

**Relationships:**
- → events (1:M)

---

### 6. WidgetSettings (widget_settings)
**Настройки виджета**

```python
- id: Integer (PK)
- account_id: Integer (unique, amoCRM account)
- account_name: String(255)
- polling_interval: Integer (default 15)
- inactivity_timeout: Integer (default 300)
- enable_activity_tracking: Boolean (default True)
- enable_overlay_blocking: Boolean (default True)
- enable_auto_finish: Boolean (default False)
- excel_columns: JSON
- settings: JSON
- created_at, updated_at: DateTime
```

---

## 📊 СТРУКТУРА БД

```
work_sessions (main table)
├── status_transitions (history)
└── activity_sessions (card work)
    └── activity_events (amoCRM events)
        └── activity_categories (colors)

widget_settings (independent)
```

**Связи:**
- 1 Work Session → N Status Transitions
- 1 Work Session → N Activity Sessions
- 1 Activity Session → N Activity Events
- 1 Activity Category → N Activity Events
- Account → 1 Widget Settings

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ: Alembic Migrations

### Шаг 1: Настроить Alembic

```bash
cd timesheet-il-widget/backend
docker-compose up -d  # Запустить БД
```

### Шаг 2: Инициализировать Alembic (ВНУТРИ КОНТЕЙНЕРА)

```bash
# Войти в контейнер
docker-compose exec backend bash

# Инициализировать Alembic
alembic init migrations

# ИЛИ если нужно переинициализировать
rm -rf migrations
alembic init migrations
```

### Шаг 3: Настроить alembic.ini

Отредактировать `backend/alembic.ini`:

```ini
# НАЙТИ строку:
sqlalchemy.url = driver://user:pass@localhost/dbname

# ЗАМЕНИТЬ НА:
# sqlalchemy.url = (удалить эту строку, будем использовать env.py)
```

### Шаг 4: Настроить migrations/env.py

Отредактировать `backend/migrations/env.py`:

```python
# В начале файла добавить:
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parents[1]))

from app.core.config import settings
from app.core.database import Base
from app.models import *  # Импортировать все модели

# В функции run_migrations_offline() заменить:
config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)

# В функции run_migrations_online() заменить:
connectable = create_engine(settings.DATABASE_URL)
```

### Шаг 5: Создать первую миграцию

```bash
# Создать автоматическую миграцию
alembic revision --autogenerate -m "Initial tables: work_sessions, activity tracking"

# Проверить созданную миграцию
ls -la migrations/versions/
```

### Шаг 6: Применить миграции

```bash
# Применить все миграции
alembic upgrade head

# Проверить статус
alembic current

# Показать историю
alembic history
```

### Шаг 7: Проверить таблицы в БД

```bash
# Подключиться к PostgreSQL
docker-compose exec db psql -U postgres -d timesheet_db

# Показать таблицы
\dt

# Должны быть:
# - alembic_version
# - work_sessions
# - status_transitions
# - activity_sessions
# - activity_events
# - activity_categories
# - widget_settings

# Выйти
\q
```

---

## 📝 ПОЛЕЗНЫЕ КОМАНДЫ ALEMBIC

```bash
# Создать новую миграцию (автогенерация)
alembic revision --autogenerate -m "Description"

# Создать пустую миграцию
alembic revision -m "Description"

# Применить все миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Откатить все миграции
alembic downgrade base

# Показать текущую версию
alembic current

# Показать историю
alembic history --verbose

# Проверить SQL без применения
alembic upgrade head --sql
```

---

## 🔧 ЕСЛИ ВОЗНИКЛИ ПРОБЛЕМЫ

### Проблема 1: "Can't locate revision..."
```bash
# Удалить migrations и начать заново
rm -rf migrations
alembic init migrations
# Настроить env.py снова
```

### Проблема 2: "Target database is not up to date"
```bash
# Пометить БД как актуальную
alembic stamp head
```

### Проблема 3: "Table already exists"
```bash
# Откатить все
alembic downgrade base
# Удалить таблицы вручную
# Применить снова
alembic upgrade head
```

### Проблема 4: Модели не импортируются
```bash
# Убедитесь что __init__.py экспортирует модели:
# backend/app/models/__init__.py должен содержать все импорты
```

---

## ✅ ЧЕКЛИСТ ДЕНЬ 2 (50% выполнено)

- [x] Создана модель WorkSession
- [x] Создана модель StatusTransition
- [x] Создана модель ActivitySession
- [x] Создана модель ActivityEvent
- [x] Создана модель ActivityCategory
- [x] Создана модель WidgetSettings
- [x] Создан __init__.py с экспортами
- [ ] Настроить Alembic
- [ ] Создать миграции
- [ ] Применить миграции
- [ ] Создать Pydantic schemas
- [ ] Протестировать БД

---

## 📊 ПРОГРЕСС

**Общий:** 12% (День 1.5 из 12)
**День 2:** 50% выполнено

**Файлов создано сегодня:** 7
- 6 моделей SQLAlchemy
- 1 __init__.py

**Строк кода:** ~400 (модели)

---

## 🔥 СЛЕДУЮЩИЙ ШАГ

1. **Настроить Alembic** (30 минут)
2. **Создать миграции** (15 минут)
3. **Применить миграции** (5 минут)
4. **Создать Pydantic schemas** (1-2 часа)

**Команды для старта:**
```bash
cd timesheet-il-widget
docker-compose up -d
docker-compose exec backend bash
alembic init migrations
# Настроить env.py
alembic revision --autogenerate -m "Initial"
alembic upgrade head
```

---

**Статус:** 🟢 Модели готовы!  
**Следующее:** Alembic + Migrations  
**Время:** ~1 час работы
