@echo off
echo Installing requirements for GPM + Playwright version...
pip install -r requirements_gpm.txt
echo Installing Playwright browsers...
playwright install chromium

echo.
echo Make sure GPM Login is running on port 19995
echo Press any key to start the automation...
pause

python main_gpm_playwright.py
