@echo off
chcp 65001 >nul 2>&1
title JLAO Frontend (http://127.0.0.1:5173)

if not exist "%~dp0frontend\package.json" (
    echo ERROR: frontend folder not found!
    pause
    exit /b 1
)

cd /d "%~dp0frontend"

echo Killing old frontend on port 5173...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

echo.
echo ============================
echo  JLAO Frontend
echo  http://127.0.0.1:5173
echo ============================
echo.

call npm run dev -- --host 127.0.0.1
if errorlevel 1 (
    echo.
    echo ERROR: npm run dev failed!
    pause
)
