@echo off
chcp 65001 >nul
echo ========================================
echo   JLAO 本地完整环境启动脚本
echo ========================================
echo.

set "ROOT_DIR=D:\JLAO"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

REM 检查目录
if not exist "%BACKEND_DIR%" (
    echo 错误: 后端目录不存在 %BACKEND_DIR%
    exit /b 1
)

if not exist "%FRONTEND_DIR%" (
    echo 错误: 前端目录不存在 %FRONTEND_DIR%
    exit /b 1
)

echo [JLAO] 启动本地完整环境...
echo.

REM 设置环境变量
REM 本地后端连接服务器数据库
set "DATABASE_URL=http://47.120.41.143/data/jlao-mvp.sqlite"

echo [JLAO] 数据库: %DATABASE_URL%
echo.

REM 启动后端（新窗口）
echo [JLAO] 启动后端...
start "JLAO Backend" cmd /k "cd /d %BACKEND_DIR% && .venv\Scripts\activate && set DATABASE_URL=%DATABASE_URL% && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端（新窗口）
echo [JLAO] 启动前端...
start "JLAO Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"

echo.
echo [JLAO] 本地环境已启动！
echo.
echo 访问地址：
echo   - 前端：http://127.0.0.1:5173
echo   - 后端：http://127.0.0.1:8000
echo   - 数据库：http://47.120.41.143/data/jlao-mvp.sqlite
echo.
echo 请确保：
echo   1. 后端窗口显示 "Application startup complete"
echo   2. 前端窗口显示 "Local: http://127.0.0.1:5173"
echo.
pause
