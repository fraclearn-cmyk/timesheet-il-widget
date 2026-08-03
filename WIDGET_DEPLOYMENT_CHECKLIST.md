# ✅ ЧЕК-ЛИСТ: ПОДГОТОВКА ВИДЖЕТА К УСТАНОВКЕ В amoCRM

**Дата:** 30 июля 2026  
**Виджет:** Timesheet IL v1.0.0

---

## 📋 БЫСТРЫЙ ЧЕК-ЛИСТ

### 1️⃣ Подготовка изображений (5 минут)
- [ ] Создана папка `widget/images/`
- [ ] Создан файл `widget/images/logo.png` (200x200px)
- [ ] Создан файл `widget/images/icon.png` (64x64px)

**Помощь:** Можно использовать любой графический редактор или онлайн-генератор логотипов.

---

### 2️⃣ Настройка API URL (2 минуты)

- [ ] Открыт файл `widget/script.js`
- [ ] **Строка 13** - изменен `apiBaseUrl`:
  ```javascript
  // ❌ Было:
  apiBaseUrl: 'http://localhost:8000/api/v1',
  
  // ✅ Должно быть:
  apiBaseUrl: 'https://ВАШ-ДОМЕН.com/api/v1',
  ```

**Примеры:**
- Production: `https://api.mycompany.com/api/v1`
- ngrok: `https://abc123.ngrok.io/api/v1`
- Локальный IP: `http://192.168.1.100:8000/api/v1`

---

### 3️⃣ Настройка CSS URL (1 минута)

- [ ] **Строка 145** в `widget/script.js` - изменен `cssUrl`:
  ```javascript
  // ❌ Было:
  var cssUrl = 'https://example.com/widget/styles.css';
  
  // ✅ Должно быть:
  var cssUrl = 'https://ВАШ-ДОМЕН.com/widget/styles.css';
  ```

**Важно:** CSS файл должен быть доступен по публичному URL.

**Альтернатива:** Если нет возможности разместить CSS, можно встроить стили в script.js (см. инструкцию ниже).

---

### 4️⃣ Обновление manifest.json (2 минуты)

- [ ] Открыт файл `widget/manifest.json`
- [ ] **Строка 12** - обновлена ссылка поддержки:
  ```json
  "link": "https://ваш-сайт.com/support"
  ```
- [ ] **Строка 13** - обновлен email:
  ```json
  "email": "support@ваш-email.com"
  ```

---

### 5️⃣ Backend готов к работе (5 минут)

- [ ] Docker контейнеры запущены:
  ```bash
  docker-compose up -d
  ```
- [ ] Backend доступен: `http://localhost:8000/docs` открывается
- [ ] Миграции применены:
  ```bash
  docker-compose exec backend alembic upgrade head
  ```
- [ ] Backend доступен из интернета (через ngrok или на сервере)

**Для ngrok:**
```bash
ngrok http 8000
# Скопируйте URL: https://abc123.ngrok.io
```

---

### 6️⃣ CORS настроен (2 минуты)

- [ ] Открыт файл `backend/app/main.py`
- [ ] В CORS добавлены домены amoCRM:
  ```python
  allow_origins=[
      "https://*.amocrm.ru",
      "https://*.amocrm.com",
      "http://localhost:3000",
  ]
  ```
- [ ] Backend перезапущен:
  ```bash
  docker-compose restart backend
  ```

---

### 7️⃣ Создание ZIP архива (1 минута)

- [ ] Выполнена команда (из папки проекта):
  ```powershell
  cd widget
  Compress-Archive -Force -Path manifest.json,script.js,styles.css,i18n,images -DestinationPath ..\timesheet_il_widget.zip
  ```
- [ ] Файл `timesheet_il_widget.zip` создан в корне проекта

**Проверка архива:**
```
timesheet_il_widget.zip
├── manifest.json          ✅
├── script.js              ✅
├── styles.css             ✅
├── i18n/
│   ├── ru.json           ✅
│   └── en.json           ✅
└── images/
    ├── logo.png          ✅
    └── icon.png          ✅
```

---

### 8️⃣ Установка в amoCRM (5 минут)

- [ ] Открыт amoCRM → Настройки → Интеграции → Виджеты
- [ ] Нажата кнопка "Добавить виджет" или "Загрузить свой виджет"
- [ ] Выбран файл `timesheet_il_widget.zip`
- [ ] Загрузка завершена успешно
- [ ] Виджет включен (тумблер "Вкл")
- [ ] Выбраны разделы для отображения:
  - [ ] Карточка лида
  - [ ] Карточка контакта
  - [ ] Карточка компании
  - [ ] Карточка задачи
  - [ ] Настройки (опционально)
- [ ] Настройки сохранены

---

### 9️⃣ Тестирование (10 минут)

- [ ] Открыта любая карточка в amoCRM
- [ ] Виджет "⏱️ Рабочее время" отображается на боковой панели
- [ ] Нажата кнопка "▶️ Начать рабочий день"
- [ ] Статус изменился на "✅ Работаю"
- [ ] Таймер работает (обновляется каждую секунду)
- [ ] Кнопка "⏸️ Перерыв" работает
- [ ] Кнопка "▶️ Продолжить работу" работает
- [ ] Кнопка "⏹️ Завершить день" работает
- [ ] Нет ошибок в консоли браузера (F12)
- [ ] Данные сохраняются в БД

**Проверка БД:**
```bash
docker-compose exec db psql -U postgres -d timesheet_db -c "SELECT COUNT(*) FROM work_sessions;"
```

---

## 🚀 БЫСТРЫЙ СТАРТ (Все команды подряд)

### Вариант 1: С ngrok (для локального тестирования)

```bash
# 1. Запустить backend
cd d:\табель
docker-compose up -d

# 2. Применить миграции
docker-compose exec backend alembic upgrade head

# 3. Запустить ngrok (в новом окне терминала)
ngrok http 8000
# Скопируйте URL, например: https://abc123.ngrok.io

# 4. Обновить URL в widget/script.js (строка 13 и 145)
# ВРУЧНУЮ: замените localhost:8000 на ngrok URL

# 5. Создать архив
cd widget
Compress-Archive -Force -Path manifest.json,script.js,styles.css,i18n,images -DestinationPath ..\timesheet_il_widget.zip

# 6. Загрузить в amoCRM
# ВРУЧНУЮ: через интерфейс amoCRM
```

### Вариант 2: С production сервером

```bash
# 1. Настроить API URL в widget/script.js
# ВРУЧНУЮ: заменить на https://api.your-domain.com/api/v1

# 2. Создать архив
cd d:\табель\widget
Compress-Archive -Force -Path manifest.json,script.js,styles.css,i18n,images -DestinationPath ..\timesheet_il_widget.zip

# 3. Загрузить в amoCRM
# ВРУЧНУЮ: через интерфейс amoCRM
```

---

## ⚠️ ВАЖНЫЕ МОМЕНТЫ

### ❗ Обязательные изменения перед созданием архива:

1. **API URL** (script.js строка 13) - должен быть публичным
2. **CSS URL** (script.js строка 145) - должен быть публичным
3. **Изображения** (widget/images/) - должны существовать
4. **Backend** - должен быть доступен из интернета
5. **CORS** - должен разрешать домены *.amocrm.ru

### 🔧 Если нет публичного CSS URL:

Встройте стили напрямую в `script.js`:

```javascript
// В начале файла script.js добавьте:
CustomWidget.prototype.loadCSS = function() {
    if ($('#timesheet-inline-styles').length) return;
    
    var styles = `/* Вставьте сюда содержимое styles.css */`;
    
    $('<style>')
        .attr('id', 'timesheet-inline-styles')
        .html(styles)
        .appendTo('head');
};
```

---

## 🐛 Решение типичных проблем

### Проблема: "Виджет не отображается"
**Решение:**
1. Проверьте, что виджет включен в настройках amoCRM
2. Очистите кэш браузера (Ctrl+Shift+Delete)
3. Проверьте консоль браузера (F12) на ошибки

### Проблема: "CORS error"
**Решение:**
```bash
# Добавьте в backend/app/main.py:
allow_origins=["https://*.amocrm.ru", "https://*.amocrm.com"]

# Перезапустите backend:
docker-compose restart backend
```

### Проблема: "API не доступен"
**Решение:**
1. Проверьте: `docker-compose ps` (должны быть запущены backend и db)
2. Проверьте: `curl http://localhost:8000/docs`
3. Если используете ngrok, обновите URL в script.js

### Проблема: "Данные не сохраняются"
**Решение:**
```bash
# Проверьте миграции:
docker-compose exec backend alembic current
docker-compose exec backend alembic upgrade head

# Проверьте логи:
docker-compose logs backend --tail=50
```

---

## 📊 ПРОВЕРКА ГОТОВНОСТИ

Перед установкой в amoCRM проверьте:

✅ **Backend:**
- [ ] `docker-compose ps` - все контейнеры Running
- [ ] `http://localhost:8000/docs` - открывается Swagger
- [ ] `http://YOUR-PUBLIC-URL/docs` - доступен из интернета

✅ **Файлы виджета:**
- [ ] `widget/manifest.json` - обновлен (support, email)
- [ ] `widget/script.js` - обновлен (apiBaseUrl, cssUrl)
- [ ] `widget/images/logo.png` - существует
- [ ] `widget/images/icon.png` - существует

✅ **Архив:**
- [ ] `timesheet_il_widget.zip` - создан
- [ ] Размер архива > 10 KB (не пустой)
- [ ] Все файлы в корне архива (не в подпапке)

---

## ✨ ГОТОВО!

После выполнения всех пунктов чек-листа виджет готов к установке в amoCRM!

**Время выполнения:** ~30 минут (первый раз)

**Следующий раз:** ~5 минут (если backend уже настроен)

---

## 📞 НУЖНА ПОМОЩЬ?

Подробная инструкция: **AMOCRM_WIDGET_TESTING_GUIDE.md**

---

*Создано: 30 июля 2026*  
*Версия: 1.0.0*  
*Проект: Timesheet IL Widget*
