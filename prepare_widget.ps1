# ========================================
# СКРИПТ ПОДГОТОВКИ ВИДЖЕТА ДЛЯ amoCRM
# ========================================
# Версия: 1.0.0
# Дата: 30 июля 2026
# Описание: Автоматизированная подготовка и упаковка виджета Timesheet IL

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "",
    
    [Parameter(Mandatory=$false)]
    [string]$CssUrl = "",
    
    [Parameter(Mandatory=$false)]
    [string]$SupportEmail = "support@example.com",
    
    [Parameter(Mandatory=$false)]
    [string]$SupportLink = "https://example.com/support"
)

# Цвета для вывода
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success { Write-ColorOutput Green $args }
function Write-Error-Message { Write-ColorOutput Red $args }
function Write-Warning-Message { Write-ColorOutput Yellow $args }
function Write-Info { Write-ColorOutput Cyan $args }

# Заголовок
Clear-Host
Write-Info "========================================="
Write-Info "  ПОДГОТОВКА ВИДЖЕТА ДЛЯ amoCRM"
Write-Info "  Timesheet IL v1.0.0"
Write-Info "========================================="
Write-Output ""

# Проверка текущей директории
$currentDir = Get-Location
Write-Info "📁 Текущая директория: $currentDir"

if (-not (Test-Path "widget")) {
    Write-Error-Message "❌ ОШИБКА: Папка 'widget' не найдена!"
    Write-Error-Message "Запустите скрипт из корня проекта (d:\табель)"
    exit 1
}

# ========================================
# ШАГ 1: ПРОВЕРКА СТРУКТУРЫ
# ========================================
Write-Output ""
Write-Info "🔍 Шаг 1: Проверка структуры файлов..."

$requiredFiles = @(
    "widget/manifest.json",
    "widget/script.js",
    "widget/styles.css",
    "widget/i18n/ru.json",
    "widget/i18n/en.json"
)

$allFilesExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Success "  ✅ $file"
    } else {
        Write-Error-Message "  ❌ $file - НЕ НАЙДЕН!"
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Error-Message ""
    Write-Error-Message "❌ Не все обязательные файлы найдены!"
    exit 1
}

# ========================================
# ШАГ 2: ПРОВЕРКА ИЗОБРАЖЕНИЙ
# ========================================
Write-Output ""
Write-Info "🖼️ Шаг 2: Проверка изображений..."

$imagesDir = "widget/images"
$logoPath = "$imagesDir/logo.png"
$iconPath = "$imagesDir/icon.png"

if (-not (Test-Path $imagesDir)) {
    Write-Warning-Message "  ⚠️ Папка 'widget/images' не найдена. Создаю..."
    New-Item -ItemType Directory -Path $imagesDir -Force | Out-Null
}

$imagesOk = $true
if (Test-Path $logoPath) {
    Write-Success "  ✅ logo.png найден"
} else {
    Write-Warning-Message "  ⚠️ logo.png НЕ НАЙДЕН! Требуется создать (200x200px)"
    $imagesOk = $false
}

if (Test-Path $iconPath) {
    Write-Success "  ✅ icon.png найден"
} else {
    Write-Warning-Message "  ⚠️ icon.png НЕ НАЙДЕН! Требуется создать (64x64px)"
    $imagesOk = $false
}

if (-not $imagesOk) {
    Write-Output ""
    $continue = Read-Host "Продолжить без изображений? (y/n)"
    if ($continue -ne "y") {
        Write-Error-Message "Прервано пользователем."
        exit 1
    }
}

# ========================================
# ШАГ 3: ЗАПРОС URL API
# ========================================
Write-Output ""
Write-Info "🌐 Шаг 3: Настройка URL API..."

if ($ApiUrl -eq "") {
    Write-Output ""
    Write-Output "Введите URL вашего API backend:"
    Write-Output "Примеры:"
    Write-Output "  - https://api.mycompany.com/api/v1"
    Write-Output "  - https://abc123.ngrok.io/api/v1"
    Write-Output "  - http://192.168.1.100:8000/api/v1"
    Write-Output ""
    $ApiUrl = Read-Host "API URL"
    
    if ($ApiUrl -eq "") {
        Write-Warning-Message "⚠️ API URL не указан. Используется localhost (только для разработки!)"
        $ApiUrl = "http://localhost:8000/api/v1"
    }
}

Write-Info "  🔗 API URL: $ApiUrl"

# ========================================
# ШАГ 4: ЗАПРОС CSS URL
# ========================================
Write-Output ""
Write-Info "🎨 Шаг 4: Настройка CSS URL..."

if ($CssUrl -eq "") {
    Write-Output ""
    Write-Output "Введите публичный URL для styles.css:"
    Write-Output "Пример: https://cdn.mycompany.com/widget/styles.css"
    Write-Output ""
    Write-Output "Или нажмите Enter для встраивания CSS в script.js"
    Write-Output ""
    $CssUrl = Read-Host "CSS URL (или Enter для встраивания)"
}

if ($CssUrl -eq "") {
    Write-Warning-Message "  ⚠️ CSS будет встроен в script.js"
    $embedCss = $true
} else {
    Write-Info "  🔗 CSS URL: $CssUrl"
    $embedCss = $false
}

# ========================================
# ШАГ 5: ОБНОВЛЕНИЕ SCRIPT.JS
# ========================================
Write-Output ""
Write-Info "📝 Шаг 5: Обновление script.js..."

$scriptPath = "widget/script.js"
$scriptContent = Get-Content $scriptPath -Raw

# Обновление API URL
$scriptContent = $scriptContent -replace "apiBaseUrl: '.*?'", "apiBaseUrl: '$ApiUrl'"
Write-Success "  ✅ API URL обновлен"

# Обновление CSS URL или встраивание
if ($embedCss) {
    # Чтение styles.css
    $stylesContent = Get-Content "widget/styles.css" -Raw
    
    # Создание кода для встраивания CSS
    $cssCode = @"
    // Load CSS
    CustomWidget.prototype.loadCSS = function() {
        if (`$('#timesheet-inline-styles').length) return;
        
        var styles = ``$stylesContent``;
        
        `$('<style>')
            .attr('id', 'timesheet-inline-styles')
            .html(styles)
            .appendTo('head');
    };
"@
    
    # Замена функции loadCSS
    $scriptContent = $scriptContent -replace "(?s)// Load CSS.*?CustomWidget\.prototype\.loadCSS = function\(\) \{.*?\};", $cssCode
    Write-Success "  ✅ CSS встроен в script.js"
} else {
    $scriptContent = $scriptContent -replace "var cssUrl = '.*?';", "var cssUrl = '$CssUrl';"
    Write-Success "  ✅ CSS URL обновлен"
}

# Сохранение изменений
Set-Content -Path $scriptPath -Value $scriptContent -Encoding UTF8
Write-Success "  ✅ script.js сохранен"

# ========================================
# ШАГ 6: ОБНОВЛЕНИЕ MANIFEST.JSON
# ========================================
Write-Output ""
Write-Info "📋 Шаг 6: Обновление manifest.json..."

$manifestPath = "widget/manifest.json"
$manifestContent = Get-Content $manifestPath -Raw | ConvertFrom-Json

# Обновление support информации
$manifestContent.widget.support.email = $SupportEmail
$manifestContent.widget.support.link = $SupportLink

# Сохранение
$manifestContent | ConvertTo-Json -Depth 10 | Set-Content $manifestPath -Encoding UTF8
Write-Success "  ✅ Email: $SupportEmail"
Write-Success "  ✅ Support: $SupportLink"
Write-Success "  ✅ manifest.json сохранен"

# ========================================
# ШАГ 7: ПРОВЕРКА BACKEND
# ========================================
Write-Output ""
Write-Info "🔧 Шаг 7: Проверка backend..."

# Проверка Docker
$dockerRunning = docker ps 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Success "  ✅ Docker работает"
    
    # Проверка контейнеров
    $containers = docker-compose ps -q 2>$null
    if ($containers) {
        Write-Success "  ✅ Docker Compose контейнеры запущены"
    } else {
        Write-Warning-Message "  ⚠️ Docker Compose контейнеры не запущены"
        Write-Output ""
        $startDocker = Read-Host "Запустить docker-compose up -d? (y/n)"
        if ($startDocker -eq "y") {
            docker-compose up -d
            Start-Sleep -Seconds 5
            Write-Success "  ✅ Контейнеры запущены"
        }
    }
} else {
    Write-Warning-Message "  ⚠️ Docker не запущен или не установлен"
}

# ========================================
# ШАГ 8: СОЗДАНИЕ ZIP АРХИВА
# ========================================
Write-Output ""
Write-Info "📦 Шаг 8: Создание ZIP архива..."

$zipPath = "timesheet_il_widget.zip"

# Удаление старого архива
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Info "  🗑️ Старый архив удален"
}

# Создание списка файлов для архива
$filesToZip = @(
    "widget/manifest.json",
    "widget/script.js",
    "widget/styles.css",
    "widget/i18n"
)

# Добавление images только если они существуют
if (Test-Path $imagesDir) {
    if ((Test-Path $logoPath) -or (Test-Path $iconPath)) {
        $filesToZip += "widget/images"
    }
}

# Создание временной директории
$tempDir = "temp_widget_build"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Копирование файлов
foreach ($file in $filesToZip) {
    $destination = $tempDir + "/" + (Split-Path $file -Leaf)
    if (Test-Path $file) {
        Copy-Item $file $destination -Recurse -Force
    }
}

# Создание архива
Compress-Archive -Path "$tempDir/*" -DestinationPath $zipPath -Force

# Очистка
Remove-Item $tempDir -Recurse -Force

# Проверка размера
$zipSize = (Get-Item $zipPath).Length
$zipSizeKB = [math]::Round($zipSize / 1KB, 2)

if ($zipSize -gt 10KB) {
    Write-Success "  ✅ Архив создан: $zipPath ($zipSizeKB KB)"
} else {
    Write-Error-Message "  ❌ Архив слишком маленький ($zipSizeKB KB). Возможно что-то пошло не так!"
}

# ========================================
# ШАГ 9: ФИНАЛЬНАЯ ПРОВЕРКА
# ========================================
Write-Output ""
Write-Info "✅ Шаг 9: Финальная проверка..."

Write-Output ""
Write-Success "╔════════════════════════════════════════╗"
Write-Success "║     ВИДЖЕТ ГОТОВ К УСТАНОВКЕ! ✨       ║"
Write-Success "╚════════════════════════════════════════╝"
Write-Output ""

Write-Info "📦 Файл архива: $zipPath"
Write-Info "📊 Размер: $zipSizeKB KB"
Write-Output ""

Write-Info "📋 Следующие шаги:"
Write-Output "  1. Откройте amoCRM → Настройки → Интеграции → Виджеты"
Write-Output "  2. Нажмите 'Добавить виджет' или 'Загрузить свой виджет'"
Write-Output "  3. Выберите файл: $zipPath"
Write-Output "  4. Включите виджет и выберите разделы для отображения"
Write-Output "  5. Сохраните настройки"
Write-Output ""

Write-Info "🔗 Настроенные URL:"
Write-Output "  API: $ApiUrl"
if ($embedCss) {
    Write-Output "  CSS: Встроен в script.js"
} else {
    Write-Output "  CSS: $CssUrl"
}
Write-Output ""

Write-Info "📞 Поддержка:"
Write-Output "  Email: $SupportEmail"
Write-Output "  Link: $SupportLink"
Write-Output ""

Write-Info "📚 Документация:"
Write-Output "  - AMOCRM_WIDGET_TESTING_GUIDE.md - Подробная инструкция"
Write-Output "  - WIDGET_DEPLOYMENT_CHECKLIST.md - Чек-лист проверки"
Write-Output ""

# Открыть папку с архивом
$openFolder = Read-Host "Открыть папку с архивом? (y/n)"
if ($openFolder -eq "y") {
    explorer.exe .
}

Write-Output ""
Write-Success "✨ Готово! Удачи с установкой! ✨"
Write-Output ""
