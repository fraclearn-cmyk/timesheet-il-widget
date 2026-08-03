# 🚀 БЫСТРЫЙ СТАРТ: УСТАНОВКА ВИДЖЕТА В amoCRM

**Виджет:** Timesheet IL v1.0.0  
**Время установки:** ~30 минут  
**Уровень:** Начальный

---

## 📌 ЧТО НУЖНО СДЕЛАТЬ

### Вариант А: Автоматическая подготовка (рекомендуется) ⚡

```powershell
# 1. Создайте изображения (logo.png и icon.png)
# Поместите их в widget/images/

# 2. Запустите скрипт подготовки
.\prepare_widget.ps1

# 3. Следуйте инструкциям на экране
# Скрипт спросит:
# - URL вашего API backend
# - URL для CSS (или встроит в script.js)
# - Email поддержки
# - Ссылку на support

# 4. Получите готовый архив: timesheet_il_widget.zip

# 5. Загрузите в amoCRM
```

### Вариант Б: Ручная подготовка 🔧

```powershell
# 1. Создайте изображения
mkdir widget\images
# Добавьте logo.png (200x200px) и icon.png (64x64px)

# 2. Обновите API URL в widget/script.js (строка 13)
# apiBaseUrl: 'https://ваш-api-url.com/api/v1'

# 3. Обновите CSS URL в widget/script.js (строка 145)
# var cssUrl = 'https://ваш-css-url.com/widget/styles.css';

# 4. Обновите manifest.json (email и support link)

# 5. Создайте ZIP архив
cd widget
Compress-Archive -Force -Path manifest.json,script.js,styles.css,i18n,images -DestinationPath ..\timesheet_il_widget.zip

# 6. Загрузите в amoCRM
```

---

## 🎯 ПОШАГОВАЯ ИНСТРУКЦИЯ

### ШАГ 1: Подготовка изображений (5 минут)

Создайте два изображения:

1. **logo.png** - 200x200px (логотип виджета)
2. **icon.png** - 64x64px (иконка в списке виджетов)

Поместите в папку `widget/images/`

**Где создать:**
- Photoshop / GIMP
- Онлайн: [Canva](https://canva.com), [Figma](https://figma.com)
- Генераторы логотипов

---

### ШАГ 2: Запуск backend (5 минут)

```bash
# Убедитесь, что Docker запущен
docker --version

# Запустите контейнеры
cd d:\табель
docker-compose up -d

# Примените миграции
docker-compose exec backend alembic upgrade head

# Проверьте работу
start http://localhost:8000/docs
```

**Ожидаемый результат:** Swagger UI открывается и показывает все API endpoints.

---

### ШАГ 3: Сделайте API публичным (10 минут)

Виджет в amoCRM должен иметь доступ к вашему API из интернета.

#### Вариант 3.1: ngrok (для тестирования)

```bash
# Скачайте и установите ngrok: https://ngrok.com/download

# Запустите туннель
ngrok http 8000

# Скопируйте URL (например: https://abc123.ngrok.io)
```

#### Вариант 3.2: Production сервер

Разместите backend на сервере с доменом:
- AWS, DigitalOcean, Heroku и т.д.
- Настройте SSL (HTTPS обязателен для production)

---

### ШАГ 4: Запустите скрипт подготовки (5 минут)

```powershell
# Из корня проекта
cd d:\табель

# Запустите скрипт
.\prepare_widget.ps1

# Или с параметрами:
.\prepare_widget.ps1 -ApiUrl "https://abc123.ngrok.io/api/v1" -SupportEmail "your@email.com"
```

**Скрипт автоматически:**
- ✅ Проверит все файлы
- ✅ Обновит URL в script.js
- ✅ Встроит CSS или настроит URL
- ✅ Обновит manifest.json
- ✅ Создаст ZIP архив
- ✅ Проверит backend

**Результат:** Файл `timesheet_il_widget.zip` готов к загрузке.

---

### ШАГ 5: Установка в amoCRM (5 минут)

1. **Откройте amoCRM**
   - Войдите в ваш аккаунт
   - Нажмите на шестерёнку (Настройки) в правом верхнем углу

2. **Перейдите в Виджеты**
   - Настройки → Интеграции → Виджеты
   - Нажмите "Добавить виджет" или "Загрузить свой виджет"

3. **Загрузите архив**
   - Выберите файл `timesheet_il_widget.zip`
   - Нажмите "Загрузить"
   - Дождитесь проверки (~30 секунд)

4. **Настройте виджет**
   - Включите виджет (тумблер "Вкл")
   - Выберите разделы для отображения:
     - ✅ Карточка лида
     - ✅ Карточка контакта
     - ✅ Карточка компании
     - ✅ Карточка задачи
   - Нажмите "Сохранить"

---

### ШАГ 6: Тестирование (5 минут)

1. **Откройте карточку**
   - Откройте любую сделку/контакт/компанию
   - Найдите виджет "⏱️ Рабочее время" на боковой панели

2. **Проверьте функции**
   - Нажмите "▶️ Начать рабочий день"
   - Проверьте, что таймер работает
   - Попробуйте "⏸️ Перерыв"
   - Попробуйте "▶️ Продолжить работу"
   - Попробуйте "⏹️ Завершить день"

3. **Проверьте консоль (F12)**
   - Не должно быть ошибок
   - Должны быть успешные API запросы

---

## ⚡ ЭКСПРЕСС-УСТАНОВКА (для опытных)

```bash
# 1. Создать изображения в widget/images/

# 2. Запустить backend
docker-compose up -d && docker-compose exec backend alembic upgrade head

# 3. Запустить ngrok (в новом окне)
ngrok http 8000

# 4. Запустить скрипт (заменить URL на ngrok URL)
.\prepare_widget.ps1 -ApiUrl "https://YOUR-NGROK-URL.ngrok.io/api/v1"

# 5. Загрузить timesheet_il_widget.zip в amoCRM

# 6. Готово! ✨
```

**Время:** ~15 минут

---

## 🔧 НАСТРОЙКА CORS (ВАЖНО!)

Убедитесь, что в `backend/app/main.py` настроен CORS:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.amocrm.ru",      # ← ОБЯЗАТЕЛЬНО
        "https://*.amocrm.com",     # ← ОБЯЗАТЕЛЬНО
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

После изменения перезапустите backend:
```bash
docker-compose restart backend
```

---

## 📋 ЧЕКЛИСТ ПЕРЕД УСТАНОВКОЙ

- [ ] ✅ Backend запущен (`docker-compose ps`)
- [ ] ✅ API доступен (`http://localhost:8000/docs` открывается)
- [ ] ✅ API доступен из интернета (через ngrok или сервер)
- [ ] ✅ CORS настроен для *.amocrm.ru
- [ ] ✅ Миграции применены (`alembic upgrade head`)
- [ ] ✅ Изображения созданы (logo.png, icon.png)
- [ ] ✅ ZIP архив создан (`timesheet_il_widget.zip`)
- [ ] ✅ У вас есть доступ к amoCRM с правами администратора

---

## 🐛 РЕШЕНИЕ ПРОБЛЕМ

### Проблема: "Виджет не загружается"

```powershell
# 1. Проверьте структуру архива
Expand-Archive -Path timesheet_il_widget.zip -DestinationPath temp_check
ls temp_check
# Должны быть: manifest.json, script.js, styles.css, i18n/, images/

# 2. Очистите кэш браузера
# Ctrl+Shift+Delete

# 3. Проверьте консоль браузера (F12)
# Ищите ошибки JavaScript
```

### Проблема: "CORS error"

```bash
# Добавьте в backend/app/main.py:
allow_origins=["https://*.amocrm.ru", "https://*.amocrm.com"]

# Перезапустите:
docker-compose restart backend
```

### Проблема: "API недоступен"

```bash
# Проверьте Docker:
docker-compose ps
# Все контейнеры должны быть Up

# Проверьте логи:
docker-compose logs backend --tail=50

# Проверьте доступность:
curl http://localhost:8000/docs
```

### Проблема: "Данные не сохраняются"

```bash
# Проверьте миграции:
docker-compose exec backend alembic current
docker-compose exec backend alembic upgrade head

# Проверьте таблицы БД:
docker-compose exec db psql -U postgres -d timesheet_db -c "\dt"
```

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### Документация проекта:
- **AMOCRM_WIDGET_TESTING_GUIDE.md** - Подробная инструкция (все детали)
- **WIDGET_DEPLOYMENT_CHECKLIST.md** - Чек-лист проверки
- **WIDGET_COMPLETE.md** - Описание всех функций виджета

### Скрипты:
- **prepare_widget.ps1** - Автоматическая подготовка виджета

### Команды для работы:

```bash
# Запуск backend
docker-compose up -d

# Остановка backend
docker-compose down

# Логи backend
docker-compose logs backend -f

# Перезапуск backend
docker-compose restart backend

# Проверка БД
docker-compose exec db psql -U postgres -d timesheet_db

# Применение миграций
docker-compose exec backend alembic upgrade head

# Swagger документация
start http://localhost:8000/docs
```

---

## 🎓 ИСПОЛЬЗОВАНИЕ СКРИПТА

### Базовое использование:

```powershell
.\prepare_widget.ps1
```
Скрипт запросит все необходимые данные интерактивно.

### С параметрами:

```powershell
.\prepare_widget.ps1 `
  -ApiUrl "https://api.mycompany.com/api/v1" `
  -CssUrl "https://cdn.mycompany.com/widget/styles.css" `
  -SupportEmail "support@mycompany.com" `
  -SupportLink "https://mycompany.com/support"
```

### Встраивание CSS:

```powershell
.\prepare_widget.ps1 -ApiUrl "https://api.mycompany.com/api/v1"
# При запросе CSS URL нажмите Enter (CSS встроится в script.js)
```

---

## ✨ ГОТОВО!

После выполнения всех шагов виджет будет работать в вашем amoCRM!

**Что дальше:**
1. Протестируйте все функции
2. Соберите обратную связь от команды
3. Мониторьте логи backend
4. При необходимости оптимизируйте производительность

**Нужна помощь?**
- Проверьте AMOCRM_WIDGET_TESTING_GUIDE.md
- Проверьте логи: `docker-compose logs backend -f`
- Проверьте консоль браузера (F12)

---

## 📞 ПОДДЕРЖКА

### Проверка статуса системы:

```bash
# Все ли работает?
docker-compose ps
curl http://localhost:8000/docs
docker-compose exec db psql -U postgres -d timesheet_db -c "SELECT COUNT(*) FROM work_sessions;"
```

### Если ничего не помогло:

1. Остановите всё: `docker-compose down`
2. Удалите volume: `docker-compose down -v`
3. Пересоздайте: `docker-compose up -d`
4. Примените миграции: `docker-compose exec backend alembic upgrade head`
5. Запустите скрипт: `.\prepare_widget.ps1`

---

**Время полной установки:** ~30 минут  
**Время переустановки:** ~5 минут  
**Успехов с запуском! 🚀**

---

*Создано: 30 июля 2026*  
*Версия: 1.0.0*  
*Проект: Timesheet IL Widget*
