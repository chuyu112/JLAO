@echo off
echo ========================================
echo   JLAO Local Backend Launcher
echo ========================================
echo.

set BACKEND_DIR=D:\JLAO\backend
set PORT=8000
set LOG_DIR=D:\JLAO\logs

if not exist %LOG_DIR% mkdir %LOG_DIR%

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
echo [JLAO] Logs: %LOG_DIR%\backend.log
echo.

:loop
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% 2>&1 | powershell -Command "$input | Tee-Object -FilePath '%LOG_DIR%\backend.log' -Append"
echo [JLAO] Backend exited at %date% %time%, restarting in 3s...
timeout /t 3 /nobreak >nul 2>nul
goto loop
