param(
    [int]$BackendPort = 8000,
    [int]$PostgresPort = 55432
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$pythonExe = Join-Path $projectRoot ".venv312\Scripts\python.exe"
$localToolsRoot = Join-Path $env:LOCALAPPDATA "TimesheetIL"
$postgresSource = Join-Path $projectRoot "tmp\phase5-tools\pgsql"
$postgresRoot = Join-Path $localToolsRoot "pgsql"
$postgresBin = Join-Path $postgresRoot "bin"
$runtimeRoot = Join-Path $localToolsRoot "local-runtime"
$dataRoot = Join-Path $runtimeRoot "postgres-data"
$postgresLog = Join-Path $runtimeRoot "postgres.log"
$backendOutLog = Join-Path $runtimeRoot "backend.stdout.log"
$backendErrorLog = Join-Path $runtimeRoot "backend.stderr.log"
$backendPidFile = Join-Path $runtimeRoot "backend.pid"

New-Item -ItemType Directory -Path $localToolsRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $postgresBin "initdb.exe"))) {
    if (-not (Test-Path -LiteralPath (Join-Path $postgresSource "bin\initdb.exe"))) {
        throw "Portable PostgreSQL source is missing: $postgresSource"
    }
    Copy-Item -LiteralPath $postgresSource -Destination $postgresRoot -Recurse -Force
}

foreach ($requiredPath in @(
    $pythonExe,
    (Join-Path $postgresBin "initdb.exe"),
    (Join-Path $postgresBin "pg_ctl.exe"),
    (Join-Path $postgresBin "createdb.exe"),
    (Join-Path $postgresBin "psql.exe"),
    (Join-Path $postgresBin "pg_isready.exe"),
    (Join-Path $backendRoot ".env")
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required local component is missing: $requiredPath"
    }
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

$portListener = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
if ($portListener) {
    throw "Backend port $BackendPort is already in use. Stop the other process or set -BackendPort."
}

$pgCtl = Join-Path $postgresBin "pg_ctl.exe"
$pgIsReady = Join-Path $postgresBin "pg_isready.exe"

if (-not (Test-Path -LiteralPath (Join-Path $dataRoot "PG_VERSION"))) {
    New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
    & (Join-Path $postgresBin "initdb.exe") `
        --pgdata=$dataRoot `
        --username=timesheet `
        --auth=trust `
        --encoding=UTF8 `
        --locale=C
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to initialize local PostgreSQL."
    }
}

$localPostgresRunning = $false
& $pgCtl status -D $dataRoot *> $null
$localPostgresRunning = $LASTEXITCODE -eq 0

if ($localPostgresRunning) {
    & $pgIsReady -h 127.0.0.1 -p $PostgresPort -d postgres | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Local PostgreSQL is already running on a different port. Stop it before changing -PostgresPort."
    }
} else {
    $postgresPortListener = Get-NetTCPConnection -LocalPort $PostgresPort -State Listen -ErrorAction SilentlyContinue
    if ($postgresPortListener) {
        throw "PostgreSQL port $PostgresPort is already in use by another process."
    }
    & $pgCtl start -D $dataRoot -l $postgresLog -o "-h 127.0.0.1 -p $PostgresPort"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start local PostgreSQL. See: $postgresLog"
    }
}

$databaseUrl = "postgresql://timesheet@127.0.0.1:$PostgresPort/timesheet_local"
$databaseExists = & (Join-Path $postgresBin "psql.exe") `
    -h 127.0.0.1 -p $PostgresPort -U timesheet -d postgres `
    -Atc "SELECT 1 FROM pg_database WHERE datname = 'timesheet_local'"
if ($databaseExists -ne "1") {
    & (Join-Path $postgresBin "createdb.exe") -h 127.0.0.1 -p $PostgresPort -U timesheet timesheet_local
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the timesheet_local database."
    }
}

$env:DATABASE_URL = $databaseUrl
$env:ENVIRONMENT = "development"
$env:DEBUG = "true"
$env:INGESTION_WORKER_ENABLED = "false"
$env:AMOCRM_REDIRECT_URI = "https://localhost.invalid/api/v1/auth/callback"
$env:ALLOWED_ORIGINS = "[`"http://127.0.0.1:$BackendPort`",`"http://localhost:$BackendPort`"]"

Push-Location $backendRoot
try {
    & $pythonExe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to migrate the local database."
    }

    $backendProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @(
            "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", "$BackendPort",
            "--no-access-log"
        ) `
        -WorkingDirectory $backendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOutLog `
        -RedirectStandardError $backendErrorLog `
        -PassThru
} finally {
    Pop-Location
}

Set-Content -LiteralPath $backendPidFile -Value $backendProcess.Id -Encoding ascii

$readyUrl = "http://127.0.0.1:$BackendPort/health/ready"
for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
        $response = Invoke-RestMethod -Uri $readyUrl -TimeoutSec 2
        if ($response.status -eq "ready") {
            Write-Output "Local environment is running."
            Write-Output "API: http://127.0.0.1:$BackendPort"
            Write-Output "Swagger: http://127.0.0.1:$BackendPort/api/docs"
            Write-Output "PostgreSQL: 127.0.0.1:$PostgresPort / timesheet_local"
            Write-Output "amoCRM ingestion is disabled for this safe local run."
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

throw "Backend did not become ready in 30 seconds. See: $backendErrorLog"
