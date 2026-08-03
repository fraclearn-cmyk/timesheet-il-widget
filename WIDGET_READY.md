# ✅ ВИДЖЕТ ГОТОВ К УСТАНОВКЕ В amoCRM!

**Дата:** 30 июля 2026, 10:40  
**Статус:** ✅ READY TO DEPLOY  
**Архив:** `timesheet_il_widget.zip` (10.37 KB)

---

## 🎉 ЧТО ВЫПОЛНЕНО

✅ **Структура виджета проверена**
- manifest.json
- script.js
- styles.css
- i18n/ru.json
- i18n/en.json

✅ **Изображения созданы**
- widget/images/logo.png (200x200px) - временная заглушка
- widget/images/icon.png (64x64px) - временная заглушка

✅ **Конфигурация обновлена**
- API URL: `http://localhost:8000/api/v1`
- CSS: Встроен в script.js
- Support Email: support@example.com
- Support Link: https://example.com/support

✅ **ZIP архив создан**
- Файл: `timesheet_il_widget.zip`
- Размер: 10.37 KB
- Все файлы упакованы корректно

---

## 📋 ЧТО НУЖНО СДЕЛАТЬ СЕЙЧАС

### ⚠️ ВАЖНО: Перед установкой в amoCRM

#### 1. Запустите Backend API (если еще не запущен)

```bash
# Запустите Docker Desktop (если еще не запущен)

# Запустите контейнеры
docker-compose up -d

# Примените миграции
docker-compose exec backend alembic upgrade head

# Проверьте работу
# Откройте http://localhost:8000/docs в браузере
```

#### 2. Сделайте API доступным из интернета

**Вариант А: ngrok (для тестирования)**
```bash
# Скачайте ngrok: https://ngrok.com/download
# Запустите:
ngrok http 8000

# Скопируйте URL (например: https://abc123.ngrok.io)
```

**Вариант Б: Production сервер**
- Разместите backend на сервере с доменом
- Настройте HTTPS (обязательно!)

#### 3. Пересоберите виджет с правильным URL

После того как получите публичный URL API, пересоберите виджет:

```powershell
# Замените YOUR-URL на реальный URL вашего API
.\build_widget.ps1 -ApiUrl "https://YOUR-NGROK-URL.ngrok.io/api/v1"

# Или для production:
.\build_widget.ps1 -ApiUrl "https://api.your-domain.com/api/v1" -SupportEmail "your@email.com"
```

#### 4. Настройте CORS в backend

Откройте файл `backend/app/main.py` и убедитесь, что настроен CORS:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.amocrm.ru",      # ← ОБЯЗАТЕЛЬНО!
        "https://*.amocrm.com",     # ← ОБЯЗАТЕЛЬНО!
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

После изменения:
```bash
docker-compose restart backend
```

---

## 🚀 УСТАНОВКА В amoCRM

### Шаг 1: Откройте amoCRM
1. Войдите в ваш аккаунт amoCRM
2. Нажмите на иконку шестерёнки (Настройки) в правом верхнем углу

### Шаг 2: Перейдите в раздел виджетов
1. Настройки → Интеграции → Виджеты
2. Нажмите "Добавить виджет" или "Загрузить свой виджет"

### Шаг 3: Загрузите архив
1. Выберите файл `timesheet_il_widget.zip` (в текущей папке)
2. Нажмите "Загрузить"
3. Дождитесь проверки (~30 секунд)

### Шаг 4: Настройте виджет
1. Включите виджет (тумблер "Вкл")
2. Выберите разделы для отображения:
   - ✅ Карточка лида
   - ✅ Карточка контакта
   - ✅ Карточка компании
   - ✅ Карточка задачи
3. Нажмите "Сохранить"

### Шаг 5: Тестирование
1. Откройте любую карточку в amoCRM
2. Найдите виджет "⏱️ Рабочее время" на боковой панели
3. Нажмите "▶️ Начать рабочий день"
4. Проверьте, что:
   - Таймер работает
   - Статус меняется
   - Данные сохраняются
   - Нет ошибок в консоли браузера (F12)

---

## 📁 СОЗДАННЫЕ ФАЙЛЫ

В вашей папке созданы следующие файлы:

### Основные:
- ✅ **timesheet_il_widget.zip** - готовый виджет для установки
- ✅ **widget/images/logo.png** - логотип виджета (заглушка)
- ✅ **widget/images/icon.png** - иконка виджета (заглушка)

### Документация:
- 📚 **AMOCRM_WIDGET_TESTING_GUIDE.md** - подробная инструкция
- 📚 **WIDGET_DEPLOYMENT_CHECKLIST.md** - чек-лист проверки
- 📚 **WIDGET_QUICK_START.md** - быстрый старт
- 📚 **WIDGET_READY.md** - этот файл

### Скрипты:
- 🔧 **build_widget.ps1** - основной скрипт сборки
- 🔧 **create_placeholder_images.ps1** - создание изображений
- 🔧 **prepare_widget.ps1** - полный скрипт с интерактивным режимом

---

## 🔄 ПЕРЕСБОРКА ВИДЖЕТА

Если нужно изменить настройки (URL, email и т.д.):

```powershell
# Базовая пересборка
.\build_widget.ps1

# С параметрами
.\build_widget.ps1 -ApiUrl "https://your-api.com/api/v1" -SupportEmail "your@email.com"

# Пример с ngrok
.\build_widget.ps1 -ApiUrl "https://abc123.ngrok.io/api/v1"

# С внешним CSS
.\build_widget.ps1 -ApiUrl "https://api.com/api/v1" -CssUrl "https://cdn.com/styles.css"
```

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

### 1. Текущий URL API: localhost
Виджет сейчас настроен на `http://localhost:8000/api/v1`, который **не будет работать из amoCRM**.

**Что делать:**
- Используйте ngrok для тестирования
- Или разместите backend на production сервере
- Затем пересоберите виджет с правильным URL

### 2. Изображения - временные заглушки
Созданы простые синие квадраты с текстом.

**Что делать:**
- Замените `widget/images/logo.png` на реальный логотип (200x200px)
- Замените `widget/images/icon.png` на реальную иконку (64x64px)
- Пересоберите виджет: `.\build_widget.ps1`

### 3. Docker не запущен
На момент сборки Docker не был запущен.

**Что делать:**
- Запустите Docker Desktop
- Выполните: `docker-compose up -d`
- Проверьте: `docker-compose ps`

---

## 🧪 ТЕСТИРОВАНИЕ

### Чек-лист перед установкой:
- [ ] Backend запущен (`docker-compose ps`)
- [ ] API доступен (`http://localhost:8000/docs` открывается)
- [ ] API доступен из интернета (ngrok или production)
- [ ] CORS настроен для *.amocrm.ru
- [ ] Виджет пересобран с правильным API URL
- [ ] У вас есть права администратора в amoCRM

### После установки в amoCRM:
- [ ] Виджет отображается в карточках
- [ ] Кнопка "Начать рабочий день" работает
- [ ] Таймер обновляется каждую секунду
- [ ] Перерыв и возобновление работают
- [ ] Завершение дня работает
- [ ] Данные сохраняются в БД
- [ ] Нет ошибок в консоли (F12)

---

## 📞 ПОЛЕЗНЫЕ КОМАНДЫ

### Работа с backend:
```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Логи
docker-compose logs backend -f

# Перезапуск
docker-compose restart backend

# Миграции
docker-compose exec backend alembic upgrade head

# Проверка БД
docker-compose exec db psql -U postgres -d timesheet_db -c "SELECT COUNT(*) FROM work_sessions;"
```

### Работа с виджетом:
```powershell
# Пересборка
.\build_widget.ps1

# С параметрами
.\build_widget.ps1 -ApiUrl "https://your-url.com/api/v1"

# Проверка архива
Expand-Archive -Path timesheet_il_widget.zip -DestinationPath temp_check
ls temp_check
```

---

## 📚 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

Подробные инструкции в файлах:
- **AMOCRM_WIDGET_TESTING_GUIDE.md** - все детали тестирования
- **WIDGET_DEPLOYMENT_CHECKLIST.md** - пошаговый чек-лист
- **WIDGET_QUICK_START.md** - быстрый старт за 15 минут

---

## ✨ СЛЕДУЮЩИЕ ШАГИ

1. **Запустите backend** (если не запущен)
2. **Настройте ngrok** или production сервер
3. **Пересоберите виджет** с правильным API URL
4. **Настройте CORS** в backend/app/main.py
5. **Загрузите в amoCRM** файл timesheet_il_widget.zip
6. **Протестируйте** все функции

---

**Время на установку:** ~30 минут  
**Статус:** Ready to Deploy ✅  
**Создано:** 30 июля 2026

Удачи с установкой! 🚀
