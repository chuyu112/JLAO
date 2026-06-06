@echo off
echo ========================================
echo   JLAO Local Backend Launcher
echo ========================================
echo.

set BACKEND_DIR=D:\JLAO\backend
set PORT=8000

cd /d %BACKEND_DIR%

echo [JLAO] Killing process on port %PORT%...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>nul
    echo [JLAO] Killed PID %%a
)

timeout /t 2 /nobreak >nul 2>nul

echo.
echo [JLAO] Starting backend...
echo [JLAO] URL: http://127.0.0.1:%PORT%
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

pause
