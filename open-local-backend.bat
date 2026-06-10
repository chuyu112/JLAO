@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
set "BACKEND_START=%ROOT_DIR%start-backend.bat"
set "BACKEND_HEALTH=http://127.0.0.1:8000/health"
set "BACKEND_URL=http://127.0.0.1:8000/docs"

title JLAO Local Backend

if not exist "%ROOT_DIR%backend\app\main.py" (
    echo ERROR: backend folder not found: %ROOT_DIR%backend
    pause
    exit /b 1
)

if not exist "%BACKEND_START%" (
    echo ERROR: backend start script not found: %BACKEND_START%
    pause
    exit /b 1
)

call :check_backend
if "%BACKEND_READY%"=="1" goto open_browser

echo Starting JLAO backend...
start "JLAO Backend" /D "%ROOT_DIR%" "%ComSpec%" /k call "%BACKEND_START%"

echo Waiting for %BACKEND_HEALTH% ...
for /l %%i in (1,1,45) do (
    powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1
    call :check_backend
    if "!BACKEND_READY!"=="1" goto open_browser
)

echo.
echo Backend did not become ready within 45 seconds.
echo Check the "JLAO Backend" window for Python or uvicorn errors.
pause
exit /b 1

:open_browser
echo Opening %BACKEND_URL%
start "" "%BACKEND_URL%"
exit /b 0

:check_backend
set "BACKEND_READY=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%BACKEND_HEALTH%' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 set "BACKEND_READY=1"
exit /b 0
