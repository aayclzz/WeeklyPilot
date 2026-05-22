@echo off
chcp 65001 >nul
title LanQiao Weekly Report V4.1

echo.
echo ========================================
echo   LanQiao Weekly Report System V4.1
echo ========================================
echo.

cd /d "%~dp0"

:: === 查找 Python 解释器 ===
:: 依次尝试：虚拟环境 → PATH → py 启动器 → 常见安装路径（含自定义盘符）

:: 1. 优先使用虚拟环境
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
    set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
    goto :python_found
)

:: 2. 尝试 PATH 中的 python（用 for /f 捕获实际路径，比 errorlevel 更可靠）
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PYTHON=%%i"
    goto :python_found
)

:: 3. 尝试 python3（部分环境只注册了 python3）
for /f "delims=" %%i in ('where python3 2^>nul') do (
    set "PYTHON=%%i"
    goto :python_found
)

:: 4. 尝试 Windows Python Launcher（py.exe，常见于官方安装器）
for /f "delims=" %%i in ('where py 2^>nul') do (
    set "PYTHON=py"
    goto :python_found
)

:: 5. 遍历常见安装路径（多盘符 + 多版本）
for %%d in (C D E F) do (
    for %%v in (314 313 312 311 310 39 38) do (
        if exist "%%d:\Python%%v\python.exe" (
            set "PYTHON=%%d:\Python%%v\python.exe"
            goto :python_found
        )
    )
    if exist "%%d:\Python\python.exe" (
        set "PYTHON=%%d:\Python\python.exe"
        goto :python_found
    )
    if exist "%%d:\python.exe" (
        set "PYTHON=%%d:\python.exe"
        goto :python_found
    )
)

:: 6. 默认用户安装路径（%LOCALAPPDATA%\Programs\Python\）
for %%v in (314 313 312 311 310 39 38) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        goto :python_found
    )
)

:: 7. Program Files 路径
for %%d in (C D) do (
    for %%v in (314 313 312 311 310 39 38) do (
        if exist "%%d:\Program Files\Python%%v\python.exe" (
            set "PYTHON=%%d:\Program Files\Python%%v\python.exe"
            goto :python_found
        )
    )
)

:: 全部未找到
echo [ERROR] Python not found. Please install Python or add it to PATH.
echo        Download: https://www.python.org/downloads/
pause
exit /b 1

:python_found

echo [INFO] Found Python: %PYTHON%

:: === 检查 Python 版本（需要 3.8+） ===
set "PY_VER="
set "PY_MAJOR="
set "PY_MINOR="
for /f "tokens=2 delims= " %%v in ('"%PYTHON%" --version 2^>^&1') do set "PY_VER=%%v"
if not defined PY_VER (
    echo [WARN] Unable to detect Python version, skipping version check.
    goto :env_setup
)
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)
if not defined PY_MAJOR (
    echo [WARN] Unable to parse Python version (%PY_VER%), skipping version check.
    goto :env_setup
)
if %PY_MAJOR% LSS 3 (
    echo [ERROR] Python version %PY_VER% is too old. Python 3.8+ is required.
    pause
    exit /b 1
)
if %PY_MAJOR%==3 if %PY_MINOR% LSS 8 (
    echo [ERROR] Python version %PY_VER% is too old. Python 3.8+ is required.
    pause
    exit /b 1
)

:env_setup

:: === 自动创建 .env 配置文件 ===
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo [SETUP] Created .env from .env.example
        echo [SETUP] Please edit .env and fill in your account info before running.
        echo        Required fields: LANQIAO_USERNAME, LANQIAO_PASSWORD, OPENAI_API_KEY
        echo.
        echo Opening .env for editing...
        start notepad ".env"
        pause
        exit /b 0
    )
)

:: === 检查并安装依赖 ===
"%PYTHON%" -c "import flask" >nul 2>nul
if %errorlevel% NEQ 0 (
    echo [SETUP] First run detected, installing dependencies...
    echo.
    "%PYTHON%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% NEQ 0 (
        echo.
        echo [WARN] Install with mirror failed, retrying with default source...
        "%PYTHON%" -m pip install -r requirements.txt
    )
    if %errorlevel% NEQ 0 (
        echo.
        echo [ERROR] Failed to install dependencies. Please run manually:
        echo        "%PYTHON%" -m pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo [SETUP] Dependencies installed successfully!
    echo.
)

set MODE=%1
if "%MODE%"=="" set MODE=select

if "%MODE%"=="select" (
    echo [MODE] Visual Select Mode
    echo.
    "%PYTHON%" main.py --select
    goto end
)

if "%MODE%"=="direct" (
    echo [MODE] Direct Input Mode
    echo.
    "%PYTHON%" main.py --direct
    goto end
)

if "%MODE%"=="catalog" (
    echo [MODE] View Course Catalog
    echo.
    "%PYTHON%" main.py --catalog --course-id "%~2"
    goto end
)

if "%MODE%"=="test" (
    echo [MODE] Test Mode
    echo.
    "%PYTHON%" main.py --test --course-id "%~2"
    goto end
)

if "%MODE%"=="clear-cache" (
    echo [MODE] Clear Cache
    echo.
    "%PYTHON%" main.py --clear-cache
    goto end
)

if "%MODE%"=="help" (
    echo Usage: run.bat [mode] [args]
    echo.
    echo Modes:
    echo   select       Visual select mode (default)
    echo   direct       Direct input mode
    echo   catalog ID   View course catalog
    echo   test ID      Test mode
    echo   clear-cache  Clear cache
    echo   help         Show help
    goto end
)

echo [MODE] Visual Select Mode
echo.
"%PYTHON%" main.py --select

:end
echo.
echo Done.
pause
