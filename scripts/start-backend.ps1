$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

# Conda 环境 Python（新环境）
$CondaPython = "C:\ProgramData\miniconda3\envs\jlao\python.exe"

# 回退：旧虚拟环境
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$LocalVenvPython = Join-Path $Backend ".venv-local\Scripts\python.exe"

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

$Python = $null

# 优先使用 Conda 环境
if (Test-PythonExecutable $CondaPython) {
  $Python = $CondaPython
  Write-Host "Using Conda jlao environment." -ForegroundColor Green
} elseif (Test-PythonExecutable $VenvPython) {
  $Python = $VenvPython
  Write-Host "Using backend .venv." -ForegroundColor Yellow
} elseif (Test-PythonExecutable $LocalVenvPython) {
  $Python = $LocalVenvPython
  Write-Host "Using backend .venv-local." -ForegroundColor Yellow
} else {
  Write-Host "No Python venv found, falling back to system Python." -ForegroundColor Red
  $Python = (Get-Command python -ErrorAction Stop).Source
}

Set-Location $Backend
Write-Host "Using Python: $Python" -ForegroundColor Cyan
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
