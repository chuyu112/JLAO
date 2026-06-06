@echo off
chcp 65001 >nul
echo ========================================
echo   JLAO 自动构建和部署
echo ========================================
echo.

set "SERVER=root@47.120.41.143"
set "SERVER_IP=47.120.41.143"
set "LOCAL_DIR=D:\JLAO"
set "REMOTE_DIR=/var/www/jlao"

echo [1/4] 构建前端...
cd /d %LOCAL_DIR%\frontend
call npm run build
if errorlevel 1 (
    echo 错误: 前端构建失败
    pause
    exit /b 1
)

echo.
echo [2/4] 上传到服务器...
scp -r %LOCAL_DIR%\frontend\dist\* %SERVER%:%REMOTE_DIR%/
if errorlevel 1 (
    echo 错误: 上传失败
    pause
    exit /b 1
)

echo.
echo [3/4] 重启 nginx...
ssh %SERVER% "nginx -t && systemctl restart nginx"
if errorlevel 1 (
    echo 错误: nginx 重启失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   部署完成!
echo ========================================
echo.
echo 访问地址: https://jlao.szkakayiduo.com
echo.
pause
