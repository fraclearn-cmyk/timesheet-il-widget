# 📦 ПОШАГОВАЯ ИНСТРУКЦИЯ: Сборка и Проверка Widget.zip для amoCRM

**Дата:** 11.08.2026, 17:43  
**Цель:** Собрать и проверить виджет для загрузки в приватные виджеты amoCRM

---

## 📋 СОДЕРЖАНИЕ

1. [Структура виджета](#структура-виджета)
2. [Требования amoCRM](#требования-amocrm)
3. [Шаг 1: Проверка файлов](#шаг-1-проверка-файлов)
4. [Шаг 2: Валидация manifest.json](#шаг-2-валидация-manifestjson)
5. [Шаг 3: Создание архива](#шаг-3-создание-архива)
6. [Шаг 4: Проверка архива](#шаг-4-проверка-архива)
7. [Шаг 5: Загрузка в amoCRM](#шаг-5-загрузка-в-amocrm)
8. [Шаг 6: Тестирование](#шаг-6-тестирование)
9. [Troubleshooting](#troubleshooting)

---

## 🗂️ СТРУКТУРА ВИДЖЕТА

### Текущая структура `widget/`:

```
widget/
├── manifest.json          # Манифест виджета (ОБЯЗАТЕЛЬНО)
├── script.js             # Основной код виджета (ОБЯЗАТЕЛЬНО)
├── styles.css            # Стили (опционально)
├── demo.html             # Демо (не включать в zip)
├── i18n/                 # Локализации
│   ├── en.json
│   └── ru.json
└── images/               # Иконки и лого
    ├── icon.png          # 16x16 или 32x32
    ├── logo.png          # Основной логотип
    ├── logo_main.png     # 389x270
    ├── logo_medium.png   # 200x140
    ├── logo_small.png    # 128x128
    ├── logo_min.png      # 48x48
    ├── tour_ru.png       # Туры
    └── tour_en.png
```

---

## ⚠️ ТРЕБОВАНИЯ amoCRM

### Критичные требования:

1. **Кодировка:** UTF-8 БЕЗ BOM
2. **Формат:** ZIP архив
3. **Структура:** Файлы в корне архива (НЕ в папке)
4. **Обязательные файлы:**
   - `manifest.json`
   - `script.js`
5. **Размер файлов:**
   - Каждый файл < 1 МБ
   - Общий размер < 5 МБ
6. **Иконки:**
   - icon.png (16x16 или 32x32)
   - logo.png (любой размер)

### Частые ошибки:

❌ Файлы внутри папки в zip  
❌ BOM в UTF-8 файлах  
❌ Неправильный manifest.json  
❌ Отсутствие обязательных полей  
❌ Неправильные размеры изображений  

---

## ✅ ШАГ 1: ПРОВЕРКА ФАЙЛОВ

### 1.1. Проверить наличие обязательных файлов

```powershell
# Запустить из корня проекта d:\табель
cd widget
dir

# Должны быть:
# - manifest.json
# - script.js
# - i18n/ (папка)
# - images/ (папка)
```

### 1.2. Проверить кодировку (UTF-8 без BOM)

Файлы manifest.json и script.js должны быть в UTF-8 БЕЗ BOM.

**В VS Code:** Смотрите нижний правый угол - должно быть "UTF-8" (не "UTF-8 with BOM")

**Если есть BOM, запустить:**
```powershell
python remove_bom.py
```

---

## ✅ ШАГ 2: ВАЛИДАЦИЯ MANIFEST.JSON

### 2.1. Открыть manifest.json

```powershell
code manifest.json
```

### 2.2. Проверить обязательные поля:

```json
{
  "widget": {
    "name": "widget.timesheet_il",
    "description": "Учёт рабочего времени",
    "short_description": "Табель учёта времени",
    "version": "1.0.0",
    "interface_version": 2,
    "init_once": false,
    "locale": ["ru", "en"],
    "installation": true,
    "support": {
      "link": "mailto:support@example.com",
      "email": "support@example.com"
    }
  },
  "locations": [
    "card-lead",
    "card-contact",
    "card-company"
  ],
  "settings": {
    "login": {
      "name": "settings.login",
      "type": "text"
    },
    "api_key": {
      "name": "settings.api_key",
      "type": "pass"
    }
  }
}
```

### 2.3. Проверить критичные поля:

- ✅ `widget.name` - уникальное имя (только латиница, цифры, подчеркивание)
- ✅ `widget.version` - версия (формат X.Y.Z)
- ✅ `widget.interface_version` - должно быть 2
- ✅ `widget.locale` - массив языков ["ru", "en"]
- ✅ `locations` - где показывать виджет

---

## ✅ ШАГ 3: СОЗДАНИЕ АРХИВА

### Метод 1: PowerShell Script (РЕКОМЕНДУЕТСЯ)

```powershell
# Из корня проекта d:\табель
.\build_widget.ps1
```

Этот скрипт:
1. Проверит наличие всех файлов
2. Удалит старый widget.zip
3. Создаст новый widget.zip
4. Проверит структуру архива

### Метод 2: Python Script

```powershell
python create_widget_archive.py
```

### Метод 3: Вручную через PowerShell

```powershell
# Перейти в папку widget
cd widget

# Создать архив (файлы в КОРНЕ архива, не в папке!)
Compress-Archive -Path manifest.json,script.js,styles.css,i18n,images -DestinationPath ..\widget.zip -Force

# Вернуться назад
cd ..
```

### Метод 4: 7-Zip (если установлен)

```powershell
cd widget
7z a -tzip ..\widget.zip manifest.json script.js styles.css i18n\* images\* -mx9
cd ..
```

---

## ✅ ШАГ 4: ПРОВЕРКА АРХИВА

### 4.1. Проверить размер

```powershell
Get-Item widget.zip | Select-Object Name, Length

# Должно быть < 5 МБ
```

### 4.2. Проверить содержимое

```powershell
# Метод 1: PowerShell
Expand-Archive -Path widget.zip -DestinationPath temp_check -Force
dir temp_check
Remove-Item temp_check -Recurse -Force

# Метод 2: Python script
python check_zip_content.py
```

### 4.3. Проверить структуру (КРИТИЧНО!)

**Правильная структура:**
```
widget.zip
├── manifest.json     ← В КОРНЕ!
├── script.js         ← В КОРНЕ!
├── styles.css        ← В КОРНЕ!
├── i18n/
│   ├── en.json
│   └── ru.json
└── images/
    ├── icon.png
    └── ...
```

**НЕПРАВИЛЬНО:**
```
widget.zip
└── widget/           ← ❌ НЕ ДОЛЖНО БЫТЬ ПАПКИ!
    ├── manifest.json
    └── ...
```

---

## ✅ ШАГ 5: ЗАГРУЗКА В amoCRM

### 5.1. Открыть настройки amoCRM

1. Перейти: **Настройки** → **Интеграции**
2. Выбрать: **Виджеты и API**
3. Нажать: **Загрузить виджет**

### 5.2. Загрузить widget.zip

1. Нажать **"Выбрать файл"**
2. Выбрать созданный `widget.zip`
3. Нажать **"Загрузить"**

### 5.3. Возможные ошибки при загрузке:

**Ошибка: "Некорректная структура архива"**
- Проверьте, что файлы в КОРНЕ архива, а не в папке
- Пересоздайте архив по инструкции

**Ошибка: "Некорректный manifest.json"**
- Проверьте JSON валидность на jsonlint.com
- Убедитесь в наличии всех обязательных полей

**Ошибка: "Кодировка файла"**
- Удалите BOM из UTF-8 файлов
- Запустите `remove_bom.py`

**Ошибка: "Файл слишком большой"**
- Проверьте размер каждого файла
- Оптимизируйте изображения

---

## ✅ ШАГ 6: ТЕСТИРОВАНИЕ

### 6.1. Установить виджет

После успешной загрузки:

1. Найти виджет в списке
2. Нажать **"Установить"**
3. Ввести настройки (если требуются)
4. Нажать **"Сохранить"**

### 6.2. Открыть карточку для теста

1. Перейти в Leads/Contacts/Companies
2. Открыть любую карточку
3. Найти виджет в правой панели

### 6.3. Проверить функционал

- ✅ Виджет отображается
- ✅ Кнопки работают
- ✅ API запросы уходят
- ✅ Данные сохраняются
- ✅ Нет ошибок в консоли

### 6.4. Открыть консоль разработчика

**F12** → **Console**

Проверить на ошибки:
- ❌ Красные ошибки
- ⚠️ Желтые предупреждения
- ✅ Должны быть только логи виджета

---

## 🔧 TROUBLESHOOTING

### Проблема 1: "Виджет не загружается"

**Решение:**
```powershell
# 1. Проверить структуру архива
python check_zip_content.py

# 2. Удалить BOM
python remove_bom.py

# 3. Пересоздать архив
.\build_widget.ps1

# 4. Попробовать снова
```

### Проблема 2: "Виджет не отображается"

**Решение:**
1. Проверить `locations` в manifest.json
2. Убедиться, что виджет установлен
3. Проверить права доступа
4. Очистить кэш браузера (Ctrl+Shift+Del)

### Проблема 3: "Ошибки в консоли"

**Решение:**
1. Открыть F12 → Console
2. Найти точную ошибку
3. Проверить script.js
4. Проверить API endpoint (должен быть доступен)

### Проблема 4: "API не отвечает"

**Решение:**
```powershell
# Проверить backend
docker ps

# Должны работать:
# - timesheet_db (postgres)
# - timesheet_backend (api)

# Если нет, запустить:
docker-compose up -d
```

### Проблема 5: "CORS ошибки"

**Решение:**
Backend должен разрешать CORS для amoCRM:
```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production указать точный домен amoCRM
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📝 ЧЕКЛИСТ ПЕРЕД ЗАГРУЗКОЙ

### Файлы:
- [ ] manifest.json существует
- [ ] script.js существует
- [ ] i18n/ru.json существует
- [ ] i18n/en.json существует
- [ ] images/icon.png существует (16x16 или 32x32)
- [ ] images/logo.png существует

### Валидация:
- [ ] manifest.json валиден (JSONLint)
- [ ] Все файлы UTF-8 БЕЗ BOM
- [ ] widget.name уникален
- [ ] widget.version указана
- [ ] locations заданы

### Архив:
- [ ] widget.zip создан
- [ ] Размер < 5 МБ
- [ ] Файлы в КОРНЕ архива
- [ ] Нет папки "widget/" внутри

### Backend:
- [ ] PostgreSQL запущен
- [ ] FastAPI запущен (port 8000)
- [ ] CORS настроен
- [ ] Миграции применены

---

## 🚀 БЫСТРЫЙ СТАРТ

### Все команды одной строкой:

```powershell
# 1. Проверить backend
docker ps

# 2. Собрать виджет
.\build_widget.ps1

# 3. Проверить архив
python check_zip_content.py

# 4. Готово! Файл widget.zip готов к загрузке
```

---

## 📚 ПОЛЕЗНЫЕ ССЫЛКИ

**Документация amoCRM:**
- [Разработка виджетов](https://www.amocrm.ru/developers/content/widgets)
- [Структура манифеста](https://www.amocrm.ru/developers/content/widgets/structure)
- [API виджетов](https://www.amocrm.ru/developers/content/widgets/js-sdk)

**Внутренние документы:**
- `AMOCRM_WIDGET_TESTING_GUIDE.md` - Полная инструкция по тестированию
- `WIDGET_DEPLOYMENT_CHECKLIST.md` - Чеклист развертывания
- `WIDGET_QUICK_START.md` - Быстрый старт

**Скрипты:**
- `build_widget.ps1` - Сборка виджета (PowerShell)
- `create_widget_archive.py` - Сборка (Python)
- `check_zip_content.py` - Проверка архива
- `remove_bom.py` - Удаление BOM

---

## ✅ ФИНАЛЬНАЯ ПРОВЕРКА

Перед загрузкой в amoCRM убедитесь:

1. ✅ Backend работает (docker ps)
2. ✅ widget.zip создан
3. ✅ Архив проверен (check_zip_content.py)
4. ✅ Размер < 5 МБ
5. ✅ Нет BOM в файлах
6. ✅ manifest.json валиден
7. ✅ Структура правильная (файлы в корне)

**Если все ✅ - можно загружать в amoCRM!**

---

**Создано:** 11.08.2026  
**Версия:** 1.0  
**Статус:** Готово к использованию ✅

🎉 **УДАЧИ С ЗАГРУЗКОЙ ВИДЖЕТА!** 🚀
