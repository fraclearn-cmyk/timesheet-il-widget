# ⚡ RAILWAY.APP - БЫСТРЫЙ СТАРТ

**За 15 минут до работающего виджета!**

---

## 🚀 ПОШАГОВАЯ ИНСТРУКЦИЯ

### 1. РЕГИСТРАЦИЯ (2 минуты)
1. Откройте: https://railway.app/
2. **Login with GitHub**
3. Авторизуйте Railway

---

### 2. СОЗДАНИЕ ПРОЕКТА (1 минута)
1. **New Project**
2. **Deploy from GitHub repo**
3. Выберите: **fraclearn-cmyk/timesheet-il-widget**

---

### 3. ДОБАВИТЬ POSTGRESQL (1 минута)
1. **+ New** → **Database** → **Add PostgreSQL**
2. Подождите ~30 секунд

---

### 4. НАСТРОИТЬ BACKEND (3 минуты)
Кликните на сервис → **Settings**:

```
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

### 5. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (2 минуты)

Перейдите в **Variables** → **New Variable**:

```bash
API_HOST=0.0.0.0
DEBUG=False
CORS_ORIGINS=["https://*.up.railway.app","https://*.amocrm.ru","https://*.amocrm.com"]
SECRET_KEY=<сгенерируйте: python -c "import secrets; print(secrets.token_urlsafe(32))">
```

**DATABASE_URL** уже добавлен автоматически! ✅

---

### 6. ГЕНЕРАЦИЯ ДОМЕНА (1 минута)
**Settings** → **Networking** → **Generate Domain**

Скопируйте URL (формат: `xxx.up.railway.app`)

---

### 7. ОБНОВИТЬ CORS (1 минута)
**Variables** → **CORS_ORIGINS** → Обновите:
```json
["https://ваш-url.up.railway.app","https://*.amocrm.ru","https://*.amocrm.com"]
```

---

### 8. ДЕПЛОЙ (2-5 минут)
**Deployments** → Следите за логами → Дождитесь **Success** ✅

---

### 9. МИГРАЦИИ (1 минута)

**Локально:**
```powershell
# Скопируйте DATABASE_URL из Railway Variables
$env:DATABASE_URL="postgresql://..."
cd d:\табель\backend
alembic upgrade head
```

---

### 10. ПРОВЕРКА (1 минута)
Откройте: `https://ваш-url.up.railway.app/health`

Должно вернуть: `{"status":"healthy"}` ✅

---

## ✅ ГОТОВО!

Теперь:
1. Пересоберите виджет с Railway URL
2. Загрузите в amoCRM
3. Тестируйте!

---

## 💰 СТОИМОСТЬ

**$5/месяц бесплатно** - хватит на 100-150 часов работы

---

## 📚 ПОДРОБНЕЕ

**RAILWAY_DEPLOYMENT.md** - полная инструкция

---

**Время:** 15-20 минут  
**Результат:** Рабочий виджет ✅
