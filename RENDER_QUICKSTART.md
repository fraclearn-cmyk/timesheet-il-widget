# ⚡ RENDER.COM - БЫСТРЫЙ СТАРТ

**За 15 минут от кода до работающего виджета в amoCRM!**

---

## 🚀 3 ПРОСТЫХ ШАГА

### 1️⃣ GITHUB (5 минут)

```powershell
cd d:\табель
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/timesheet-il-widget.git
git push -u origin main
```

---

### 2️⃣ RENDER.COM (10 минут)

#### A. Зарегистрируйтесь
- https://render.com/
- Sign up with GitHub

#### B. Создайте базу данных
- New + → PostgreSQL
- Name: `timesheet-db`
- Region: Frankfurt
- Plan: Free
- Create Database
- **Скопируйте Internal Database URL**

#### C. Создайте Web Service
- New + → Web Service
- Выберите репозиторий: `timesheet-il-widget`
- Name: `timesheet-backend`
- Region: Frankfurt
- Root Directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Plan: Free

#### D. Добавьте переменные окружения

```bash
DATABASE_URL=<Internal Database URL из шага B>
API_HOST=0.0.0.0
DEBUG=False
CORS_ORIGINS=["https://timesheet-backend.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]
SECRET_KEY=<сгенерируйте: python -c "import secrets; print(secrets.token_urlsafe(32))">
```

- Create Web Service
- Дождитесь деплоя (2-5 минут)

#### E. Примените миграции
- В dashboard → Shell
- Выполните: `cd backend && alembic upgrade head`

#### F. Проверьте
- https://timesheet-backend.onrender.com/health
- Должно вернуть: `{"status":"healthy"}`

---

### 3️⃣ ВИДЖЕТ В amoCRM (5 минут)

```powershell
# Пересобрать виджет
cd d:\табель
.\build_widget.ps1 -ApiUrl "https://timesheet-backend.onrender.com/api/v1"
```

**В amoCRM:**
1. Настройки → Интеграции → Виджеты
2. Загрузить свой виджет
3. Выбрать: `timesheet_il_widget.zip`
4. Включить виджет
5. Выбрать разделы (лиды, контакты, компании, сделки)
6. Сохранить
7. Протестировать в любой карточке

---

## ✅ ГОТОВО!

Виджет работает в amoCRM! 🎉

---

## 🔄 ОБНОВЛЕНИЕ

```powershell
# Внесите изменения в код
git add .
git commit -m "Update"
git push

# Render автоматически задеплоит (2-5 минут)
# Пересоберите и переза грузите виджет
```

---

## 🆘 ЕСЛИ НЕ РАБОТАЕТ

### Backend не отвечает
- Подождите 60 секунд (cold start на free плане)
- Проверьте логи в Render dashboard

### CORS ошибка
```bash
# В Environment variables проверьте:
CORS_ORIGINS=["https://ваш-url.onrender.com","https://*.amocrm.ru","https://*.amocrm.com"]
```

### Миграции не применились
```bash
# В Shell:
cd backend
alembic upgrade head
```

---

## 💰 СТОИМОСТЬ

**Free Plan:** $0/месяц
- ⚠️ Sleep mode (засыпает после 15 мин)
- ⚠️ Cold start (первый запрос 30-60 сек)

**Starter Plan:** $7/месяц
- ✅ Без sleep mode
- ✅ 24/7 работа

---

## 📚 ПОДРОБНЕЕ

**RENDER_DEPLOYMENT.md** - полная инструкция

---

**Время:** 15-20 минут  
**Стоимость:** $0 (бесплатно)  
**Результат:** Рабочий виджет ✅
