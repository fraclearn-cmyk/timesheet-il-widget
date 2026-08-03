# Quick Start Script for Local Testing
# Automatically starts backend and provides instructions for ngrok

param(
    [string]$NgrokPath = "C:\ngrok\ngrok.exe"
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LOCAL TESTING - QUICK START" -ForegroundColor Cyan
Write-Host "  Timesheet IL Widget" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Docker
Write-Host "Step 1: Checking Docker..." -ForegroundColor Cyan
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: Docker is installed" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Docker not found!" -ForegroundColor Red
        Write-Host "  Please install Docker Desktop and try again" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "  ERROR: Docker not found!" -ForegroundColor Red
    exit 1
}

# Step 2: Check if Docker is running
Write-Host ""
Write-Host "Step 2: Checking if Docker is running..." -ForegroundColor Cyan
try {
    docker ps | Out-Null
    Write-Host "  OK: Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Step 3: Stop old containers
Write-Host ""
Write-Host "Step 3: Stopping old containers..." -ForegroundColor Cyan
docker-compose down 2>&1 | Out-Null
Write-Host "  OK: Old containers stopped" -ForegroundColor Green

# Step 4: Start containers
Write-Host ""
Write-Host "Step 4: Starting backend containers..." -ForegroundColor Cyan
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Containers started" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Failed to start containers" -ForegroundColor Red
    exit 1
}

# Step 5: Wait for database
Write-Host ""
Write-Host "Step 5: Waiting for database to start (15 seconds)..." -ForegroundColor Cyan
Start-Sleep -Seconds 15
Write-Host "  OK: Database should be ready" -ForegroundColor Green

# Step 6: Apply migrations
Write-Host ""
Write-Host "Step 6: Applying database migrations..." -ForegroundColor Cyan
$migrationOutput = docker-compose exec -T backend alembic upgrade head 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Migrations applied" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Migration issues (might be already applied)" -ForegroundColor Yellow
}

# Step 7: Check backend status
Write-Host ""
Write-Host "Step 7: Checking backend status..." -ForegroundColor Cyan
Start-Sleep -Seconds 3

$containerStatus = docker-compose ps --format json | ConvertFrom-Json
$backendRunning = $false

foreach ($container in $containerStatus) {
    if ($container.Service -eq "backend" -and $container.State -eq "running") {
        $backendRunning = $true
        break
    }
}

if ($backendRunning) {
    Write-Host "  OK: Backend is running on http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Backend is not running" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check logs:" -ForegroundColor Yellow
    docker-compose logs backend --tail=20
    exit 1
}

# Step 8: Test backend
Write-Host ""
Write-Host "Step 8: Testing backend..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  OK: Backend API is responding" -ForegroundColor Green
    }
} catch {
    Write-Host "  WARNING: Backend might still be starting..." -ForegroundColor Yellow
}

# Step 9: Check ngrok
Write-Host ""
Write-Host "Step 9: Checking ngrok..." -ForegroundColor Cyan

if (Test-Path $NgrokPath) {
    Write-Host "  OK: ngrok found at $NgrokPath" -ForegroundColor Green
} else {
    Write-Host "  WARNING: ngrok not found at $NgrokPath" -ForegroundColor Yellow
    Write-Host "  Please download from: https://ngrok.com/download" -ForegroundColor Yellow
    Write-Host "  Or specify path: .\start_local_testing.ps1 -NgrokPath 'C:\path\to\ngrok.exe'" -ForegroundColor Yellow
}

# Final instructions
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  BACKEND IS READY!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host ""

Write-Host "1. START NGROK (in a NEW PowerShell window):" -ForegroundColor White
Write-Host "   $NgrokPath http 8000" -ForegroundColor Cyan
Write-Host ""

Write-Host "2. COPY THE NGROK URL:" -ForegroundColor White
Write-Host "   Look for: 'Forwarding https://xxxxx.ngrok.io'" -ForegroundColor Cyan
Write-Host ""

Write-Host "3. BUILD WIDGET WITH NGROK URL:" -ForegroundColor White
Write-Host "   .\build_widget.ps1 -ApiUrl 'https://YOUR-NGROK-URL.ngrok.io/api/v1'" -ForegroundColor Cyan
Write-Host ""

Write-Host "4. UPLOAD TO amoCRM:" -ForegroundColor White
Write-Host "   Settings -> Integrations -> Widgets -> Upload custom widget" -ForegroundColor Cyan
Write-Host "   Select file: timesheet_il_widget.zip" -ForegroundColor Cyan
Write-Host ""

Write-Host "USEFUL COMMANDS:" -ForegroundColor Yellow
Write-Host "  View logs:        docker-compose logs backend -f" -ForegroundColor White
Write-Host "  Stop backend:     docker-compose down" -ForegroundColor White
Write-Host "  Restart backend:  docker-compose restart backend" -ForegroundColor White
Write-Host "  Check database:   docker-compose exec db psql -U postgres -d timesheet_db" -ForegroundColor White
Write-Host ""

Write-Host "MONITORING:" -ForegroundColor Yellow
Write-Host "  ngrok dashboard:  http://localhost:4040" -ForegroundColor White
Write-Host "  Backend API:      http://localhost:8000/docs" -ForegroundColor White
Write-Host ""

Write-Host "Read full guide: LOCAL_TESTING_GUIDE.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "Ready for testing! Good luck! " -ForegroundColor Green -NoNewline
Write-Host "🚀" -ForegroundColor Yellow
Write-Host ""
