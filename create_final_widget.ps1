# Encoding: UTF-8 with BOM
# Widget creation script for amoCRM

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " Widget Creation for amoCRM" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Remove old archive if exists
if (Test-Path "timesheet_widget_fixed.zip") {
    Remove-Item "timesheet_widget_fixed.zip"
    Write-Host "Old archive removed" -ForegroundColor Yellow
}

# Go to widget folder
Set-Location widget

# Create archive
Write-Host "Creating archive..." -ForegroundColor Green
Compress-Archive -Path "manifest.json","script.js","i18n","images" -DestinationPath "../timesheet_widget_fixed.zip" -CompressionLevel Optimal -Force

# Go back
Set-Location ..

# Check result
if (Test-Path "timesheet_widget_fixed.zip") {
    $size = (Get-Item "timesheet_widget_fixed.zip").Length
    $sizeKB = [math]::Round($size/1KB, 2)
    
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host " SUCCESS!" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "File: timesheet_widget_fixed.zip" -ForegroundColor White
    Write-Host "Size: $sizeKB KB" -ForegroundColor White
    Write-Host ""
    Write-Host "What was fixed:" -ForegroundColor Cyan
    Write-Host "  * script.js - init method properly closed" -ForegroundColor White
    Write-Host "  * manifest.json - tour with is_tour: true" -ForegroundColor White
    Write-Host "  * manifest.json - version 1.0.1" -ForegroundColor White
    Write-Host "  * i18n files - tour_description added" -ForegroundColor White
    Write-Host "  * Tour images created" -ForegroundColor White
    Write-Host ""
    Write-Host "Upload to amoCRM:" -ForegroundColor Yellow
    Write-Host "  Marketplace -> Integrations -> Upload widget" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "ERROR: Archive creation failed!" -ForegroundColor Red
    Write-Host ""
}

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
