@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title 网易云歌单下载工具 - 自动模式

:: 设置工作目录为脚本所在目录
cd /d "%~dp0"

echo ============================================
echo      网易云歌单下载工具 - 自动下载模式
echo ============================================
echo.

:: 检查并激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [*] 虚拟环境已激活
) else (
    echo [提示] 使用全局 Python
)

:: 安装依赖
echo [*] 检查依赖...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m pip install -q -r requirements.txt
) else (
    python -m pip install -q -r requirements.txt
)
echo [OK] 依赖就绪
echo.

:: 直接启动下载（不显示菜单）
echo [*] 开始自动下载...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python main.py
) else (
    python main.py
)

echo.
echo [*] 下载完成，窗口将在 5 秒后关闭...
timeout /t 5 /nobreak >nul
exit /b 0
