$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$Python = $VenvPython

if (Test-Path $VenvPython) {
  $PreviousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & $VenvPython -c "print('venv ok')" *> $null
  $ErrorActionPreference = $PreviousErrorActionPreference
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend venv Python is broken, falling back to system Python." -ForegroundColor Yellow
    $Python = (Get-Command python -ErrorAction Stop).Source
  }
} else {
  Write-Host "Backend venv Python not found, falling back to system Python." -ForegroundColor Yellow
  $Python = (Get-Command python -ErrorAction Stop).Source
}

Set-Location $Backend
Write-Host "Using Python: $Python" -ForegroundColor Cyan
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
