# Build a fixed, runtime-only amoCRM widget package. Sources are never edited.
param(
    [string]$ApiUrl
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($PSScriptRoot)
$runtime = @(
    'manifest.json', 'script.js', 'overlay.js', 'timesheet/controller.js', 'styles.css',
    'settings/settings.html', 'settings/settings.js', 'settings/settings.css',
    'i18n/ru.json', 'i18n/en.json',
    'images/icon.png', 'images/logo.png', 'images/logo_main.png',
    'images/logo_medium.png', 'images/logo_min.png', 'images/logo_small.png',
    'images/tour_en.png', 'images/tour_ru.png'
)
$stage = Join-Path $root ('.widget-stage-' + [guid]::NewGuid().ToString('N'))
$archiveTemp = Join-Path $root ('.widget-package-' + [guid]::NewGuid().ToString('N') + '.zip')
$archiveBackup = Join-Path $root ('.widget-backup-' + [guid]::NewGuid().ToString('N') + '.zip')
$archiveFinal = Join-Path $root 'widget.zip'
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)

if ($PSBoundParameters.ContainsKey('ApiUrl')) {
    Write-Warning '-ApiUrl is deprecated and ignored; configure the native amoCRM api_url field instead.'
}

try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    foreach ($name in $runtime) {
        $relative = $name.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        if ($name.StartsWith('settings/')) {
            $source = Join-Path (Join-Path $root 'frontend') $relative
        } else {
            $source = Join-Path (Join-Path $root 'widget') $relative
        }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Missing runtime source: $name"
        }
        $target = Join-Path $stage $relative
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        if ($name -match '\.(json|js|css|html)$') {
            $content = [System.IO.File]::ReadAllText($source, $utf8).TrimStart([char]0xFEFF)
            [System.IO.File]::WriteAllText($target, $content, $utf8)
        } else {
            Copy-Item -LiteralPath $source -Destination $target
        }
    }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $writer = [System.IO.Compression.ZipFile]::Open($archiveTemp, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $runtime) {
            $relative = $name.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $writer, (Join-Path $stage $relative), $name)
        }
    } finally {
        $writer.Dispose()
    }
    $archive = [System.IO.Compression.ZipFile]::OpenRead($archiveTemp)
    try {
        $actual = @($archive.Entries | ForEach-Object { $_.FullName })
        if ($actual.Count -ne $runtime.Count -or (Compare-Object $actual $runtime)) {
            throw 'Build produced unexpected or missing ZIP entries.'
        }
        foreach ($jsonName in @('manifest.json', 'i18n/ru.json', 'i18n/en.json')) {
            $stream = $archive.GetEntry($jsonName).Open()
            try {
                $reader = New-Object System.IO.StreamReader($stream, $utf8, $false)
                try {
                    $jsonText = $reader.ReadToEnd()
                } finally {
                    $reader.Dispose()
                }
                try {
                    $null = ConvertFrom-Json -InputObject $jsonText -ErrorAction Stop
                } catch {
                    throw "Invalid JSON in staged archive: $jsonName"
                }
            } finally {
                $stream.Dispose()
            }
        }
    } finally {
        $archive.Dispose()
    }
    $validatorScript = Join-Path $root 'validate_widget_zip.py'
    if (-not (Test-Path -LiteralPath $validatorScript -PathType Leaf)) {
        throw 'Widget ZIP validator is missing.'
    }
    $pythonExe = Join-Path $root '.venv312\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        $pythonExe = (Get-Command python -ErrorAction Stop).Source
    }
    & $pythonExe $validatorScript $archiveTemp
    if ($LASTEXITCODE -ne 0) {
        throw 'Staged widget ZIP failed validation.'
    }
    if (Test-Path -LiteralPath $archiveFinal -PathType Leaf) {
        [System.IO.File]::Replace($archiveTemp, $archiveFinal, $archiveBackup)
    } else {
        [System.IO.File]::Move($archiveTemp, $archiveFinal)
    }
    Write-Host "Built $archiveFinal ($($runtime.Count) runtime files)."
    Write-Host 'Enter the operational API URL in the native amoCRM field.'
} finally {
    $verifiedStage = [System.IO.Path]::GetFullPath($stage)
    if ($verifiedStage.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $verifiedStage)) {
        Remove-Item -LiteralPath $verifiedStage -Recurse -Force
    }
    $verifiedTemp = [System.IO.Path]::GetFullPath($archiveTemp)
    if ($verifiedTemp.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $verifiedTemp)) {
        Remove-Item -LiteralPath $verifiedTemp -Force
    }
    $verifiedBackup = [System.IO.Path]::GetFullPath($archiveBackup)
    if ($verifiedBackup.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $verifiedBackup)) {
        Remove-Item -LiteralPath $verifiedBackup -Force
    }
}
