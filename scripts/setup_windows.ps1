$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$Launcher = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $Launcher) {
    & py -3.13 -m venv .venv
    Assert-NativeSuccess "Create Python 3.13 virtual environment"
} else {
    $Version = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Assert-NativeSuccess "Read Python version"
    if ($Version.Trim() -ne "3.13") {
        throw "Python 3.13 is required. Current Python: $Version"
    }
    python -m venv .venv
    Assert-NativeSuccess "Create virtual environment"
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python was not created: $Python"
}

& $Python -m pip install --upgrade pip
Assert-NativeSuccess "Upgrade pip"
& $Python -m pip install -e ".[dev]"
Assert-NativeSuccess "Install project dependencies"
& $Python scripts/quality_gate.py
Assert-NativeSuccess "Architecture quality gate"
& $Python -m ruff check src tests scripts
Assert-NativeSuccess "Ruff"
& $Python -m pytest -q
Assert-NativeSuccess "Pytest"

Write-Host ""
Write-Host "Cai dat va kiem tra hoan tat."
Write-Host "Chay ung dung bang CHAY_UNG_DUNG.bat hoac:"
Write-Host "  .\.venv\Scripts\python.exe -m tms"
