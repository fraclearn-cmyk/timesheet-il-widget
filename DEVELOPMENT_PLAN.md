# 🚀 ПЛАН РАЗРАБОТКИ: Виджет "Табель IL"

**Версия:** Full (с автоматическим трекингом)  
**Срок:** 9-12 дней  
**Старт:** 09.07.2026

---

## ✅ ВЫПОЛНЕНО

- [x] Техническая спецификация (MVP)
- [x] Дополнение: Activity Tracking
- [x] Утверждение полной версии (Full)
- [x] Создание структуры проекта
- [x] README.md

---

## 📋 ЭТАПЫ РАЗРАБОТКИ

### **ЭТАП 1: Backend Foundation** (2 дня)

#### День 1: Настройка проекта и БД
- [ ] `docker-compose.yml` + `Dockerfile`
- [ ] `.env.example`
- [ ] `requirements.txt` + `requirements-dev.txt`
- [ ] `backend/app/core/config.py` (настройки)
- [ ] `backend/app/core/database.py` (подключение к БД)
- [ ] `backend/app/core/security.py` (JWT auth)
- [ ] `alembic.ini` + миграции setup

#### День 2: Models & Schemas
- [ ] `backend/app/models/__init__.py`
- [ ] `backend/app/models/work_session.py`
- [ ] `backend/app/models/status_transition.py`
- [ ] `backend/app/models/activity_session.py`
- [ ] `backend/app/models/activity_event.py`
- [ ] `backend/app/models/activity_category.py`
- [ ] `backend/app/models/widget_settings.py`
- [ ] Создать миграции Alembic
- [ ] Pydantic schemas для всех моделей

---

### **ЭТАП 2: Базовый функционал** (2 дня)

#### День 3: Timesheet API
- [ ] `backend/app/services/timesheet_service.py`
  - `start_work()`
  - `start_break()`
  - `end_break()`
  - `finish_work()`
  - `get_current_status()`
  - `change_status()` (core logic)
  
- [ ] `backend/app/api/v1/timesheet.py`
  - POST `/start-work`
  - POST `/start-break`
  - POST `/end-break`
  - POST `/finish-work`
  - GET `/my-status`
  - GET `/my-today`

#### День 4: Мониторинг команды
- [ ] `backend/app/services/team_service.py`
  - `get_team_status()` (с фильтрацией по правам)
  - `get_team_history()`
  
- [ ] `backend/app/api/v1/timesheet.py` (дополнить)
  - GET `/team-status`
  - GET `/team-history`
  
- [ ] Интеграция с amoCRM API (роли/подразделения)
- [ ] `backend/app/integrations/amocrm.py`

---

### **ЭТАП 3: Activity Tracking** (3 дня)

#### День 5: Activity Service
- [ ] `backend/app/services/activity_service.py`
  - `start_activity_session()`
  - `stop_activity_session()`
  - `pause_session()`
  - `resume_session()`
  - `log_event()`
  - `calculate_activity_score()`

- [ ] `backend/app/api/v1/activity.py`
  - POST `/start`
  - POST `/stop`
  - POST `/pause`
  - POST `/resume`
  - POST `/event`
  - GET `/history`

#### День 6: Frontend Activity Tracker
- [ ] `frontend/widget/activity-tracker.js`
  - ActivityTracker class
  - Отслеживание открытия/закрытия карточек
  - Мониторинг активности (мышь, клавиатура)
  - Авто-пауза при неактивности
  - Batch-отправка событий

- [ ] Интеграция с amoCRM Widget SDK
- [ ] Event listeners (card:opened, card:closed, call:started)

#### День 7: События amoCRM
- [ ] Webhook endpoints для событий
- [ ] Обработка звонков (call_started, call_ended)
- [ ] Обработка задач, notes, emails
- [ ] Маппинг событий на категории

---

### **ЭТАП 4: Frontend Widget** (2 дня)

#### День 8: Основной виджет
- [ ] `frontend/widget/manifest.json`
- [ ] `frontend/widget/script.js`
  - Кнопка управления статусом
  - Отображение текущего статуса
  - Таймер текущей сессии
  - Переключение статусов
  
- [ ] `frontend/widget/styles.css`
  - Дизайн кнопки
  - Цветовая индикация
  - Адаптивность

- [ ] Overlay-блокировка
  - `overlay.js`
  - Fullscreen overlay (z-index: 9999)
  - Polling статуса каждые 15 сек
  - Кнопка возобновления

#### День 9: Dashboard для РОП
- [ ] `frontend/monitoring/dashboard.html`
- [ ] `frontend/monitoring/dashboard.js`
  - Таблица сотрудников
  - Real-time обновление
  - Цветовая индикация
  - Hover tooltip с историей
  - Детальный отчёт по клику

- [ ] `frontend/monitoring/styles.css`
  - Таблица с сортировкой
  - Графики активности (Chart.js)
  - Адаптивный дизайн

---

### **ЭТАП 5: Отчёты и Excel** (2 дня)

#### День 10: Отчёты
- [ ] `backend/app/services/report_service.py`
  - `get_detailed_report()` (фильтры)
  - `get_user_activity_breakdown()`
  - `get_activity_by_categories()`
  - `get_statistics()`

- [ ] `backend/app/api/v1/reports.py`
  - GET `/detailed-report`
  - GET `/activity-breakdown`
  - GET `/statistics`

#### День 11: Excel Export
- [ ] `backend/app/services/excel_service.py`
  - `generate_timesheet_report()`
  - `generate_activity_report()`
  - Настраиваемые колонки
  - Условное форматирование
  - Два листа (сводка + детализация)

- [ ] `backend/app/api/v1/reports.py` (дополнить)
  - POST `/export-excel`
  - GET `/settings`
  - PUT `/settings`

- [ ] Frontend: настройки экспорта
  - Чекбоксы выбора колонок
  - Выбор периода
  - Кнопка "Экспорт"

---

### **ЭТАП 6: Тестирование и доработка** (1 день)

#### День 12: Testing & Bug Fixes
- [ ] Unit tests (pytest)
  - test_timesheet.py
  - test_activity.py
  - test_reports.py
  
- [ ] Integration tests
  - API endpoints
  - Database operations
  - amoCRM integration

- [ ] Frontend testing
  - Manual testing
  - Browser compatibility
  - Overlay blocking

- [ ] Bug fixes
- [ ] Performance optimization
- [ ] Documentation updates

---

## 📦 ДОПОЛНИТЕЛЬНЫЕ ФАЙЛЫ (создать параллельно)

### Backend
- [ ] `backend/app/__init__.py`
- [ ] `backend/app/main.py` (FastAPI app)
- [ ] `backend/app/api/__init__.py`
- [ ] `backend/app/api/v1/__init__.py`
- [ ] `backend/app/schemas/__init__.py`
- [ ] `backend/app/services/__init__.py`
- [ ] `backend/app/integrations/__init__.py`
- [ ] `backend/Dockerfile`
- [ ] `backend/.dockerignore`
- [ ] `backend/alembic.ini`
- [ ] `backend/migrations/env.py`
- [ ] `backend/migrations/script.py.mako`

### Root
- [ ] `docker-compose.yml`
- [ ] `.env.example`
- [ ] `.gitignore`
- [ ] `Makefile` (опционально)

### Docs
- [ ] `docs/DEPLOYMENT.md`
- [ ] `docs/API.md`
- [ ] `docs/CONFIGURATION.md`

---

## 🔧 ТЕХНОЛОГИИ И ЗАВИСИМОСТИ

### Backend (requirements.txt)
```
fastapi==0.110.0
uvicorn[standard]==0.27.1
sqlalchemy==2.0.27
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic==2.6.1
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
openpyxl==3.1.2
httpx==0.26.0
python-dotenv==1.0.1
```

### Backend Dev (requirements-dev.txt)
```
pytest==8.0.0
pytest-cov==4.1.0
pytest-asyncio==0.23.3
black==24.1.1
flake8==7.0.0
mypy==1.8.0
```

### Frontend
- amoCRM Widget SDK
- Chart.js (для графиков)
- Vanilla JavaScript (ES6+)

---

## 🎯 КРИТЕРИИ ГОТОВНОСТИ

### MVP (базовый функционал)
- ✅ Управление статусами работает
- ✅ Overlay блокирует интерфейс
- ✅ Мониторинг команды отображается
- ✅ Права доступа работают
- ✅ Базовый Excel-экспорт

### Full (полный функционал)
- ✅ Activity tracker отслеживает карточки
- ✅ События amoCRM логируются
- ✅ Детальные отчёты доступны
- ✅ Цветовая категоризация работает
- ✅ История при наведении отображается
- ✅ Excel с детализацией экспортируется

---

## 📊 МЕТРИКИ УСПЕХА

1. **Функциональность:** 100% функций из спецификации
2. **Производительность:** API < 200ms response time
3. **Надёжность:** 0 critical bugs
4. **Тестирование:** >80% code coverage
5. **Документация:** Полная документация API

---

## 🚀 СЛЕДУЮЩИЙ ШАГ

**Начать с создания конфигурационных файлов:**
1. `docker-compose.yml`
2. `.env.example`
3. `requirements.txt`
4. `backend/Dockerfile`

Затем перейти к моделям БД и миграциям.

---

**Статус:** 🟢 Ready to Start  
**Дата начала:** 09.07.2026  
**Планируемое завершение:** 21.07.2026
