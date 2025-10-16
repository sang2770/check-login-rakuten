@echo off
setlocal

echo ===================================================
echo  Checking for Python 3.11 installation...
echo ===================================================

:: Kiểm tra xem Python 3.11 đã cài chưa
python --version 2>nul | find "3.11" >nul
if %errorlevel%==0 (
    echo ✅ Python 3.11 is already installed.
) else (
    echo ⚠️  Python 3.11 not found. Installing...

    :: Tạo thư mục tạm
    set "TMP_DIR=%TEMP%\pysetup"
    if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

    :: Tải Python 3.11 installer (64-bit)
    echo Downloading Python 3.11 installer...
    powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile '%TMP_DIR%\python-installer.exe'"

    :: Cài Python silent + add PATH
    echo Installing Python 3.11 silently...
    "%TMP_DIR%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1

    :: Xóa file cài
    del "%TMP_DIR%\python-installer.exe" >nul 2>&1
)

echo ===================================================
echo  Installing Playwright + Browsers
echo ===================================================

:: Cài Playwright nếu chưa có
pip show playwright >nul 2>&1
if %errorlevel%==0 (
    echo ✅ Playwright is already installed.
) else (
    echo Installing Playwright via pip...
    pip install playwright
)

:: Cài browser Chromium cho Playwright
echo Installing Playwright browsers (Chromium)...
python -m playwright install chromium

echo ===================================================
echo ✅ Setup complete!
echo ===================================================
pause
