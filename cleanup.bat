@echo off
echo ========================================
echo Cleanup browser driver processes
echo ========================================
echo.

echo [1/3] Cleanup Chrome driver...
taskkill /F /IM chromedriver.exe 2>nul

echo [2/3] Cleanup Edge driver...
taskkill /F /IM msedgedriver.exe 2>nul

echo [3/3] Cleanup Firefox driver...
taskkill /F /IM geckodriver.exe 2>nul

echo.
echo ========================================
echo Cleanup completed!
echo ========================================
pause
