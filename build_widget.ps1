# Simple Widget Builder for amoCRM
# Version: 1.0.0

param(
    [string]$ApiUrl = "http://localhost:8000/api/v1",
    [string]$CssUrl = "",
    [string]$SupportEmail = "support@example.com",
    [string]$SupportLink = "https://example.com/support"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Widget Builder for amoCRM" -ForegroundColor Cyan
Write-Host "  Timesheet IL v1.0.0" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check files
Write-Host "Step 1: Checking files..." -ForegroundColor Cyan

$requiredFiles = @(
    "widget/manifest.json",
    "widget/script.js",
    "widget/styles.css",
    "widget/i18n/ru.json",
    "widget/i18n/en.json"
)

$allExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  OK: $file" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $file" -ForegroundColor Red
        $allExist = $false
    }
}

if (-not $allExist) {
    Write-Host ""
    Write-Host "ERROR: Required files missing!" -ForegroundColor Red
    exit 1
}

# Step 2: Check images
Write-Host ""
Write-Host "Step 2: Checking images..." -ForegroundColor Cyan

if (Test-Path "widget/images/logo.png") {
    Write-Host "  OK: logo.png" -ForegroundColor Green
} else {
    Write-Host "  WARNING: logo.png not found" -ForegroundColor Yellow
}

if (Test-Path "widget/images/icon.png") {
    Write-Host "  OK: icon.png" -ForegroundColor Green
} else {
    Write-Host "  WARNING: icon.png not found" -ForegroundColor Yellow
}

# Step 3: Update script.js
Write-Host ""
Write-Host "Step 3: Updating script.js..." -ForegroundColor Cyan

$scriptPath = "widget/script.js"
$scriptContent = Get-Content $scriptPath -Raw -Encoding UTF8

# Update API URL
$scriptContent = $scriptContent -replace "apiBaseUrl: '.*?'", "apiBaseUrl: '$ApiUrl'"
Write-Host "  API URL set to: $ApiUrl" -ForegroundColor Green

# Handle CSS
if ($CssUrl -eq "") {
    Write-Host "  CSS will be embedded in script.js" -ForegroundColor Yellow
    $stylesContent = Get-Content "widget/styles.css" -Raw -Encoding UTF8
    $stylesContent = $stylesContent -replace "'", "\'"
    
    $cssLoadCode = @"
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
    
    $scriptContent = $scriptContent -replace "(?s)// Load CSS.*?CustomWidget\.prototype\.loadCSS = function\(\).*?\};", $cssLoadCode
} else {
    $scriptContent = $scriptContent -replace "var cssUrl = '.*?';", "var cssUrl = '$CssUrl';"
    Write-Host "  CSS URL set to: $CssUrl" -ForegroundColor Green
}

Set-Content -Path $scriptPath -Value $scriptContent -Encoding UTF8
Write-Host "  script.js updated" -ForegroundColor Green

# Step 4: Update manifest.json
Write-Host ""
Write-Host "Step 4: Updating manifest.json..." -ForegroundColor Cyan

$manifestPath = "widget/manifest.json"
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

$manifest.widget.support.email = $SupportEmail
$manifest.widget.support.link = $SupportLink

$manifest | ConvertTo-Json -Depth 10 | Set-Content $manifestPath -Encoding UTF8
Write-Host "  Email: $SupportEmail" -ForegroundColor Green
Write-Host "  Support: $SupportLink" -ForegroundColor Green

# Step 5: Create ZIP
Write-Host ""
Write-Host "Step 5: Creating ZIP archive..." -ForegroundColor Cyan

$zipPath = "timesheet_il_widget.zip"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Host "  Old archive removed" -ForegroundColor Yellow
}

$tempDir = "temp_widget_build"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy files
Copy-Item "widget/manifest.json" "$tempDir/" -Force
Copy-Item "widget/script.js" "$tempDir/" -Force
Copy-Item "widget/styles.css" "$tempDir/" -Force
Copy-Item "widget/i18n" "$tempDir/" -Recurse -Force

if (Test-Path "widget/images") {
    Copy-Item "widget/images" "$tempDir/" -Recurse -Force
}

# Create archive
Compress-Archive -Path "$tempDir/*" -DestinationPath $zipPath -Force

# Cleanup
Remove-Item $tempDir -Recurse -Force

$zipSize = (Get-Item $zipPath).Length
$zipSizeKB = [math]::Round($zipSize / 1KB, 2)

if ($zipSize -gt 10KB) {
    Write-Host "  Archive created: $zipPath ($zipSizeKB KB)" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Archive too small ($zipSizeKB KB)" -ForegroundColor Red
}

# Final info
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  WIDGET READY FOR INSTALLATION" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Archive: $zipPath" -ForegroundColor Cyan
Write-Host "Size: $zipSizeKB KB" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open amoCRM -> Settings -> Integrations -> Widgets" -ForegroundColor White
Write-Host "  2. Click 'Add widget' or 'Upload custom widget'" -ForegroundColor White
Write-Host "  3. Select file: $zipPath" -ForegroundColor White
Write-Host "  4. Enable widget and select sections" -ForegroundColor White
Write-Host "  5. Save settings" -ForegroundColor White
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  API URL: $ApiUrl" -ForegroundColor White
if ($CssUrl -eq "") {
    Write-Host "  CSS: Embedded in script.js" -ForegroundColor White
} else {
    Write-Host "  CSS URL: $CssUrl" -ForegroundColor White
}
Write-Host "  Support Email: $SupportEmail" -ForegroundColor White
Write-Host "  Support Link: $SupportLink" -ForegroundColor White
Write-Host ""
Write-Host "DONE!" -ForegroundColor Green
Write-Host ""
