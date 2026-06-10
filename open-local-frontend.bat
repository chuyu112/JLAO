@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "FRONTEND_URL=http://127.0.0.1:5173/?api=http://127.0.0.1:8000"

title JLAO Local Frontend

if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: frontend folder not found: %FRONTEND_DIR%
    pause
    exit /b 1
)

call :check_frontend
if "%FRONTEND_READY%"=="1" goto open_browser

echo Starting JLAO frontend...
start "JLAO Frontend" /D "%FRONTEND_DIR%" "%ComSpec%" /k npm run dev -- --host 127.0.0.1

echo Waiting for %FRONTEND_URL% ...
for /l %%i in (1,1,30) do (
    powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1
    call :check_frontend
    if "!FRONTEND_READY!"=="1" goto open_browser
)

echo.
echo Frontend did not become ready within 30 seconds.
echo Check the "JLAO Frontend" window for npm errors.
pause
exit /b 1

:open_browser
echo Opening %FRONTEND_URL%
start "" "%FRONTEND_URL%"
exit /b 0

:check_frontend
set "FRONTEND_READY=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%FRONTEND_URL%' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 set "FRONTEND_READY=1"
exit /b 0
