@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "PS_FILE=%SCRIPT_DIR%start-bot-listener.ps1"

echo Starting Feishu bot listener in background...
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%PS_FILE%"

echo Bot listener started. Log: JLAO\logs\bot-listener.log
echo Press any key to close this window.
pause >nul
