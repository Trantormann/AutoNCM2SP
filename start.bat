@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title 网易云歌单下载工具

:: 设置工作目录为脚本所在目录
cd /d "%~dp0"

echo ============================================
echo      网易云歌单下载工具
echo ============================================
echo.

:: 检查 Python 环境
echo [*] 检查 Python 环境...
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo 提示：安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=*" %%a in ('python --version 2^>^&1') do set PYTHON_VERSION=%%a
echo [OK] %PYTHON_VERSION%
echo.

:: 自动创建并激活虚拟环境
echo [*] 检查虚拟环境...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] 虚拟环境已激活
) else (
    echo [提示] 未检测到虚拟环境，正在自动创建...
    python -m venv venv
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
        echo [OK] 虚拟环境创建成功
    ) else (
        echo [警告] 虚拟环境创建失败，将使用全局 Python
    )
)
echo.

:: 检查并安装 Python 依赖
echo [*] 安装依赖...
if exist "requirements.txt" (
    if exist "venv\Scripts\python.exe" (
        venv\Scripts\python.exe -m pip install -q -r requirements.txt
    ) else (
        python -m pip install -q -r requirements.txt
    )
    if errorlevel 1 (
        echo [警告] 依赖安装可能失败，继续运行...
    ) else (
        echo [OK] 依赖安装完成
    )
) else (
    echo [警告] 未找到 requirements.txt
)
echo.

:: 首次运行检查配置文件
if not exist "config\config.json" (
    if exist "config\config.example.json" (
        echo [提示] 首次运行，正在从模板创建配置文件...
        copy "config\config.example.json" "config\config.json" >nul
        echo [OK] 配置文件已创建
        echo.
        echo [重要] 请先编辑配置文件，填写歌单链接和登录信息！
        echo.
        notepad "config\config.json"
        echo.
        echo 配置完成后按任意键继续...
        pause >nul
    ) else (
        echo [警告] 未找到配置模板文件
    )
)

:: 功能选择菜单
:MENU
echo ============================================
echo      功能菜单
echo ============================================
echo.
echo   [1] 启动增量下载
echo   [2] 修改配置文件
echo   [3] 清除下载记录
echo   [4] 退出登录
echo   [5] 退出程序
echo.
set /p CHOICE="请选择功能 (1-5): "

if "!CHOICE!"=="1" goto DOWNLOAD
if "!CHOICE!"=="2" goto EDIT_CONFIG
if "!CHOICE!"=="3" goto CLEAR_RECORDS
if "!CHOICE!"=="4" goto LOGOUT
if "!CHOICE!"=="5" goto EXIT

echo [错误] 无效选项，请重新选择
echo.
goto MENU

:: 启动增量下载
:DOWNLOAD
echo.
echo [*] 启动下载...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python main.py
) else (
    python main.py
)
set MAIN_EXIT=%errorlevel%
if %MAIN_EXIT% neq 0 (
    echo.
    echo [错误] 程序异常退出，退出码: %MAIN_EXIT%
)
pause
goto MENU

:: 修改配置文件
:EDIT_CONFIG
echo.
if exist "config\config.json" (
    echo [*] 正在打开配置文件...
    notepad "config\config.json"
) else (
    echo [提示] 配置文件不存在，正在从模板创建...
    if exist "config\config.example.json" (
        copy "config\config.example.json" "config\config.json"
        notepad "config\config.json"
    ) else (
        echo [错误] 未找到配置模板文件!
    )
)
echo.
pause
goto MENU

:: 清除下载记录
:CLEAR_RECORDS
echo.
echo [*] 正在清除下载记录...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python main.py --clear
) else (
    python main.py --clear
)
echo.
pause
goto MENU

:: 退出登录
:LOGOUT
echo.
echo [*] 正在退出登录...
if exist "config\.ncm_session" (
    del "config\.ncm_session"
    echo [OK] 已清除登录状态，下次启动需要重新登录
) else (
    echo [提示] 当前未登录
)
echo.
pause
goto MENU

:: 退出程序
:EXIT
echo.
echo [*] 再见!
exit /b 0
