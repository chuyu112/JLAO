@echo off
chcp 65001 >nul 2>&1
title JLAO Backend (http://127.0.0.1:8000)

if not exist "%~dp0backend\app\main.py" (
    echo ERROR: backend folder not found!
    pause
    exit /b 1
)

cd /d "%~dp0backend"

echo Killing old backend on port 8000...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

set "CondaPython=C:\ProgramData\miniconda3\envs\jlao\python.exe"
set "VenvPython=%~dp0backend\.venv\Scripts\python.exe"
set "LocalVenvPython=%~dp0backend\.venv-local\Scripts\python.exe"
set "Python="

if exist "%CondaPython%" (
    "%CondaPython%" -c "print('ok')" >nul 2>&1
    if not errorlevel 1 (
        set "Python=%CondaPython%"
        echo [Conda] jlao environment
    )
)

if not defined Python (
    if exist "%VenvPython%" (
        "%VenvPython%" -c "print('ok')" >nul 2>&1
        if not errorlevel 1 (
            set "Python=%VenvPython%"
            echo [.venv] backend
        )
    )
)

if not defined Python (
    if exist "%LocalVenvPython%" (
        "%LocalVenvPython%" -c "print('ok')" >nul 2>&1
        if not errorlevel 1 (
            set "Python=%LocalVenvPython%"
            echo [.venv-local] backend
        )
    )
)

if not defined Python (
    echo [System] fallback to system Python
    set "Python=python"
)

echo.
echo ============================
echo  JLAO Backend
echo  http://127.0.0.1:8000
echo ============================
echo Python: %Python%
echo.

"%Python%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 (
    echo.
    echo ERROR: uvicorn failed!
    pause
)
