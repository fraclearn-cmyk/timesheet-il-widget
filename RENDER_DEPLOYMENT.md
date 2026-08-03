# 🚀 РАЗВЁРТЫВАНИЕ НА RENDER.COM

**Цель:** Быстро развернуть backend на Render.com и подключить виджет к amoCRM

---

## 🎯 ПОЧЕМУ RENDER?

✅ **Бесплатный план** - для тестирования  
✅ **Автоматический HTTPS** - SSL из коробки  
✅ **Интеграция с GitHub** - автодеплой при push  
✅ **PostgreSQL в комплекте** - управляемая база данных  
✅ **Простая настройка** - без сервера и Docker  
✅ **Быстрый старт** - 10-15 минут до готового API  

---

## 📋 ЧТО ПОНАДОБИТСЯ

- [ ] Аккаунт на GitHub (код должен быть в репозитории)
- [ ] Аккаунт на Render.com (регистрация бесплатная)
- [ ] Доступ к amoCRM (права администратора)

**Время развёртывания:** 15-20 минут  
**Стоимость:** $0 (бесплатный план)

---

## ⚡ БЫСТРЫЙ СТАРТ (10 ШАГОВ)

### ШАГ 1: Загрузите код в GitHub

Если ещё не сделали:
```powershell
cd d:\табель
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/timesheet-il-widget.git
git push -u origin main
```

Подробнее: см. `GITHUB_QUICKSTART.md`

---

### ШАГ 2: Зарегистрируйтесь на Render

1. Перейдите: https://render.com/
2. Нажмите **"Get Started"**
3. Выберите **"Sign up with GitHub"**
4. Авторизуйте Render для доступа к вашим репозиториям

---

### ШАГ 3: Создайте PostgreSQL базу данных

1. В dashboard Render нажмите **"New +"**
2. Выберите **"PostgreSQL"**
3. Заполните форму:
   ```
   Name: timesheet-db
   Database: timesheet_db
   User: postgres (по умолчанию)
   Region: Frankfurt (ближе к России)
   Plan: Free
   ```
4. Нажмите **"Create Database"**
5. **ВАЖНО:** Скопируйте **Internal Database URL** - понадобится для backend

**Формат URL:**
```
postgresql://username:password@hostname:5432/database
```

---

### ШАГ 4: Создайте Web Service для Backend

1. В dashboard нажмите **"New +"**
2. Выберите **"Web Service"**
3. Подключите ваш GitHub репозиторий `timesheet-il-widget`
4. Заполните форму:
   ```
   Name: timesheet-backend
   Region: Frankfurt
   Branch: main
   Root Directory: backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   Plan: Free
   ```

---

### ШАГ 5: Настройте переменные окружения

В настройках вашего Web Service добавьте Environment Variables:

```bash
# Database (вставьте Internal Database URL из шага 3)
DATABASE_URL=postgresql://user:pass@hostname:5432/timesheet_db

# API Settings
API_HOST=0.0.0.0
PORT=10000
DEBUG=False

# CORS - ВАЖНО! Замените на ваш Render URL после создания
CORS_ORIGINS=["https://timesheet-backend.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]

# Security - сгенерируйте случайный ключ
SECRET_KEY=ваш_случайный_секретный_ключ_64_символа_минимум

# PostgreSQL Connection Pool (для бесплатного плана)
POSTGRES_MAX_CONNECTIONS=20
```

**Генерация SECRET_KEY:**
```powershell
# На вашем компьютере
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### ШАГ 6: Создайте render.yaml (опционально, но рекомендуется)

Создайте файл `render.yaml` в корне проекта:

```yaml
services:
  - type: web
    name: timesheet-backend
    env: python
    region: frankfurt
    plan: free
    buildCommand: "cd backend && pip install -r requirements.txt"
    startCommand: "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: API_HOST
        value: 0.0.0.0
      - key: DEBUG
        value: False
      - key: CORS_ORIGINS
        value: '["https://timesheet-backend.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]'
      - key: DATABASE_URL
        fromDatabase:
          name: timesheet-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true

databases:
  - name: timesheet-db
    databaseName: timesheet_db
    plan: free
    region: frankfurt
```

Загрузите в GitHub:
```powershell
git add render.yaml
git commit -m "Add Render configuration"
git push
```

---

### ШАГ 7: Дождитесь развёртывания

1. Render автоматически начнёт деплой
2. Процесс займёт 2-5 минут
3. Следите за логами в реальном времени
4. Статус изменится на **"Live"**

**Ваш URL будет вида:**
```
https://timesheet-backend.onrender.com
```

---

### ШАГ 8: Примените миграции базы данных

После успешного деплоя нужно применить миграции Alembic.

**Вариант А: Через Render Shell (рекомендуется)**

1. В dashboard вашего Web Service нажмите **"Shell"**
2. В открывшейся консоли выполните:
   ```bash
   cd backend
   alembic upgrade head
   ```

**Вариант Б: Через локальное подключение**

На вашем компьютере:
```powershell
# Установите переменную окружения с URL БД (External Database URL из Render)
$env:DATABASE_URL="postgresql://user:pass@hostname:5432/timesheet_db"

# Примените миграции
cd backend
alembic upgrade head
```

---

### ШАГ 9: Проверьте работу backend

Откройте в браузере:
- `https://timesheet-backend.onrender.com/health`
  - Должно вернуть: `{"status":"healthy"}`
- `https://timesheet-backend.onrender.com/docs`
  - Должна открыться документация Swagger UI

**Если работает** - backend готов! ✅

---

### ШАГ 10: Пересоберите виджет с Render URL

На вашем компьютере:

```powershell
cd d:\табель

# Пересобрать виджет с вашим Render URL
.\build_widget.ps1 -ApiUrl "https://timesheet-backend.onrender.com/api/v1" -SupportEmail "support@your-company.com"
```

Должен создаться файл: `timesheet_il_widget.zip`

---

## 📤 ЗАГРУЗКА ВИДЖЕТА В amoCRM

### 1. Откройте amoCRM

1. Войдите в ваш аккаунт amoCRM
2. Нажмите **⚙️ (Настройки)** в правом верхнем углу
3. Перейдите: **Настройки → Интеграции → Виджеты**

### 2. Загрузите виджет

1. Нажмите **"Загрузить свой виджет"**
2. Выберите файл: `timesheet_il_widget.zip`
3. Нажмите **"Загрузить"**
4. Дождитесь проверки (~10-30 секунд)

### 3. Настройте виджет

1. **Включите виджет** - переведите тумблер в положение "Вкл"
2. **Выберите разделы** где показывать:
   - ✅ Карточка лида
   - ✅ Карточка контакта
   - ✅ Карточка компании
   - ✅ Карточка сделки
3. Нажмите **"Сохранить"**

### 4. Тестирование

1. Откройте любую карточку в amoCRM
2. Найдите виджет **"⏱️ Рабочее время"** на правой панели
3. Нажмите **"▶️ Начать рабочий день"**
4. Проверьте:
   - ✅ Таймер работает
   - ✅ Кнопки реагируют
   - ✅ Нет ошибок в консоли (F12)

**Если всё работает** - поздравляю! Виджет развёрнут! 🎉

---

## 🔄 АВТОМАТИЧЕСКИЙ ДЕПЛОЙ

При использовании GitHub интеграции, Render автоматически:
- ✅ Отслеживает изменения в main ветке
- ✅ Автоматически деплоит при `git push`
- ✅ Уведомляет о статусе деплоя

**Workflow:**
```powershell
# 1. Внесите изменения в код
# 2. Закоммитьте
git add .
git commit -m "Update: улучшения виджета"

# 3. Загрузите в GitHub
git push

# 4. Render автоматически задеплоит изменения (2-5 минут)
# 5. Проверьте обновления в amoCRM
```

---

## 📊 ОСОБЕННОСТИ БЕСПЛАТНОГО ПЛАНА RENDER

### ✅ Что включено:
- 750 часов работы в месяц (для одного сервиса - достаточно)
- Автоматический HTTPS
- Автодеплой из GitHub
- PostgreSQL база данных (1 GB)
- 512 MB RAM
- Shared CPU

### ⚠️ Ограничения:
- **Sleep mode** - сервис засыпает после 15 минут неактивности
- **Cold start** - первый запрос после сна занимает 30-60 секунд
- **Shared ресурсы** - может быть медленнее в пиковые часы

### 💡 Решение проблемы sleep mode:

Если нужна постоянная работа без "засыпания":
- Апгрейд на платный план ($7/месяц) - сервис работает 24/7
- Или используйте cron для пинга каждые 10 минут (костыль, но работает)

---

## 🔧 НАСТРОЙКА RENDER.YAML (ПРОДВИНУТАЯ КОНФИГУРАЦИЯ)

Создайте `render.yaml` в корне проекта для Infrastructure as Code:

```yaml
services:
  # Backend Web Service
  - type: web
    name: timesheet-backend
    env: python
    region: frankfurt
    plan: free
    branch: main
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: API_HOST
        value: 0.0.0.0
      - key: DEBUG
        value: False
      - key: CORS_ORIGINS
        value: '["https://timesheet-backend.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]'
      - key: DATABASE_URL
        fromDatabase:
          name: timesheet-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: PYTHON_VERSION
        value: "3.11"

databases:
  # PostgreSQL Database
  - name: timesheet-db
    databaseName: timesheet_db
    user: postgres
    plan: free
    region: frankfurt
```

---

## 🛠️ УПРАВЛЕНИЕ ЧЕРЕЗ RENDER DASHBOARD

### Логи

1. Откройте ваш Web Service
2. Перейдите в **"Logs"**
3. Смотрите логи в реальном времени
4. Фильтруйте по типу (Build, Deploy, Application)

### Shell доступ

1. Откройте ваш Web Service
2. Нажмите **"Shell"** в верхнем меню
3. Получите доступ к bash консоли
4. Можете выполнять команды:
   ```bash
   # Применить миграции
   cd backend && alembic upgrade head
   
   # Проверить переменные окружения
   env | grep DATABASE
   
   # Проверить структуру
   ls -la
   ```

### Переменные окружения

1. Откройте Web Service
2. Перейдите в **"Environment"**
3. Добавьте/измените переменные
4. Нажмите **"Save Changes"**
5. Сервис автоматически перезапустится

### Метрики

1. Откройте Web Service
2. Перейдите в **"Metrics"**
3. Смотрите:
   - CPU usage
   - Memory usage
   - Request count
   - Response time

---

## 🗄️ РАБОТА С БАЗОЙ ДАННЫХ

### Подключение к БД

**Получите credentials:**
1. Откройте вашу PostgreSQL базу в Render
2. Скопируйте **"External Database URL"**

**Подключитесь локально:**
```bash
# Через psql
psql "postgresql://user:pass@hostname:5432/timesheet_db"

# Или через pgAdmin, DBeaver, DataGrip
Host: hostname-from-render
Port: 5432
Database: timesheet_db
Username: user-from-render
Password: password-from-render
SSL Mode: Require
```

### Резервное копирование

```bash
# Создать backup
pg_dump "postgresql://user:pass@hostname:5432/timesheet_db" > backup.sql

# Восстановить из backup
psql "postgresql://user:pass@hostname:5432/timesheet_db" < backup.sql
```

---

## 🔍 МОНИТОРИНГ И ОТЛАДКА

### Проверка здоровья

```bash
# Health check
curl https://timesheet-backend.onrender.com/health

# API docs
curl https://timesheet-backend.onrender.com/docs
```

### Просмотр логов

1. Dashboard → Ваш сервис → **Logs**
2. Или через CLI:
   ```bash
   # Установить Render CLI
   npm install -g render-cli
   
   # Логин
   render login
   
   # Просмотр логов
   render logs timesheet-backend
   ```

### Отладка CORS

Если виджет не подключается:
1. Проверьте CORS_ORIGINS в Environment variables
2. Должно быть: `["https://timesheet-backend.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]`
3. После изменения сервис автоматически перезапустится

---

## 💰 СТОИМОСТЬ

### Free Plan (для тестирования):
- **$0/месяц**
- Web Service: 750 часов (достаточно для 1 сервиса)
- PostgreSQL: 1 GB storage, 90 дней retention
- Ограничения: sleep mode, shared ресурсы

### Starter Plan (для production):
- **$7/месяц** за Web Service
- **$7/месяц** за PostgreSQL (опционально, можно использовать free)
- Без sleep mode
- Dedicated ресурсы
- 24/7 работа

**Итого для production:** ~$7-14/месяц

---

## 🔄 ОБНОВЛЕНИЕ ПРИЛОЖЕНИЯ

### Автоматическое (рекомендуется):
```powershell
# Внесите изменения
git add .
git commit -m "Update: описание"
git push

# Render автоматически задеплоит
```

### Ручное:
1. Dashboard → Ваш сервис
2. Нажмите **"Manual Deploy"**
3. Выберите ветку
4. Нажмите **"Deploy"**

---

## 🆘 РЕШЕНИЕ ПРОБЛЕМ

### Проблема 1: "Service unavailable"

**Причина:** Сервис "спит" (free plan)

**Решение:**
- Подождите 30-60 секунд (cold start)
- Или апгрейдните на Starter plan

### Проблема 2: "Database connection failed"

**Причина:** Неправильный DATABASE_URL

**Решение:**
1. Откройте PostgreSQL в Render
2. Скопируйте **Internal Database URL**
3. Обновите переменную DATABASE_URL
4. Сохраните

### Проблема 3: "Build failed"

**Причина:** Ошибка в requirements.txt или коде

**Решение:**
1. Посмотрите логи сборки
2. Исправьте ошибку локально
3. Закоммитьте и запушьте

### Проблема 4: CORS ошибки

**Причина:** Неправильный CORS_ORIGINS

**Решение:**
```bash
# В Environment variables добавьте:
CORS_ORIGINS=["https://ваш-render-url.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]
```

### Проблема 5: Миграции не применились

**Решение:**
1. Откройте Shell в Render
2. Выполните:
   ```bash
   cd backend
   alembic upgrade head
   ```

---

## 📋 ЧЕКЛИСТ РАЗВЁРТЫВАНИЯ

### Подготовка:
- [ ] Код загружен в GitHub
- [ ] Создан аккаунт на Render
- [ ] Render подключен к GitHub

### База данных:
- [ ] Создана PostgreSQL база
- [ ] Скопирован Internal Database URL

### Backend:
- [ ] Создан Web Service
- [ ] Настроены Environment Variables
- [ ] DATABASE_URL указан правильно
- [ ] CORS_ORIGINS настроен
- [ ] SECRET_KEY сгенерирован
- [ ] Деплой успешен
- [ ] Миграции применены

### Проверка:
- [ ] /health возвращает {"status":"healthy"}
- [ ] /docs открывается
- [ ] API отвечает на запросы

### Виджет:
- [ ] Виджет пересобран с Render URL
- [ ] Загружен в amoCRM
- [ ] Включен и настроен
- [ ] Протестирован в карточках

---

## ✅ СЛЕДУЮЩИЕ ШАГИ

После успешного развёртывания:

1. **Тестируйте виджет** в amoCRM
2. **Собирайте обратную связь** от пользователей
3. **Мониторьте метрики** в Render dashboard
4. **Настройте резервное копирование** БД
5. **При необходимости** апгрейдьте на Starter plan

---

## 🎯 ПРЕИМУЩЕСТВА RENDER vs VPS

### Render:
✅ Проще в настройке (10 минут)  
✅ Автоматический HTTPS  
✅ Автодеплой из GitHub  
✅ Не нужно настраивать сервер  
✅ Бесплатный план для тестирования  
❌ Sleep mode на free плане  
❌ Меньше контроля  

### VPS (DigitalOcean):
✅ Полный контроль  
✅ Без sleep mode  
✅ Больше ресурсов за те же деньги  
❌ Нужно настраивать (2-4 часа)  
❌ Нужны навыки Linux  
❌ Нужно настраивать SSL вручную  

**Рекомендация:**
- Для тестирования → Render (быстро и бесплатно)
- Для production с бюджетом < $15 → Render Starter
- Для production с высокими требованиями → VPS

---

**Время развёртывания:** 15-20 минут  
**Стоимость:** $0 (free) или $7-14/мес (production)  
**Результат:** Рабочий виджет в amoCRM ✅

**Следующий документ:** AMOCRM_WIDGET_TESTING_GUIDE.md для тестирования

**Создано:** 3 августа 2026  
**Версия:** 1.0.0
