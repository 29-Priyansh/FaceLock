# Builds dist\FaceLock\FaceLock.exe. Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating virtual environment..."
    py -3.11 -m venv .venv
    & $py -m pip install --upgrade pip
    & $py -m pip install -r requirements-dev.txt
}

& $py tools\make_icon.py
& $py -m PyInstaller --noconfirm --clean facelock.spec

$size = (Get-ChildItem dist\FaceLock -Recurse | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Built dist\FaceLock\FaceLock.exe  (folder size {0:N0} MB)" -f $size)
