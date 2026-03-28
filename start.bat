@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title 网易云歌单下载工具

:: 设置工作目录为脚本所在目录
cd /d "%~dp0"

echo ============================================
echo      网易云歌单下载工具 - 启动脚本
echo ============================================
echo.

:: 检查 Python 环境
echo [1/2] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%a in ('python --version 2^>^&1') do set PYTHON_VERSION=%%a
echo [OK] %PYTHON_VERSION%
echo.

:: 检查、创建并激活虚拟环境
echo [2/2] 检查虚拟环境...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] 已激活虚拟环境
) else (
    echo [提示] 未检测到虚拟环境
    set /p CREATE_VENV="是否自动创建虚拟环境? (Y/n): "
    if "!CREATE_VENV!"=="" set CREATE_VENV=Y
    if /i "!CREATE_VENV!"=="Y" (
        echo 正在创建虚拟环境，请稍候...
        python -m venv venv
        if exist "venv\Scripts\activate.bat" (
            call venv\Scripts\activate.bat
            echo [OK] 虚拟环境创建并激活成功
        ) else (
            echo [错误] 虚拟环境创建失败，将使用全局 Python
        )
    ) else (
        echo [提示] 使用全局 Python 运行
    )
)
echo.

:: 检查并安装 Python 依赖
echo 检查 Python 依赖...
if exist "requirements.txt" (
    if exist "venv\Scripts\python.exe" (
        venv\Scripts\python.exe -m pip install -q -r requirements.txt
    ) else (
        python -m pip install -q -r requirements.txt
    )
    if errorlevel 1 (
        echo [警告] 依赖安装可能失败，尝试继续运行...
    ) else (
        echo [OK] 依赖检查完成
    )
) else (
    echo [警告] 未找到 requirements.txt
)
echo.

echo ============================================
echo      启动主程序...
echo ============================================
echo.

:: 运行主程序
echo 正在启动程序...
echo.

:: 使用虚拟环境的 Python 运行（如果存在）
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python main.py
) else (
    python main.py
)
set MAIN_EXIT=%errorlevel%

if %MAIN_EXIT% neq 0 (
    echo.
    echo [错误] 程序异常退出（退出码: %MAIN_EXIT%）
    pause
)

exit /b %MAIN_EXIT%
