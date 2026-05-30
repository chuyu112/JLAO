$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$LocalVenvPython = Join-Path $Backend ".venv-local\Scripts\python.exe"
$Python = $VenvPython

function Test-PythonExecutable {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    return $false
  }

  $PreviousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & $Path -c "print('venv ok')" *> $null
  $ExitCode = $LASTEXITCODE
  $ErrorActionPreference = $PreviousErrorActionPreference
  return $ExitCode -eq 0
}

if (Test-Path $VenvPython) {
  if (-not (Test-PythonExecutable $VenvPython)) {
    if (Test-PythonExecutable $LocalVenvPython) {
      Write-Host "Backend .venv Python is broken, using .venv-local." -ForegroundColor Yellow
      $Python = $LocalVenvPython
    } else {
      Write-Host "Backend venv Python is broken, falling back to system Python." -ForegroundColor Yellow
      $Python = (Get-Command python -ErrorAction Stop).Source
    }
  }
} else {
  if (Test-PythonExecutable $LocalVenvPython) {
    Write-Host "Backend .venv not found, using .venv-local." -ForegroundColor Yellow
    $Python = $LocalVenvPython
  } else {
    Write-Host "Backend venv Python not found, falling back to system Python." -ForegroundColor Yellow
    $Python = (Get-Command python -ErrorAction Stop).Source
  }
}

Set-Location $Backend
Write-Host "Using Python: $Python" -ForegroundColor Cyan
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
