# Build a Windows DocShield bundle. Run from the repo root in PowerShell.
#
# Usage:   .\packaging\build_windows.ps1
# Output:  dist\DocShield\DocShield.exe    (portable folder)
#
# No admin rights required at build or run time (NFR-3.1). Users can
# drop the folder onto a USB stick and launch from any machine.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv\Scripts\pyinstaller.exe")) {
    Write-Error "PyInstaller not found in .venv. Install with: .venv\Scripts\pip install pyinstaller"
    exit 1
}

# Verify models are installed.
& .venv\Scripts\python.exe -c @"
import importlib.util, sys
missing = [m for m in ('en_core_web_lg', 'it_core_news_lg') if importlib.util.find_spec(m) is None]
if missing: sys.exit(f'missing spaCy models: {missing}')
"@

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }

& .venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\docshield.spec

Write-Host ""
Write-Host "Built: dist\DocShield\DocShield.exe"
Get-ChildItem dist\DocShield | Measure-Object -Property Length -Sum | ForEach-Object {
    "{0:N0} MB total" -f ($_.Sum / 1MB)
}
