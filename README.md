it # 📊 Виджет "Табель IL" для amoCRM

**Версия:** 1.0.0  
**Тип:** Standalone amoCRM Widget с автоматическим трекингом активности

---

## 🎯 Описание

Виджет учёта рабочего времени с автоматическим трекингом активности сотрудников в amoCRM.

### Ключевые возможности

✅ **Управление статусами** (Работаю/Перерыв/Завершил)  
✅ **Overlay-блокировка интерфейса** при статусе "Не работаю"  
✅ **Автоматический трекинг активности** (карточки, звонки, события)  
✅ **Мониторинг команды в реальном времени**  
✅ **Детальная аналитика по событиям** с цветовой категоризацией  
✅ **Гибкий Excel-экспорт** (настраиваемые колонки)  
✅ **Права доступа** (Менеджер/РОП/Администратор)

---

## 📋 Технологический стек

### Backend
- Python 3.11+
- FastAPI
- PostgreSQL 15
- SQLAlchemy + Alembic
- openpyxl (Excel)

### Frontend
- HTML5/CSS3/JavaScript
- amoCRM Widget SDK
- ActivityTracker (custom)

### Infrastructure
- Docker + Docker Compose
- Nginx
- SSL/TLS

---

## 📁 Структура проекта

```
timesheet-il-widget/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API endpoints
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── integrations/    # amoCRM API
│   │   └── core/            # Config, DB, security
│   ├── migrations/          # Alembic migrations
│   ├── tests/               # Tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── widget/              # amoCRM widget files
│   │   ├── script.js
│   │   ├── styles.css
│   │   └── manifest.json
│   ├── monitoring/          # Dashboard для РОП
│   └── assets/              # Images, icons
├── docs/                    # Documentation
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Быстрый старт

### 1. Клонировать репозиторий
```bash
git clone <repo-url>
cd timesheet-il-widget
```

### 2. Настроить окружение
```bash
cp .env.example .env
# Отредактировать .env (добавить БД, amoCRM ключи)
```

### 3. Запустить через Docker
```bash
docker-compose up -d
```

### 4. Применить миграции
```bash
docker-compose exec backend alembic upgrade head
```

### 5. Открыть
```
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs
Widget: установить через amoCRM marketplace
```

---

## 📊 Основной функционал

### 1. Автоматический трекинг активности

Виджет отслеживает:
- ⏱️ Время работы с карточками (сделки/контакты/компании)
- 📞 События: звонки, задачи, notes, emails
- 🖱️ Активность пользователя (мышь, клавиатура)
- ⏸️ Автопауза при неактивности >5 минут

### 2. Управление статусами

**Три статуса:**
- 🟢 Работаю (доступ открыт)
- 🟡 Перерыв (интерфейс заблокирован)
- 🔴 Завершил (рабочий день окончен)

**Блокировка:**
- Полупрозрачный overlay поверх amoCRM
- Блокирует все взаимодействие
- Доступна только кнопка возобновления

### 3. Мониторинг команды

**Real-time обновление:**
- Polling каждые 15 секунд
- Кнопка "Обновить" для ручного обновления
- Цветовая индикация статусов
- Время в текущем статусе

**Права доступа:**
- Менеджер → видит только себя
- РОП → видит своё подразделение
- Администратор → видит всех

### 4. Детальная аналитика

**Отчёты включают:**
- Сводка по сотрудникам
- Детализация по карточкам
- События с временными метками
- Группировка по типам активности
- Цветовая категоризация

**Цвета событий:**
- 🟢 Сделки (зелёный)
- 🟡 Контакты (жёлтый)
- 🔵 Компании (синий)
- 📞 Звонки (красный)
- 📝 Задачи (фиолетовый)
- 💬 Переписка (оранжевый)
- ⏸️ Перерывы (серый)

### 5. Excel-экспорт

**Настраиваемые колонки:**
- ФИО сотрудника
- Дата работы
- Время начала/окончания
- Всего часов работы
- Время перерывов
- Количество перерывов
- Детальная история переходов
- Подразделение
- Переработки
- События по карточкам

**Период:** до 3 месяцев

---

## 🗄️ База данных

### Таблицы

1. **work_sessions** - рабочие сессии сотрудников
2. **status_transitions** - история переходов статусов
3. **activity_sessions** - сессии работы с карточками
4. **activity_events** - события amoCRM
5. **activity_categories** - настройки цветов категорий
6. **widget_settings** - настройки виджета

---

## 🔗 API Endpoints

### Для сотрудников
```
POST /api/v1/timesheet/start-work     # Начать работу
POST /api/v1/timesheet/start-break    # Уйти на перерыв
POST /api/v1/timesheet/end-break      # Вернуться с перерыва
POST /api/v1/timesheet/finish-work    # Завершить день
GET  /api/v1/timesheet/my-status      # Мой статус
GET  /api/v1/timesheet/my-today       # Моя сегодняшняя сессия
```

### Для менеджеров/РОП
```
GET /api/v1/timesheet/team-status    # Статусы команды
GET /api/v1/timesheet/team-history   # История команды
```

### Для РОП/Администраторов
```
GET  /api/v1/timesheet/detailed-report # Детальный отчёт
POST /api/v1/timesheet/export-excel    # Экспорт в Excel
GET  /api/v1/timesheet/settings        # Настройки
PUT  /api/v1/timesheet/settings        # Обновить настройки
```

### Activity Tracking
```
POST /api/v1/activity/start      # Старт сессии
POST /api/v1/activity/stop       # Стоп сессии
POST /api/v1/activity/pause      # Пауза
POST /api/v1/activity/resume     # Возобновление
POST /api/v1/activity/event      # Логировать событие
GET  /api/v1/activity/history    # История активности
```

---

## ⚙️ Настройка

### Переменные окружения (.env)

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/timesheet_db

# amoCRM
AMOCRM_CLIENT_ID=your_client_id
AMOCRM_CLIENT_SECRET=your_client_secret
AMOCRM_REDIRECT_URI=https://your-domain.com/oauth/callback

# Backend
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Settings
POLLING_INTERVAL=15
INACTIVITY_TIMEOUT=300
```

### Настройки виджета (в админке)

- Интервал polling (по умолчанию 15 сек)
- Таймаут неактивности (по умолчанию 5 мин)
- Выбор колонок для Excel-экспорта
- Цвета категорий событий
- Автоматическое завершение дня (опционально)

---

## 🧪 Тестирование

```bash
# Запустить тесты
docker-compose exec backend pytest

# С покрытием
docker-compose exec backend pytest --cov=app

# Конкретный модуль
docker-compose exec backend pytest tests/test_timesheet.py
```

---

## 📖 Документация

- [Техническая спецификация](../TIMESHEET_IL_SPECIFICATION.md)
- [Activity Tracking](../TIMESHEET_ACTIVITY_TRACKING_ADDON.md)
- [API Documentation](http://localhost:8000/docs)
- [Руководство по развёртыванию](docs/DEPLOYMENT.md)

---

## ⏱️ Оценка разработки

**Этап 1 (MVP):** 4-5 дней
- Базовый функционал
- Управление статусами
- Блокировка интерфейса
- Простой мониторинг

**Этап 2 (Full):** +5-7 дней
- Автоматический трекинг
- События amoCRM
- Детальные отчёты
- Графики

**Итого:** 9-12 дней полная реализация

---

## 🐛 Известные ограничения

1. amoCRM Events API не предоставляет длительность действий
2. Трекинг активности работает только при открытом браузере
3. Offline режим не поддерживается

---

## 📝 Лицензия

Proprietary - Все права защищены

---

## 👥 Контакты

**Разработчик:** [Ваше имя]  
**Email:** support@example.com  
**Дата создания:** 09.07.2026

---

**Статус:** 🚀 Ready for Development
