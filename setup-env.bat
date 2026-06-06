@echo off
chcp 65001 >nul
echo ========================================
echo   JLAO 环境配置脚本
echo ========================================
echo.

set "CONDA_ENV=jlao"
set "PYTHON_VERSION=3.11"

if "%1"=="create" goto :create
if "%1"=="activate" goto :activate
if "%1"=="install" goto :install
if "%1"=="update" goto :update
if "%1"=="remove" goto :remove
if "%1"=="help" goto :help

echo 用法: setup-env.bat [命令]
echo.
echo 命令:
echo   create    - 创建 Conda 环境
echo   activate  - 激活环境并启动服务
echo   install   - 安装/更新依赖
echo   update    - 更新所有包
echo   remove    - 删除环境
echo   help      - 显示帮助
echo.
echo 示例:
echo   setup-env.bat create
echo   setup-env.bat activate
echo.
goto :eof

:create
echo [JLAO] 创建 Conda 环境 %CONDA_ENV% (Python %PYTHON_VERSION%)...
conda create -n %CONDA_ENV% python=%PYTHON_VERSION% -y
if errorlevel 1 (
    echo 错误: 创建环境失败
    exit /b 1
)
echo.
echo [JLAO] 安装 CUDA 依赖...
call conda install -n %CONDA_ENV% cudatoolkit=12.8 -c nvidia -y
echo.
echo [JLAO] 安装 Python 依赖...
call %CONDA_ENV%\python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
call %CONDA_ENV%\python -m pip install -r backend\requirements.txt
echo.
echo [JLAO] 环境创建完成！
echo 使用 "setup-env.bat activate" 激活环境
goto :eof

:activate
echo [JLAO] 激活环境 %CONDA_ENV%...
call conda activate %CONDA_ENV%
echo.
echo 环境已激活，可以运行：
echo   python -m uvicorn app.main:app --reload
goto :eof

:install
echo [JLAO] 安装依赖...
call conda activate %CONDA_ENV%
call pip install -r backend\requirements.txt --upgrade
goto :eof

:update
echo [JLAO] 更新所有包...
call conda activate %CONDA_ENV%
call pip install --upgrade torch torchvision torchaudio funasr paddlepaddle paddleocr
call pip install -r backend\requirements.txt --upgrade
goto :eof

:remove
echo [JLAO] 删除环境 %CONDA_ENV%...
conda env remove -n %CONDA_ENV% -y
goto :eof
