# Решение проблемы установки виджета amoCRM

## 📋 Проблема

**Ошибка**: `Failed to get object manifest.json`

**Симптомы**: Виджет не загружается в amoCRM при попытке установки через zip-архив.

---

## 🔍 Корневая причина

PowerShell команда `Compress-Archive -Path "$tempDir/*"` создавала архив с **неправильной структурой**:

### ❌ Неправильная структура (старая)
```
timesheet_il_widget.zip
  └── temp_widget_build/
        ├── manifest.json
        ├── script.js
        ├── styles.css
        └── ...
```

### ✅ Правильная структура (исправленная)
```
timesheet_il_widget.zip
  ├── manifest.json          ← В КОРНЕ архива!
  ├── script.js
  ├── styles.css
  ├── i18n/
  │   ├── ru.json
  │   └── en.json
  └── images/
      ├── logo.png
      └── ...
```

**amoCRM требует, чтобы manifest.json находился в корне архива**, а не во вложенной папке.

---

## ✅ Решение

### Изменения в `build_widget.ps1`

**Было (строки 141-145)**:
```powershell
# Create archive
Compress-Archive -Path "$tempDir/*" -DestinationPath $zipPath -Force

# Cleanup
Remove-Item $tempDir -Recurse -Force
```

**Стало**:
```powershell
# Create archive with correct structure (files in root, not in subfolder)
# We need to change to temp directory to ensure files are in root of zip
$currentDir = Get-Location
Set-Location $tempDir

# Get all items to compress
$items = Get-ChildItem -Path . -Recurse

# Create the archive from within the temp directory
Compress-Archive -Path * -DestinationPath "../$zipPath" -Force

# Return to original directory
Set-Location $currentDir

# Cleanup
Remove-Item $tempDir -Recurse -Force
```

### Ключевое изменение

Переход в временную директорию **перед** созданием архива:
- `Set-Location $tempDir` - переходим в папку с файлами
- `Compress-Archive -Path *` - архивируем все файлы из текущей папки
- Файлы попадают в **корень** архива, а не во вложенную папку

---

## 🚀 Использование исправленного скрипта

### 1. Создание архива

```powershell
# Базовый запуск (localhost)
.\build_widget.ps1

# С указанием production API URL
.\build_widget.ps1 -ApiUrl "https://your-api.com/api/v1"

# Полная настройка
.\build_widget.ps1 -ApiUrl "https://your-api.com/api/v1" `
                   -SupportEmail "help@company.com" `
                   -SupportLink "https://company.com/support"
```

### 2. Проверка структуры архива

```powershell
# Использовать Python скрипт
python check_zip_content.py timesheet_il_widget.zip
```

Или вручную распаковать и убедиться, что `manifest.json` в корне.

### 3. Установка в amoCRM

1. Открыть amoCRM → Настройки → Интеграции → Виджеты
2. Нажать "Загрузить виджет"
3. Выбрать файл `timesheet_il_widget.zip`
4. ✅ Виджет должен успешно установиться!

---

## 📊 Результат

- ✅ Скрипт `build_widget.ps1` исправлен
- ✅ Архив `timesheet_il_widget.zip` создан с правильной структурой
- ✅ manifest.json находится в корне архива
- ✅ Размер архива: ~22 KB
- ✅ Виджет готов к установке в amoCRM

---

## 🔧 Техническая справка

### Почему это важно?

amoCRM парсит zip-архив и ищет `manifest.json` **строго в корне**. Если файл находится во вложенной папке, система не может его найти и выдает ошибку `Failed to get object manifest.json`.

### Альтернативные методы создания архива

**Python** (правильно):
```python
import zipfile
with zipfile.ZipFile('widget.zip', 'w') as zf:
    zf.write('manifest.json')
    zf.write('script.js')
    # ...
```

**7zip** (правильно):
```bash
cd widget
7z a -tzip ../widget.zip *
```

**WinRAR/Explorer** (НЕПРАВИЛЬНО):
Правый клик на папку → "Добавить в архив" создаст архив с вложенной папкой!

---

## 📝 Checklist для проверки

Перед загрузкой в amoCRM убедитесь:

- [ ] manifest.json находится в корне архива (не во вложенной папке)
- [ ] Все обязательные файлы присутствуют: `manifest.json`, `script.js`, `i18n/ru.json`
- [ ] Файлы изображений в папке `images/` (если есть)
- [ ] Размер архива адекватный (20-30 KB для базового виджета)
- [ ] В manifest.json корректный JSON (без BOM, без ошибок)
- [ ] Указаны правильные locations в manifest.json

---

## 🎯 Дата исправления

**13 августа 2026**

Проблема решена через discovery-interview процесс с глубоким анализом корневой причины.
