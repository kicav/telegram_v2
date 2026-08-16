$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
$env:PYTHONPATH = (Join-Path $RepoRoot "src")

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction Stop
    $Python = $PythonCommand.Source
}

& $Python scripts/quality_gate.py
Assert-NativeSuccess "Architecture quality gate"
& $Python -m ruff check src tests scripts
Assert-NativeSuccess "Ruff"
& $Python -m pytest -q
Assert-NativeSuccess "Pytest"

if (Test-Path "dist") {
    Remove-Item "dist" -Recurse -Force
}

$NuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--enable-plugin=pyside6",
    "--windows-console-mode=disable",
    "--assume-yes-for-downloads",
    "--include-package=tms",
    "--include-package=telethon",
    "--include-package=openpyxl",
    "--include-data-file=src/tms/storage/schema.sql=tms/storage/schema.sql",
    "--output-dir=dist",
    "--output-filename=TelegramMigrationStudio.exe",
    "scripts/windows_entry.py"
)
& $Python @NuitkaArgs
Assert-NativeSuccess "Nuitka standalone build"

$Exe = Get-ChildItem -Path "dist" -Recurse -Filter "TelegramMigrationStudio.exe" -File | Select-Object -First 1
if ($null -eq $Exe) {
    throw "Nuitka finished without producing TelegramMigrationStudio.exe"
}

Write-Host ""
Write-Host "Windows standalone build completed: $($Exe.FullName)"
