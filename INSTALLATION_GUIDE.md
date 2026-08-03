# 🚀 ПОШАГОВАЯ ИНСТРУКЦИЯ ПО УСТАНОВКЕ ВИДЖЕТА

**Дата:** 30.07.2026  
**Для виджета:** Табель IL Widget  
**Предполагаемое время:** 30-60 минут

---

## 📋 ЧТО ВАМ ПОНАДОБИТСЯ

- ✅ Аккаунт amoCRM (у вас есть)
- ✅ Права администратора в amoCRM
- ⏳ Сервер для хостинга backend (настроим)
- ⏳ Хостинг для виджета (настроим)

---

## 🎯 ПЛАН ДЕЙСТВИЙ

### Этап 1: Запуск Backend (10-15 минут)
### Этап 2: Подготовка виджета для amoCRM (5 минут)
### Этап 3: Регистрация виджета в amoCRM (10-15 минут)
### Этап 4: Установка виджета в ваш аккаунт (5 минут)
### Этап 5: Тестирование (10-20 минут)

---

## ЭТАП 1: ЗАПУСК BACKEND (локально для тестирования)

### Шаг 1.1: Проверка Docker

```bash
# Откройте командную строку (cmd) и проверьте Docker
docker --version
docker-compose --version
```

Если Docker не установлен:
- Скачайте Docker Desktop для Windows с https://www.docker.com/products/docker-desktop
- Установите и перезагрузите компьютер

### Шаг 1.2: Запуск проекта

```bash
# Перейдите в папку проекта
cd d:\табель

# Запустите backend и базу данных
docker-compose up -d

# Дождитесь запуска (30-60 секунд)
# Проверьте статус
docker-compose ps
```

Вы должны увидеть 2 запущенных контейнера:
- `timesheet-backend` (running)
- `timesheet-postgres` (running)

### Шаг 1.3: Применение миграций БД

```bash
# Примените миграции для создания таблиц
docker-compose exec backend alembic upgrade head
```

Должны увидеть:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002
```

### Шаг 1.4: Проверка работоспособности

Откройте браузер и перейдите:
- **Swagger UI:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

Если видите Swagger UI с 44 endpoints - backend работает! ✅

---

## ЭТАП 2: ПОДГОТОВКА ВИДЖЕТА ДЛЯ AMOCRM

### Шаг 2.1: Установка ngrok (для локального тестирования)

Чтобы amoCRM мог подключиться к вашему локальному backend, нужен туннель.

1. Скачайте ngrok: https://ngrok.com/download
2. Распакуйте в удобную папку (например, `C:\ngrok\`)
3. Зарегистрируйтесь на ngrok.com и получите authtoken
4. Настройте ngrok:

```bash
# В новом окне командной строки
cd C:\ngrok
ngrok authtoken ВАШ_ТОКЕН_ИЗ_NGROK_COM
```

### Шаг 2.2: Запуск туннеля для backend

```bash
# Запустите туннель на порт 8000 (backend)
ngrok http 8000
```

Вы увидите что-то вроде:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

**ВАЖНО:** Скопируйте URL `https://abc123.ngrok.io` - это ваш публичный адрес backend!

### Шаг 2.3: Запуск туннеля для виджета

Откройте **второе** окно командной строки:

```bash
# Перейдите в папку виджета
cd d:\табель\widget

# Запустите простой HTTP сервер
python -m http.server 8080
```

Откройте **третье** окно командной строки:

```bash
# Запустите второй туннель на порт 8080 (виджет)
cd C:\ngrok
ngrok http 8080
```

Скопируйте второй URL, например: `https://xyz789.ngrok.io`

### Шаг 2.4: Обновление конфигурации виджета

Откройте файл `d:\табель\widget\script.js` в редакторе и измените строку 13:

**БЫЛО:**
```javascript
apiBaseUrl: 'http://localhost:8000/api/v1',
```

**ДОЛЖНО БЫТЬ:**
```javascript
apiBaseUrl: 'https://abc123.ngrok.io/api/v1',  // Ваш ngrok URL backend
```

Сохраните файл!

---

## ЭТАП 3: РЕГИСТРАЦИЯ ВИДЖЕТА В AMOCRM

### Шаг 3.1: Перейдите в раздел разработчиков

1. Откройте https://www.amocrm.ru/developers/
2. Войдите в свой аккаунт amoCRM
3. Перейдите в раздел "Интеграции" → "Создать интеграцию"

### Шаг 3.2: Создайте новую интеграцию

Заполните форму:

**Основная информация:**
- **Название:** Табель IL
- **Описание:** Виджет учёта рабочего времени с Activity Tracking
- **Ссылка на сайт:** `https://xyz789.ngrok.io` (ваш ngrok URL виджета)
- **Тип интеграции:** Виджет

**Доступы (Scopes):**
Выберите следующие права:
- ✅ Контакты (чтение)
- ✅ Сделки (чтение)
- ✅ Компании (чтение)
- ✅ Задачи (чтение)
- ✅ Пользователи (чтение)

**Redirect URI (если потребуется):**
```
https://xyz789.ngrok.io/oauth
```

Нажмите "Создать интеграцию"

### Шаг 3.3: Получите данные интеграции

После создания вы получите:
- **Integration ID** (ID интеграции)
- **Secret Key** (секретный ключ)
- **Client ID** и **Client Secret** (для OAuth)

Сохраните эти данные!

### Шаг 3.4: Настройка манифеста виджета

Откройте `d:\табель\widget\manifest.json` и обновите:

```json
{
  "widget": {
    "name": "widget.timesheet_il",
    "description": "Виджет учёта рабочего времени",
    "short_description": "Учёт времени и активности",
    "version": "1.0.0",
    "interface_version": 2,
    "init_once": false,
    "locale": ["ru", "en"],
    "installation": true,
    
    "support": {
      "link": "https://xyz789.ngrok.io",
      "email": "support@example.com"
    },
    
    "images": {
      "logo": "https://via.placeholder.com/256x256.png?text=Timesheet+IL",
      "icon": "https://via.placeholder.com/48x48.png?text=TI"
    },
    
    "locations": [
      "lcard",
      "ccard", 
      "comcard",
      "tcard",
      "settings"
    ],
    
    "settings": {
      "login": "",
      "client_id": "ВАШ_CLIENT_ID_ИЗ_AMOCRM",
      "client_secret": "ВАШ_CLIENT_SECRET",
      "redirect_uri": "https://xyz789.ngrok.io/oauth"
    },
    
    "scopes": [
      "crm"
    ]
  }
}
```

Сохраните файл!

---

## ЭТАП 4: УСТАНОВКА ВИДЖЕТА В АККАУНТ

### Шаг 4.1: Установка через настройки amoCRM

**Вариант А: Через Marketplace (рекомендуется после публикации)**
1. Откройте ваш amoCRM
2. Перейдите в Настройки → Интеграции → Marketplace
3. Найдите "Табель IL"
4. Нажмите "Установить"

**Вариант Б: Через прямую ссылку (для разработки)**
1. Перейдите в Настройки → Интеграции
2. Нажмите "Установить виджет"
3. Введите URL: `https://xyz789.ngrok.io/manifest.json`
4. Нажмите "Установить"

### Шаг 4.2: Настройка виджета

После установки:
1. Откройте настройки виджета "Табель IL"
2. При необходимости введите:
   - API URL: `https://abc123.ngrok.io/api/v1`
   - Account ID: ваш ID аккаунта amoCRM
3. Сохраните настройки

### Шаг 4.3: Активация виджета

1. Убедитесь, что виджет активирован (переключатель ON)
2. Выберите, где виджет должен отображаться:
   - ✅ Карточка сделки
   - ✅ Карточка контакта
   - ✅ Карточка компании
   - ✅ Карточка задачи
3. Сохраните

---

## ЭТАП 5: ТЕСТИРОВАНИЕ

### Шаг 5.1: Первый запуск

1. Откройте любую карточку сделки (Lead) в amoCRM
2. В правой панели должен появиться виджет "⏱️ Рабочее время"
3. Вы должны увидеть:
   - Заголовок виджета
   - Статус: "Рабочий день не начат"
   - Кнопка "Начать рабочий день"

### Шаг 5.2: Тест базового функционала

**Тест 1: Начало рабочего дня**
1. Нажмите "Начать рабочий день"
2. Должно произойти:
   - Статус изменится на "✅ Работаю"
   - Появится таймер (00:00:01, 00:00:02...)
   - Кнопки изменятся на "Перерыв" и "Завершить день"

**Тест 2: Перерыв**
1. Нажмите "Перерыв"
2. Должно произойти:
   - Статус изменится на "⏸️ На перерыве"
   - Таймер покажет время работы
   - Появится информация о перерывах
   - Кнопка изменится на "Продолжить работу"

**Тест 3: Возобновление работы**
1. Нажмите "Продолжить работу"
2. Статус вернётся в "✅ Работаю"
3. Таймер продолжит отсчёт

**Тест 4: Activity Tracking**
1. При открытой сессии переключитесь между карточками
2. Виджет должен автоматически отслеживать:
   - На какой карточке вы работаете
   - Сколько времени потратили на каждую

**Тест 5: Завершение дня**
1. Нажмите "Завершить день"
2. Статус изменится на "✔️ День завершён"
3. Таймер остановится

### Шаг 5.3: Проверка данных через API

Откройте Swagger UI: http://localhost:8000/docs

**Проверьте данные:**
1. `GET /api/v1/sessions/history/{user_id}` - История сессий
2. `GET /api/v1/activity/history/{work_session_id}` - История активностей
3. `GET /api/v1/team/status` - Статус команды
4. `GET /api/v1/reports/daily` - Дневной отчёт

### Шаг 5.4: Проверка БД

```bash
# Подключитесь к PostgreSQL
docker-compose exec postgres psql -U timesheet -d timesheet_db

# Проверьте данные
SELECT * FROM work_sessions;
SELECT * FROM activity_sessions;
SELECT * FROM status_transitions;

# Выход
\q
```

---

## 🐛 ВОЗМОЖНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема 1: Виджет не отображается в amoCRM

**Решение:**
1. Проверьте, что ngrok туннели запущены (оба)
2. Проверьте URL в манифесте - должен быть ngrok URL
3. Очистите кэш браузера (Ctrl+F5)
4. Проверьте настройки виджета в amoCRM

### Проблема 2: Ошибка "Cannot connect to API"

**Решение:**
1. Проверьте, что backend запущен: http://localhost:8000/health
2. Проверьте URL в `script.js` - должен быть ngrok URL backend
3. Проверьте CORS настройки в backend
4. Посмотрите логи backend: `docker-compose logs backend`

### Проблема 3: Виджет отображается, но кнопки не работают

**Решение:**
1. Откройте консоль браузера (F12)
2. Проверьте ошибки JavaScript
3. Проверьте Network tab - есть ли запросы к API
4. Проверьте, что API возвращает корректные данные

### Проблема 4: "CORS error"

**Решение:**
Обновите CORS в backend (`backend/app/main.py`):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для разработки
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Перезапустите backend: `docker-compose restart backend`

### Проблема 5: Данные не сохраняются

**Решение:**
1. Проверьте, что миграции применены: `docker-compose exec backend alembic current`
2. Проверьте логи БД: `docker-compose logs postgres`
3. Проверьте подключение: `docker-compose exec postgres psql -U timesheet -d timesheet_db -c "\dt"`

---

## 📝 ЧЕКЛИСТ ПЕРЕД ТЕСТИРОВАНИЕМ

### Backend
- [ ] Docker запущен
- [ ] Backend контейнер работает (docker-compose ps)
- [ ] Миграции применены (alembic upgrade head)
- [ ] Swagger UI открывается (http://localhost:8000/docs)
- [ ] Health check работает (http://localhost:8000/health)
- [ ] Ngrok туннель для backend запущен

### Виджет
- [ ] HTTP сервер запущен (python -m http.server 8080)
- [ ] Ngrok туннель для виджета запущен
- [ ] script.js обновлён с ngrok URL backend
- [ ] manifest.json обновлён с Client ID/Secret

### amoCRM
- [ ] Интеграция создана
- [ ] Client ID и Secret получены
- [ ] Виджет установлен в аккаунт
- [ ] Виджет активирован
- [ ] Locations выбраны (lcard, ccard и т.д.)

---

## 🎯 ЧТО ДАЛЬШЕ?

После успешного тестирования:

### Краткосрочно (1-2 дня)
1. Потестировать все сценарии использования
2. Собрать feedback от пользователей
3. Исправить найденные баги

### Среднесрочно (1-2 недели)
1. Добавить Excel export для отчётов
2. Создать логотип и иконку виджета
3. Написать unit/integration тесты
4. Добавить больше настроек

### Долгосрочно (1+ месяц)
1. Production deployment на выделенный сервер
2. Мониторинг и логирование (Sentry)
3. Backup стратегия для БД
4. Публикация в Marketplace amoCRM

---

## 📞 ПОДДЕРЖКА

### Полезные ссылки
- **Swagger UI:** http://localhost:8000/docs
- **amoCRM Developers:** https://www.amocrm.ru/developers/
- **Документация проекта:** См. все MD файлы в `d:\табель\`

### Логи для диагностики
```bash
# Backend логи
docker-compose logs backend -f

# PostgreSQL логи
docker-compose logs postgres -f

# Все логи
docker-compose logs -f
```

### Файлы конфигурации
- Backend config: `backend/app/core/config.py`
- Database: `docker-compose.yml`
- Widget config: `widget/manifest.json`
- Widget code: `widget/script.js`

---

**Удачи! Если возникнут проблемы - смотрите раздел "Возможные проблемы" или проверьте логи!** 🚀
