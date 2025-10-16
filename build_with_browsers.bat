@echo off
echo =================================================
echo Building Rakuten Check Login Executable
echo =================================================

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install required packages
echo Installing required packages...
pip install -r requirements_build.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install required packages
    pause
    exit /b 1
)

REM Install Playwright browsers first
echo Installing Playwright browsers...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo WARNING: Failed to install Playwright browsers, will try to handle at runtime
)

REM Clean previous build
echo Cleaning previous build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build with PyInstaller
echo Building executable...
pyinstaller main.spec --clean --noconfirm 
if %errorlevel% neq 0 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

REM Create browsers directory
echo Setting up browsers directory...
if not exist "dist\playwright_browsers" mkdir "dist\playwright_browsers"

REM Copy browsers to dist folder
echo Copying Playwright browsers...
set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright
if exist "%PLAYWRIGHT_BROWSERS_PATH%" (
    xcopy /s /e /y /q "%PLAYWRIGHT_BROWSERS_PATH%\*" "dist\playwright_browsers\" >nul 2>&1
    if %errorlevel% equ 0 (
        echo SUCCESS: Browsers copied successfully
    ) else (
        echo WARNING: Some browsers may not have been copied
    )
) else (
    echo WARNING: Could not find Playwright browsers at %PLAYWRIGHT_BROWSERS_PATH%
    echo The executable will try to download browsers at runtime
)

REM Copy additional files
echo Copying additional files...
if exist "accounts.txt" copy "accounts.txt" "dist\" >nul
if exist "proxy.txt" copy "proxy.txt" "dist\" >nul

echo =================================================
echo Build completed successfully!
echo =================================================
echo Executable location: dist\main.exe
echo.
echo IMPORTANT NOTES:
echo 1. Make sure to copy accounts.txt and proxy.txt to the same folder as main.exe
echo 2. If browsers don't work, check BUILD_GUIDE.md for troubleshooting
echo 3. The first run may take longer as it sets up browsers
echo =================================================
pause
