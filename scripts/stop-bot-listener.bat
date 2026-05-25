@echo off
echo Stopping Feishu Bot listener...
taskkill /F /IM "lark-cli.exe" 2>nul
echo Done.
pause
