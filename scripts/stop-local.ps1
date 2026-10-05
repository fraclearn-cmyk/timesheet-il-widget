$ErrorActionPreference = "Stop"

$runtimeRoot = Join-Path $env:LOCALAPPDATA "TimesheetIL\local-runtime"
$backendPidFile = Join-Path $runtimeRoot "backend.pid"
$pythonExe = Join-Path (Split-Path -Parent $PSScriptRoot) ".venv312\Scripts\python.exe"
$pgCtl = Join-Path $env:LOCALAPPDATA "TimesheetIL\pgsql\bin\pg_ctl.exe"
$dataRoot = Join-Path $runtimeRoot "postgres-data"

if (Test-Path -LiteralPath $backendPidFile) {
    $backendPid = [int](Get-Content -LiteralPath $backendPidFile -Raw)
    $backendProcess = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
    if ($backendProcess) {
        $backendDetails = Get-CimInstance Win32_Process -Filter "ProcessId = $backendPid"
        $expectedPython = (Resolve-Path -LiteralPath $pythonExe).Path
        if (
            $backendDetails.ExecutablePath -ne $expectedPython -or
            $backendDetails.CommandLine -notmatch "uvicorn app\.main:app"
        ) {
            throw "The saved backend PID belongs to another process; it was not stopped."
        }
        Stop-Process -Id $backendPid
        $null = $backendProcess.WaitForExit(10000)
    }
    Remove-Item -LiteralPath $backendPidFile -Force
}

if ((Test-Path -LiteralPath $pgCtl) -and (Test-Path -LiteralPath (Join-Path $dataRoot "PG_VERSION"))) {
    & $pgCtl stop -D $dataRoot -m fast
}

Write-Output "Local backend and PostgreSQL stopped. Data was preserved."
