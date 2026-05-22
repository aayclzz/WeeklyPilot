@echo off
chcp 65001 >nul
title LanQiao Weekly Report V4.0

echo.
echo ========================================
echo   LanQiao Weekly Report System V4.0
echo ========================================
echo.

cd /d "%~dp0"

:: 优先使用 PATH 中的 python，找不到再尝试常见安装路径
where python >nul 2>nul
if %errorlevel%==0 (
    set PYTHON=python
) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
) else (
    echo [ERROR] Python not found. Please install Python or add it to PATH.
    echo        Download: https://www.python.org/downloads/
    pause
    exit /b 1
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
