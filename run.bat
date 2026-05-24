@echo off
chcp 65001 >nul
title LanQiao Weekly Report V4.1

echo.
echo ========================================
echo   LanQiao Weekly Report System V4.1
echo ========================================
echo.

cd /d "%~dp0"

:: Find Python interpreter

:: 1. Check virtual environment
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
    set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
    goto :python_found
)

:: 2. Try PATH
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PYTHON=%%i"
    goto :python_found
)

:: 3. Try python3
for /f "delims=" %%i in ('where python3 2^>nul') do (
    set "PYTHON=%%i"
    goto :python_found
)

:: 4. Try py launcher
for /f "delims=" %%i in ('where py 2^>nul') do (
    set "PYTHON=py"
    goto :python_found
)

:: 5. Common install paths
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

:: 6. User install path
for %%v in (314 313 312 311 310 39 38) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        goto :python_found
    )
)

:: 7. Program Files
for %%d in (C D) do (
    for %%v in (314 313 312 311 310 39 38) do (
        if exist "%%d:\Program Files\Python%%v\python.exe" (
            set "PYTHON=%%d:\Program Files\Python%%v\python.exe"
            goto :python_found
        )
    )
)

echo [ERROR] Python not found. Please install Python or add it to PATH.
echo        Download: https://www.python.org/downloads/
pause
exit /b 1

:python_found

echo [INFO] Found Python: %PYTHON%

:: Check Python version (requires 3.8+)
set "PY_VER="
set "PY_MAJOR="
set "PY_MINOR="
for /f "tokens=2 delims= " %%v in ('"%PYTHON%" --version 2^>^&1') do set "PY_VER=%%v"
if not defined PY_VER goto :skip_ver_check
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)
if not defined PY_MAJOR goto :skip_ver_check
if %PY_MAJOR% LSS 3 goto :ver_too_old
if "%PY_MAJOR%"=="3" if %PY_MINOR% LSS 8 goto :ver_too_old
goto :env_setup

:skip_ver_check
echo [WARN] Unable to detect Python version, skipping version check.
goto :env_setup

:ver_too_old
echo [ERROR] Python version %PY_VER% is too old. Python 3.8+ is required.
pause
exit /b 1

:env_setup

:: Create .env config file
if exist ".env" goto :check_deps
if not exist ".env.example" goto :check_deps
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

:check_deps

:: Check and install dependencies
"%PYTHON%" -c "import flask" >nul 2>nul
if %errorlevel% EQU 0 goto :select_mode

echo [SETUP] First run detected, installing dependencies...
echo.
"%PYTHON%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% EQU 0 goto :deps_ok

echo.
echo [WARN] Install with mirror failed, retrying with default source...
"%PYTHON%" -m pip install -r requirements.txt
if %errorlevel% EQU 0 goto :deps_ok

echo.
echo [ERROR] Failed to install dependencies. Please run manually:
echo        "%PYTHON%" -m pip install -r requirements.txt
pause
exit /b 1

:deps_ok
echo.
echo [SETUP] Dependencies installed successfully!
echo.

:select_mode

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
