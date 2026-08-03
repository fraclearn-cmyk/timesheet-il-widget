# Создание изображений-заглушек для виджета
# Это временные изображения для тестирования

Add-Type -AssemblyName System.Drawing

# Функция создания изображения с текстом
function Create-PlaceholderImage {
    param(
        [string]$Path,
        [int]$Width,
        [int]$Height,
        [string]$Text
    )
    
    $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    
    # Фон
    $brush = [System.Drawing.Brushes]::Blue
    $graphics.FillRectangle($brush, 0, 0, $Width, $Height)
    
    # Текст
    $font = New-Object System.Drawing.Font("Arial", [Math]::Max(12, $Width / 10), [System.Drawing.FontStyle]::Bold)
    $textBrush = [System.Drawing.Brushes]::White
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $rect = New-Object System.Drawing.RectangleF(0, 0, $Width, $Height)
    
    $graphics.DrawString($Text, $font, $textBrush, $rect, $format)
    
    # Сохранение
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    
    $graphics.Dispose()
    $bitmap.Dispose()
    
    Write-Host "✅ Создано: $Path" -ForegroundColor Green
}

# Создание изображений
Write-Host "🖼️ Создание изображений-заглушек..." -ForegroundColor Cyan

Create-PlaceholderImage -Path "widget\images\logo.png" -Width 200 -Height 200 -Text "Timesheet IL"
Create-PlaceholderImage -Path "widget\images\icon.png" -Width 64 -Height 64 -Text "TIL"

Write-Host ""
Write-Host "Done! Images created." -ForegroundColor Green
Write-Host "WARNING: These are temporary placeholders. Replace them before production." -ForegroundColor Yellow
