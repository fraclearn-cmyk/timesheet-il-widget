# 🚂 РАЗВЁРТЫВАНИЕ НА RAILWAY.APP

**Преимущества Railway:**
- ✅ $5 бесплатно каждый месяц
- ✅ Не требует карту сразу
- ✅ Интеграция с GitHub
- ✅ Автоматический HTTPS
- ✅ PostgreSQL включена
- ✅ Простая настройка

**Время:** 15-20 минут  
**Стоимость:** Бесплатно (хватит $5/месяц на ~100-150 часов)

---

## ⚡ БЫСТРЫЙ СТАРТ

### ШАГ 1: Регистрация на Railway (2 минуты)

1. Откройте: https://railway.app/
2. Нажмите **"Start a New Project"** или **"Login"**
3. Выберите **"Login with GitHub"**
4. Авторизуйте Railway через GitHub
5. Подтвердите email если попросят

---

### ШАГ 2: Создание нового проекта (1 минута)

1. После входа нажмите **"New Project"**
2. Выберите **"Deploy from GitHub repo"**
3. Если попросит - дайте доступ к репозиториям
4. Выберите репозиторий: **fraclearn-cmyk/timesheet-il-widget**
5. Railway начнёт анализ проекта

---

### ШАГ 3: Настройка PostgreSQL (2 минуты)

1. В проекте нажмите **"+ New"**
2. Выберите **"Database"** → **"Add PostgreSQL"**
3. Railway автоматически создаст базу
4. Подождите ~30 секунд

**PostgreSQL автоматически создаст переменную DATABASE_URL!**

---

### ШАГ 4: Настройка Backend Service (5 минут)

1. Кликните на ваш сервис (fraclearn-cmyk/timesheet-il-widget)
2. Перейдите в **"Settings"**

#### 4.1. Root Directory
- Найдите **"Root Directory"**
- Установите: `backend`
- Сохраните

#### 4.2. Start Command
- Найдите **"Start Command"**
- Установите: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Сохраните

#### 4.3. Build Command
- Найдите **"Build Command"**  
- Установите: `pip install -r requirements.txt`
- Сохраните

---

### ШАГ 5: Переменные окружения (3 минуты)

1. Перейдите в **"Variables"** (вкладка)
2. Railway уже добавил **DATABASE_URL** автоматически
3. Добавьте остальные переменные:

Нажимайте **"New Variable"** для каждой:

```bash
# API Settings
API_HOST=0.0.0.0
DEBUG=False

# CORS - ВАЖНО! Обновите после получения домена
CORS_ORIGINS=["https://*.up.railway.app","https://*.amocrm.ru","https://*.amocrm.com"]

# Security - сгенерируйте!
SECRET_KEY=ваш_секретный_ключ_64_символа
```

**Генерация SECRET_KEY:**
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### ШАГ 6: Настройка домена (1 минута)

1. Перейдите в **"Settings"**
2. Найдите **"Networking"** → **"Public Networking"**
3. Нажмите **"Generate Domain"**
4. Railway создаст домен вида: `ваш-проект.up.railway.app`
5. **Скопируйте этот URL!**

---

### ШАГ 7: Обновите CORS_ORIGINS (1 минута)

1. Вернитесь в **"Variables"**
2. Найдите **CORS_ORIGINS**
3. Обновите на ваш реальный домен:
```json
["https://ваш-проект.up.railway.app","https://*.amocrm.ru","https://*.amocrm.com"]
```
4. Сохраните

---

### ШАГ 8: Деплой (2-5 минут)

1. Перейдите в **"Deployments"**
2. Railway автоматически начнёт деплой
3. Следите за логами
4. Дождитесь статуса **"Success"** ✅

---

### ШАГ 9: Применение миграций (1 минута)

После успешного деплоя нужно применить миграции:

**Вариант А: Через Railway CLI**
```bash
# Установить Railway CLI
npm install -g @railway/cli

# Логин
railway login

# Подключиться к проекту
railway link

# Выполнить миграции
railway run cd backend && alembic upgrade head
```

**Вариант Б: Локально с подключением к Railway БД**
```powershell
# В Railway: Variables → DATABASE_URL → копировать значение
$env:DATABASE_URL="postgresql://user:pass@host/railway"

cd d:\табель\backend
alembic upgrade head
```

---

### ШАГ 10: Проверка (1 минута)

Откройте в браузере:
```
https://ваш-проект.up.railway.app/health
```

Должно вернуть:
```json
{"status":"healthy"}
```

Также проверьте:
```
https://ваш-проект.up.railway.app/docs
```

**Если работает - backend готов!** ✅

---

## 🔧 НАСТРОЙКА railway.json

Создайте файл `railway.json` в корне проекта для автоматизации:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "cd backend && pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

Загрузите в GitHub:
```powershell
git add railway.json
git commit -m "Add Railway configuration"
git push
```

---

## 💰 СТОИМОСТЬ

### Starter Plan (бесплатный):
- **$5/месяц** в кредитах
- ~500 часов исполнения
- 512 MB RAM
- Shared CPU
- PostgreSQL 1GB

### Хватит на:
- Тестирование: 1-2 месяца
- Активное использование: ~150 часов/месяц
- Для production нужен платный план

### Developer Plan:
- **$5/месяц** + usage
- ~$10-20/месяц обычно хватает

---

## 🔄 АВТОМАТИЧЕСКИЙ ДЕПЛОЙ

Railway автоматически отслеживает GitHub:
```powershell
# Внесите изменения
git add .
git commit -m "Update: улучшения"
git push

# Railway автоматически задеплоит (1-3 минуты)
```

---

## 📊 МОНИТОРИНГ

### Метрики
1. Откройте ваш сервис
2. Перейдите в **"Metrics"**
3. Смотрите:
   - CPU usage
   - Memory usage  
   - Network
   - Build time

### Логи
1. Перейдите в **"Deployments"**
2. Кликните на активный деплой
3. Смотрите логи в реальном времени

---

## 🗄️ РАБОТА С БАЗОЙ ДАННЫХ

### Подключение
1. Откройте PostgreSQL сервис
2. Перейдите в **"Connect"**
3. Скопируйте credentials:
   - **Host**
   - **Port**
   - **Database**
   - **Username**
   - **Password**

### Подключение через psql:
```bash
psql postgresql://user:pass@host:port/railway
```

### Backup:
```bash
pg_dump postgresql://user:pass@host:port/railway > backup.sql
```

---

## 🆘 РЕШЕНИЕ ПРОБЛЕМ

### Проблема 1: Деплой failed

**Причина:** Ошибка в коде или зависимостях

**Решение:**
1. Посмотрите логи деплоя
2. Исправьте ошибку локально
3. Закоммитьте и запушьте

### Проблема 2: Database connection failed

**Причина:** DATABASE_URL неправильный

**Решение:**
1. Проверьте что PostgreSQL запущен
2. Variables → DATABASE_URL должен быть установлен автоматически
3. Если нет - скопируйте из PostgreSQL → Connect

### Проблема 3: CORS ошибки

**Причина:** Неправильный CORS_ORIGINS

**Решение:**
```bash
# В Variables обновите:
CORS_ORIGINS=["https://ваш-домен.up.railway.app","https://*.amocrm.ru","https://*.amocrm.com"]
```

### Проблема 4: Port already in use

**Причина:** Неправильная команда запуска

**Решение:**
Start Command должна использовать `$PORT`:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## 📋 ЧЕКЛИСТ

- [ ] Зарегистрирован на Railway.app
- [ ] Создан новый проект
- [ ] Репозиторий подключен
- [ ] PostgreSQL добавлена
- [ ] Root Directory установлен (backend)
- [ ] Build Command установлен
- [ ] Start Command установлен
- [ ] Переменные окружения добавлены
- [ ] Домен сгенерирован
- [ ] CORS_ORIGINS обновлён
- [ ] Деплой успешен
- [ ] Миграции применены
- [ ] /health отвечает
- [ ] /docs открывается

---

## ✅ СЛЕДУЮЩИЕ ШАГИ

После успешного развёртывания:

1. **Пересобрать виджет** с Railway URL
2. **Загрузить в amoCRM**
3. **Протестировать**
4. **Мониторить использование кредитов**

---

**Создано:** 3 августа 2026  
**Версия:** 1.0.0  
**Платформа:** Railway.app
