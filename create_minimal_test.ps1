# Create minimal test widget archive

Write-Host "Creating minimal test widget..." -ForegroundColor Cyan
Write-Host ""

# Check files
$files = @(
    "widget_minimal\manifest.json",
    "widget_minimal\script.js",
    "widget_minimal\i18n\ru.json",
    "widget_minimal\images\tour_ru.png"
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
Write-Host "Creating minimal test archive..." -ForegroundColor Green

# Remove old archive
if (Test-Path "widget_minimal_test.zip") {
    Remove-Item "widget_minimal_test.zip" -Force
}

# Create archive
Push-Location widget_minimal
Compress-Archive -Path "manifest.json","script.js","i18n","images" -DestinationPath "..\widget_minimal_test.zip" -Force
Pop-Location

if (Test-Path "widget_minimal_test.zip") {
    $size = (Get-Item "widget_minimal_test.zip").Length / 1KB
    Write-Host ""
    Write-Host "SUCCESS!" -ForegroundColor Green
    Write-Host "File: widget_minimal_test.zip" -ForegroundColor White
    Write-Host "Size: $([math]::Round($size, 2)) KB" -ForegroundColor White
    Write-Host ""
    Write-Host "This is a MINIMAL test widget with:" -ForegroundColor Yellow
    Write-Host "  - Basic manifest.json" -ForegroundColor White
    Write-Host "  - Empty script.js (only callbacks)" -ForegroundColor White
    Write-Host "  - Minimal i18n/ru.json" -ForegroundColor White
    Write-Host "  - One tour image" -ForegroundColor White
    Write-Host ""
    Write-Host "Try uploading widget_minimal_test.zip to amoCRM" -ForegroundColor Yellow
    Write-Host "If it works - add features one by one from main widget" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to create archive" -ForegroundColor Red
    Write-Host ""
}

pause
