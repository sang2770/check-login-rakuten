# Rakuten Account Checker - GPM + Playwright Version

This version uses GPM (GoLogin Proxy Manager) API with Playwright for better anti-detection.

## Prerequisites

1. **GPM Login software** must be installed and running on your system
2. GPM should be running on `http://127.0.0.1:19995` (default port)
3. Python 3.7+ installed

## Setup

1. Install required packages:
   ```
   pip install -r requirements_gpm.txt
   playwright install chromium
   ```

2. Or run the setup batch file:
   ```
   setup_gpm.bat
   ```

## File Structure

- `main_gpm_playwright.py` - Main script using GPM API + Playwright
- `accounts.txt` - Account list (email:password format)
- `proxy.txt` - Proxy list (optional)
- `requirements_gpm.txt` - Python dependencies

## How it works

1. **Profile Creation**: Creates a new GPM profile for each account with proxy settings
2. **Browser Launch**: Starts a browser instance through GPM
3. **Playwright Connection**: Connects Playwright to the GPM-managed browser via CDP
4. **Account Check**: Logs into Rakuten and checks points using Playwright
5. **Cleanup**: Closes browser and deletes the profile

## Advantages of GPM + Playwright Version

- **Best Anti-Detection**: Combines GPM's fingerprinting with Playwright's stealth
- **Better Proxy Management**: GPM handles proxy rotation and validation
- **Profile Isolation**: Each account runs in a completely isolated profile
- **Playwright Features**: Full access to Playwright's advanced features
- **Stealth Integration**: Uses undetected-playwright for maximum stealth

## Usage

1. Make sure GPM Login is running
2. Prepare your `accounts.txt` and `proxy.txt` files
3. Run: `python main_gpm_playwright.py`
4. Enter number of threads when prompted
5. Choose whether to show browser windows

## Output Files

- `successful_accounts.txt` - Successfully logged in accounts
- `failed_accounts.txt` - Failed login attempts
- `point_account.txt` - Accounts with points information
- `no_point_account.txt` - Accounts with no points
- `rakuten_automation.log` - Detailed logs

## Notes

- Each account creates a temporary GPM profile that is deleted after processing
- Proxy format: `host:port:username:password` or `host:port@username:password`
- The script automatically handles profile cleanup even if interrupted
- Uses CDP (Chrome DevTools Protocol) to connect Playwright to GPM browsers
