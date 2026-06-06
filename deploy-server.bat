@echo off
chcp 65001 >nul
echo ========================================
echo   JLAO 服务器部署脚本
echo ========================================
echo.

set "SERVER=root@47.120.41.143"
set "SERVER_IP=47.120.41.143"
set "PACKAGE=D:\JLAO\jlao-release.tar.gz"

echo 服务器: %SERVER_IP%
echo.

if not exist "%PACKAGE%" (
    echo 错误: 发布包不存在 %PACKAGE%
    exit /b 1
)

echo [JLAO] 上传发布包到服务器...
scp "%PACKAGE%" "%SERVER%:/tmp/jlao-release.tar.gz"
if errorlevel 1 (
    echo 错误: 上传失败
    exit /b 1
)

echo.
echo [JLAO] 在服务器上执行安装...
ssh %SERVER% "bash -c 'rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release && tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release && bash /tmp/jlao-release/deploy/server-install.sh'"
if errorlevel 1 (
    echo 错误: 安装失败
    exit /b 1
)

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
echo 访问地址: http://%SERVER_IP%
echo.
pause
