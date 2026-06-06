@echo off
chcp 65001 >nul
echo ========================================
echo   JLAO Docker 本地部署脚本
echo ========================================
echo.

set "COMPOSE_FILE=docker-compose.yml"

if "%1"=="build" goto :build
if "%1"=="up" goto :up
if "%1"=="down" goto :down
if "%1"=="logs" goto :logs
if "%1"=="shell" goto :shell
if "%1"=="clean" goto :clean
if "%1"=="help" goto :help

:help
echo 用法: docker-run.bat [命令]
echo.
echo 命令:
echo   build   - 构建 Docker 镜像
echo   up      - 启动服务
echo   down    - 停止服务
echo   logs    - 查看日志
echo   shell   - 进入容器
echo   clean   - 清理容器和镜像
echo   help    - 显示帮助
echo.
echo 示例:
echo   docker-run.bat build
echo   docker-run.bat up
echo   docker-run.bat logs
echo.
goto :eof

:build
echo [JLAO] 构建 Docker 镜像...
docker-compose -f %COMPOSE_FILE% build --no-cache
goto :eof

:up
echo [JLAO] 启动服务...
docker-compose -f %COMPOSE_FILE% up -d
echo.
echo 服务已启动:
echo   - 后端 API: http://localhost:8001
echo   - 前端页面: http://localhost
echo.
goto :eof

:down
echo [JLAO] 停止服务...
docker-compose -f %COMPOSE_FILE% down
goto :eof

:logs
echo [JLAO] 查看日志...
docker-compose -f %COMPOSE_FILE% logs -f
goto :eof

:shell
echo [JLAO] 进入容器...
docker-compose -f %COMPOSE_FILE% exec jlao-backend /bin/bash
goto :eof

clean
echo [JLAO] 清理容器和镜像...
docker-compose -f %COMPOSE_FILE% down --rmi all --volumes
goto :eof
