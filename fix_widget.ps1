# Script to fix widget according to specifications

param(
    [string]$WidgetPath = "d:\табель\widget"
)

# Function to remove UTF-8 BOM
function Remove-UTF8BOM {
    param([string]$FilePath)
    
    $content = [System.IO.File]::ReadAllBytes($FilePath)
    
    # Check for UTF-8 BOM (EF BB BF)
    if ($content.Length -ge 3 -and $content[0] -eq 0xEF -and $content[1] -eq 0xBB -and $content[2] -eq 0xBF) {
        Write-Host "Removing BOM from: $FilePath"
        # Remove BOM bytes and rewrite
        $contentWithoutBOM = $content[3..($content.Length - 1)]
        [System.IO.File]::WriteAllBytes($FilePath, $contentWithoutBOM)
        return $true
    }
    return $false
}

# Function to write UTF-8 without BOM
function Set-UTF8Content {
    param(
        [string]$Path,
        [string]$Value
    )
    
    $utf8NoBOM = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Value, $utf8NoBOM)
}

Write-Host "=== Starting Widget Fixes ===" -ForegroundColor Green

# 1. Remove BOM from text files
Write-Host "`n1. Removing UTF-8 BOM from files..." -ForegroundColor Cyan
$textFiles = @(
    "$WidgetPath\manifest.json",
    "$WidgetPath\script.js",
    "$WidgetPath\styles.css",
    "$WidgetPath\i18n\ru.json",
    "$WidgetPath\i18n\en.json"
)

foreach ($file in $textFiles) {
    if (Test-Path $file) {
        Remove-UTF8BOM $file
    }
}

# 2. Update manifest.json
Write-Host "`n2. Updating manifest.json..." -ForegroundColor Cyan
$manifestPath = "$WidgetPath\manifest.json"
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json

# Fix locations
$manifest.locations = @("advanced_settings")

# Remove scopes (not supported)
if ($manifest.PSObject.Properties['scopes']) {
    $manifest.PSObject.Properties.Remove('scopes')
}

# Add advanced settings
$manifest.advanced = @{
    title = "advanced.title"
}

# Convert back to JSON and write without BOM
$jsonContent = $manifest | ConvertTo-Json -Depth 10
Set-UTF8Content $manifestPath $jsonContent
Write-Host "OK: manifest.json updated" -ForegroundColor Green

# 3. Update i18n/ru.json
Write-Host "`n3. Updating i18n/ru.json..." -ForegroundColor Cyan
$ruPath = "$WidgetPath\i18n\ru.json"
$ru = Get-Content $ruPath -Raw | ConvertFrom-Json

# Add advanced translations
if (-not $ru.PSObject.Properties['advanced']) {
    $ru | Add-Member -NotePropertyName 'advanced' -NotePropertyValue @{}
}
$ru.advanced.title = "Настройки табеля"

$jsonContent = $ru | ConvertTo-Json -Depth 10
Set-UTF8Content $ruPath $jsonContent
Write-Host "OK: i18n/ru.json updated" -ForegroundColor Green

# 4. Update i18n/en.json
Write-Host "`n4. Updating i18n/en.json..." -ForegroundColor Cyan
$enPath = "$WidgetPath\i18n\en.json"
$en = Get-Content $enPath -Raw | ConvertFrom-Json

# Add advanced translations
if (-not $en.PSObject.Properties['advanced']) {
    $en | Add-Member -NotePropertyName 'advanced' -NotePropertyValue @{}
}
$en.advanced.title = "Timesheet Settings"

$jsonContent = $en | ConvertTo-Json -Depth 10
Set-UTF8Content $enPath $jsonContent
Write-Host "OK: i18n/en.json updated" -ForegroundColor Green

# 5. Create logo.png if not exists
Write-Host "`n5. Creating images/logo.png..." -ForegroundColor Cyan
$imagesDir = "$WidgetPath\images"
if (-not (Test-Path $imagesDir)) {
    New-Item -ItemType Directory -Path $imagesDir | Out-Null
    Write-Host "Created images directory"
}

$logoPng = "$imagesDir\logo.png"
if (-not (Test-Path $logoPng)) {
    # Create a minimal valid PNG (1x1 transparent)
    $pngBytes = @(
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, 
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41, 
        0x54, 0x78, 0x9C, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 
        0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D, 
        0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 
        0x44, 0xAE, 0x42, 0x60, 0x82
    )
    
    [System.IO.File]::WriteAllBytes($logoPng, $pngBytes)
    Write-Host "OK: images/logo.png created (1x1 transparent PNG)" -ForegroundColor Green
}
else {
    Write-Host "OK: images/logo.png already exists" -ForegroundColor Green
}

# 6. Add advancedSettings callback to script.js
Write-Host "`n6. Adding advancedSettings callback to script.js..." -ForegroundColor Cyan
$scriptPath = "$WidgetPath\script.js"
$scriptContent = [System.IO.File]::ReadAllText($scriptPath)

# Check if advancedSettings callback exists
if ($scriptContent -notmatch 'advancedSettings') {
    # Find the settings callback and add advancedSettings after it
    if ($scriptContent -match 'settings:\s*function\s*\(\)\s*\{[^}]*return\s+true;\s*\}') {
        $callback = @'
advancedSettings: function() {
                console.log('Advanced settings opened');
                return true;
            },
'@
        $scriptContent = $scriptContent -replace '(settings:\s*function\s*\(\)\s*\{[^}]*return\s+true;\s*\})', ('$1,' + [Environment]::NewLine + '            ' + $callback)
        Set-UTF8Content $scriptPath $scriptContent
        Write-Host "OK: advancedSettings callback added" -ForegroundColor Green
    }
}
else {
    Write-Host "OK: advancedSettings callback already exists" -ForegroundColor Green
}

# 7. Verify changes
Write-Host "`n7. Verifying changes..." -ForegroundColor Cyan
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
Write-Host "  - locations: $($manifest.locations -join ', ')"
Write-Host "  - advanced.title: $($manifest.advanced.title)"
Write-Host "  - scopes removed: $(-not $manifest.PSObject.Properties['scopes'])"
Write-Host "  - logo.png exists: $(Test-Path $logoPng)"

Write-Host "`n=== Widget Fixes Complete ===" -ForegroundColor Green
