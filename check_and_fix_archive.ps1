# Check and fix widget archive

Write-Host "Checking widget files..." -ForegroundColor Cyan

# Check if files exist
$files = @(
    "widget\manifest.json",
    "widget\script.js",
    "widget\i18n\ru.json",
    "widget\i18n\en.json",
    "widget\images\logo.png",
    "widget\images\icon.png",
    "widget\images\tour_ru.png",
    "widget\images\tour_en.png"
)

$allExist = $true
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "[OK] $file" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] $file" -ForegroundColor Red
        $allExist = $false
    }
}

if (-not $allExist) {
    Write-Host ""
    Write-Host "ERROR: Some files are missing!" -ForegroundColor Red
    pause
    exit
}

Write-Host ""
Write-Host "All files found! Creating archive..." -ForegroundColor Green
Write-Host ""

# Remove old archive
if (Test-Path "widget.zip") {
    Remove-Item "widget.zip" -Force
}

# Create archive with correct structure
Push-Location widget
Compress-Archive -Path "manifest.json","script.js","i18n","images" -DestinationPath "..\widget.zip" -Force
Pop-Location

if (Test-Path "widget.zip") {
    $size = (Get-Item "widget.zip").Length / 1KB
    Write-Host ""
    Write-Host "SUCCESS! Archive created: widget.zip" -ForegroundColor Green
    Write-Host "Size: $([math]::Round($size, 2)) KB" -ForegroundColor White
    Write-Host ""
    Write-Host "Now upload widget.zip to amoCRM!" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to create archive" -ForegroundColor Red
    Write-Host ""
}

pause
