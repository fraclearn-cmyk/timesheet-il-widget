# Widget Builder for amoCRM Timesheet IL v3.0.2
# Creates ZIP package with UTF-8 encoding (no BOM)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  amoCRM Widget Builder" -ForegroundColor Cyan
Write-Host "  Timesheet IL v3.0.2" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check files
Write-Host "Step 1: Checking required files..." -ForegroundColor Cyan

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
    }
    else {
        Write-Host "  MISSING: $file" -ForegroundColor Red
        $allExist = $false
    }
}

if (-not $allExist) {
    Write-Host ""
    Write-Host "ERROR: Required files missing!" -ForegroundColor Red
    exit 1
}

# Step 2: Check images/logo.png
Write-Host ""
Write-Host "Step 2: Checking images..." -ForegroundColor Cyan

if (Test-Path "widget/images/logo.png") {
    Write-Host "  OK: logo.png" -ForegroundColor Green
}
else {
    Write-Host "  ERROR: logo.png required" -ForegroundColor Red
    exit 1
}

# Step 3: Remove BOM from text files
Write-Host ""
Write-Host "Step 3: Preparing files (removing BOM)..." -ForegroundColor Cyan

$textFiles = @(
    "widget/manifest.json",
    "widget/script.js",
    "widget/styles.css",
    "widget/i18n/ru.json",
    "widget/i18n/en.json"
)

foreach ($file in $textFiles) {
    if (Test-Path $file) {
        $content = [System.IO.File]::ReadAllBytes($file)
        if ($content.Length -ge 3 -and $content[0] -eq 0xEF -and $content[1] -eq 0xBB -and $content[2] -eq 0xBF) {
            [System.IO.File]::WriteAllBytes($file, $content[3..($content.Length - 1)])
            Write-Host "  Removed BOM: $file" -ForegroundColor Green
        }
    }
}

# Step 4: Create ZIP
Write-Host ""
Write-Host "Step 4: Creating ZIP archive..." -ForegroundColor Cyan

$zipPath = "timesheet_il_widget.zip"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Host "  Old archive removed"
}

$tempDir = "temp_widget_build"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy only required files (exclude demo.html)
Copy-Item "widget/manifest.json" "$tempDir/" -Force
Copy-Item "widget/script.js" "$tempDir/" -Force
Copy-Item "widget/styles.css" "$tempDir/" -Force
Copy-Item "widget/i18n" "$tempDir/" -Recurse -Force

if (Test-Path "widget/images") {
    Copy-Item "widget/images" "$tempDir/" -Recurse -Force
}

Write-Host "  Files prepared"

# Create archive from temp directory
$currentDir = Get-Location
Set-Location $tempDir

Compress-Archive -Path * -DestinationPath "../$zipPath" -Force
Write-Host "  Archive created: $zipPath" -ForegroundColor Green

Set-Location $currentDir

# Cleanup
Remove-Item $tempDir -Recurse -Force

$zipSize = (Get-Item $zipPath).Length
$zipSizeKB = [math]::Round($zipSize / 1KB, 2)

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  WIDGET BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Archive: $zipPath ($zipSizeKB KB)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: Run validate_widget_zip.py to verify" -ForegroundColor Cyan
Write-Host ""
