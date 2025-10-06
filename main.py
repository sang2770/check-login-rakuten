import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
import time
import random
import logging
import threading
from queue import Queue
import os
import pyautogui
import colorama
from datetime import datetime
import signal
import sys
import atexit
import chromedriver_autoinstaller
import psutil
import shutil

colorama.init()

drivers = []
successful_accounts = []
failed_accounts = []

def kill_child_processes(pid, sig=15):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.send_signal(sig)
            except Exception:
                pass
        gone, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except Exception:
                pass
    except Exception as e:
        pass
        # logging.warning(f"Không thể kill process con cho PID {pid}: {e}")

def cleanup_drivers():
    """Dọn dẹp tất cả các WebDriver instances."""
    logging.warning("Đang dọn dẹp drivers...")
    global drivers
    for driver in drivers[:]:
        try:
            driver.close()
            driver.quit()
            if hasattr(driver, 'service') and driver.service.process:
                kill_child_processes(driver.service.process.pid)
        except Exception as e:
            logging.warning(f"Lỗi khi đóng driver: {e}")
        finally:
            if driver in drivers:
                drivers.remove(driver)

def signal_handler(sig, frame):
    """Xử lý SIGINT (Ctrl+C) và SIGTERM (đóng terminal)."""
    logging.info("Nhận tín hiệu dừng. Đang dọn dẹp...")
    cleanup_drivers()
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

# Hide verbose logs from undetected_chromedriver and other modules
logging.getLogger('undetected_chromedriver').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
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
                            # Format: host:port@username-password
                            try:
                                host_port, credentials = line.split('@', 1)
                                proxies.append({
                                    'host_port': host_port,
                                    'credentials': credentials,
                                    'full': line
                                })
                            except:
                                proxies.append({'host_port': line, 'credentials': None, 'full': line})
                        else:
                            # Standard format: host:port or host:port:user:pass
                            proxies.append({'host_port': line, 'credentials': None, 'full': line})
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

def wait_for_document_loaded(driver, timeout=10):
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                state = driver.execute_script("return document.readyState")
                if state == "complete":
                    return True
            except Exception:
                pass  # Driver might not be ready yet
            time.sleep(1)
        return False
    
def init_driver(proxy=None, email=None, row=0, col=0, size=(1366, 768)):
    """Khởi tạo Chrome driver với cài đặt không bị phát hiện"""
    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-infobars')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-gpu')
    
    # Random user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0"
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')
    
    # User data directory
    user_data_dir = os.path.join(os.getcwd(), "user-data")
    if email:
        user_data_dir = os.path.join(user_data_dir, f"user-data-{email.replace('@', '_').replace('.', '_')}")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    options.add_argument(f'--user-data-dir={user_data_dir}')
    if (proxy and show_browser):
        options.add_argument(f'--proxy-server={proxy["host_port"]}')
    
    # Headless mode
    options.headless = (not show_browser)
    
    try:
        version_main = chromedriver_autoinstaller.get_chrome_version()
        version_main = int(version_main.split('.')[0])
    except:
        version_main = None
    
    driver = uc.Chrome(
        options=options,
        version_main=version_main,
        use_subprocess=True,
        headless=(not show_browser)
    )
    
    # Set window position and size
    if show_browser:
        width, height = size
        x = col * width
        y = row * height
        driver.set_window_rect(x=x, y=y, width=width, height=height)
    else:
        driver.set_window_size(1366, 768)
    
    # Anti-detection scripts
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
    })
    
    # Proxy settings (after driver is created)
    if proxy and show_browser:
        try:
            driver.get('https://bing.com')
            time.sleep(5)
            if wait_for_document_loaded(driver, timeout=10):
                credentials = proxy.get('credentials')
                if credentials:
                    user, password = credentials.split(':')
                    pyautogui.typewrite(user)
                    pyautogui.press('tab')
                    pyautogui.typewrite(password)
                    time.sleep(1)
                    pyautogui.press('enter')
                    time.sleep(random.randint(2, 3))
        except Exception as e:
            logging.warning(f"Lỗi khi cài đặt proxy: {e}")
    
    return driver

def human_type(element, text, min_delay=0.05, max_delay=0.15):
    """Type text with human-like delay"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))

def wait_for_element(driver, by, value, timeout=10, clickable=False):
    """Wait for element to be present or clickable"""
    try:
        if clickable:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        else:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        return element
    except Exception as e:
        logging.error(f"Không tìm thấy element {value}: {repr(e)}")
        raise

def safe_click(driver, element):
    """Click an toàn với fallback về JavaScript"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.3)
        ActionChains(driver).move_to_element(element).click().perform()
    except Exception as e:
        try:
            driver.execute_script("arguments[0].click();", element)
        except Exception as e2:
            logging.warning(f"Cả hai phương pháp click đều thất bại: {repr(e)}, {repr(e2)}")
            raise

def safe_wait_and_click(driver, by, value, timeout=10):
    """Wait for element and click safely"""
    element = wait_for_element(driver, by, value, timeout, clickable=True)
    safe_click(driver, element)
    return element

def generate_random_birthdate():
    """Tạo ngày sinh ngẫu nhiên cho độ tuổi 18-60"""
    current_year = datetime.now().year
    birth_year = random.randint(current_year - 60, current_year - 18)
    birth_month = random.randint(1, 12)
    
    # Handle February and leap years
    if birth_month == 2:
        max_day = 29 if birth_year % 4 == 0 and (birth_year % 100 != 0 or birth_year % 400 == 0) else 28
    elif birth_month in [4, 6, 9, 11]:
        max_day = 30
    else:
        max_day = 31
    
    birth_day = random.randint(1, max_day)
    
    return birth_year, birth_month, birth_day

def check_rakuten_account(driver, email, password):
    """Kiểm tra tài khoản Rakuten"""
    try:
        logging.info(f"Bắt đầu kiểm tra tài khoản: {email}")
        
        # Navigate to login page
        login_url = ("https://login.account.rakuten.com/sso/authorize?"
                    "client_id=rakuten_ichiba_top_web&service_id=s245&response_type=code&"
                    "scope=openid&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F#/sign_in")
        driver.get(login_url)
                
        time.sleep(random.randint(2, 4))
        
        # Step 1: Enter email
        if not _enter_email(driver, email):
            return False, f"Lỗi nhập email cho {email}"
        
        # Step 2: Enter password
        if not _enter_password(driver, password, email):
            return False, f"Lỗi nhập password cho {email}"
        
        # Step 3: Check login success
        if not _check_login_success(driver, email):
            return False, "Đăng nhập thất bại"
        
        # Step 4: Check points
        return _check_points(driver, email, password)
            
    except Exception as e:
        logging.error(f"❌ Lỗi trong quá trình kiểm tra cho {email}: {repr(e)}")
        return False, repr(e)

def _enter_email(driver, email):
    """Enter email in login form"""
    try:
        # Wait for email input field
        email_input = wait_for_element(driver, By.NAME, "username", timeout=10)
        
        # Type email with human-like delay
        human_type(email_input, email)
        time.sleep(random.randint(1, 2))
        
        # Click first submit button (Next)
        safe_wait_and_click(driver, By.ID, "cta001", timeout=10)
        time.sleep(random.randint(2, 4))
        
        return True
        
    except Exception as e:
        logging.error(f"Lỗi khi nhập email: {repr(e)}")
        return False

def _enter_password(driver, password, email):
    """Enter password in login form"""
    try:
        # Wait for password input field
        password_input = wait_for_element(driver, By.NAME, "password", timeout=10)
        
        # Type password with human-like delay
        human_type(password_input, password)
        time.sleep(random.randint(1, 2))
        
        # Click second submit button (Next)
        safe_wait_and_click(driver, By.ID, "cta011", timeout=10)
        
        # Wait for login to process
        time.sleep(5)
        
        return True
        
    except Exception as e:
        logging.error(f"Lỗi khi nhập password cho {email}")
        return False

def _check_login_success(driver, email):
    """Check if login was successful"""
    try:
        # Wait for potential redirect to rakuten.co.jp domain
        WebDriverWait(driver, 15).until(
            lambda d: "rakuten.co.jp" in d.current_url
        )
        
        current_url = driver.current_url
        
        # If still on login page, login failed
        if "login.account.rakuten.com" in current_url:
            # Check for error messages
            try:
                error_selectors = ".error, .alert, [class*='error'], [class*='alert']"
                error_elements = driver.find_elements(By.CSS_SELECTOR, error_selectors)
                if error_elements:
                    error_text = error_elements[0].text
                    logging.warning(f"Đăng nhập thất bại cho {email}: {error_text}")
                    return False
            except:
                pass
            
            logging.warning(f"Đăng nhập thất bại cho {email}: Acc bị khoá hoặc sai mật khẩu")
            return False
        
        return True
        
    except Exception as e:
        logging.error(f"Timeout hoặc lỗi chờ redirect cho {email}: {repr(e)}")
        return False

def _check_points(driver, email, password):
    """Check points information and save to appropriate file"""
    try:
        # Navigate to points page
        points_url = "https://point.rakuten.co.jp/?l-id=top_normal_myrakuten_point"
        driver.get(points_url)    
        time.sleep(5)
        
        # Try to find points information
        try:
            # Look for the points element
            points_element = wait_for_element(driver, By.CSS_SELECTOR, ".point_num", timeout=10)
            points_text = points_element.text.strip()
            
            points_clean = ''.join(filter(str.isdigit, points_text))
            
            if points_clean:
                points_value = int(points_clean)
                logging.info(f"✅ {email} - Điểm: {points_value:,}")
                
                # Save to appropriate file based on points
                with file_lock:
                    if points_value > 0:
                        with open('point_account.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{email}|{password}|{points_value}\n")
                        return True, f"Có điểm: {points_value:,}"
                    else:
                        with open('no_point_account.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{email}|{password}|0\n")
                        return True, "Không có điểm"
            else:
                logging.warning(f"Không thể đọc số điểm cho {email}")
                return True, "Đăng nhập thành công nhưng không đọc được điểm"
                
        except Exception as e:
            logging.warning(f"Không tìm thấy thông tin điểm cho {email}: {repr(e)}")
            # Still consider login successful even if can't read points
            return True, "Đăng nhập thành công nhưng không tìm thấy điểm"
            
    except Exception as e:
        logging.warning(f"Lỗi khi kiểm tra điểm cho {email}: {repr(e)}")
        return True, "Đăng nhập thành công nhưng lỗi kiểm tra điểm"

def process_account(driver, account, account_index):
    """Xử lý đăng ký một tài khoản"""
    email, password = account['email'], account['password']
    try:
        logging.info(f"Đang xử lý tài khoản {account_index + 1}: {email}")
        success, message = check_rakuten_account(driver, email, password)
        with file_lock:
            if success:
                successful_accounts.append(account)
                # Lưu tài khoản thành công
                with open('successful_accounts.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}|{password}|{message}\n")
                
                # Remove successful email from accounts.txt
                try:
                    with open('accounts.txt', 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    with open('accounts.txt', 'w', encoding='utf-8') as f:
                        for line in lines:
                            if line.strip() and not line.startswith('#'):
                                parts = line.strip().split('|')
                                if len(parts) >= 1 and parts[0].strip() != email:
                                    f.write(line)
                            else:
                                f.write(line)
                    logging.info(f"Đã xóa {email} khỏi accounts.txt")
                except Exception as e:
                    logging.warning(f"Không thể xóa {email} khỏi accounts.txt: {e}")
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

def clean_all_user_data(retries=5, delay=1):
    """Dọn dẹp tất cả thư mục dữ liệu người dùng"""
    logging.info("Đang dọn dẹp dữ liệu người dùng...")
    user_data_dir = os.path.join(os.getcwd(), "user-data")
    if os.path.exists(user_data_dir):
        for _ in range(retries):
            try:
                shutil.rmtree(user_data_dir)
                logging.info("Đã dọn dẹp dữ liệu người dùng thành công.")
                break
            except PermissionError:
                logging.warning(f"Đang dọn dẹp dữ liệu. Thử lại sau {delay}s...")
                time.sleep(delay)
            except Exception as e:
                # logging.error(f"Lỗi không mong muốn khi dọn dẹp dữ liệu người dùng: {repr(e)}")
                time.sleep(delay)
        else:
            logging.error(f"Không thể dọn dẹp dữ liệu người dùng sau {retries} lần thử.")

def main():
    """Hàm chính"""
    global show_browser
    
    try:
        # Load input files
        accounts, proxies = load_input_files()
        
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
        
        driver_init_lock = threading.Lock()
        
        def worker():
            """Hàm worker thread"""
            driver = None
            while not account_queue.empty():
                try:
                    account, account_index = account_queue.get()
                    
                    with driver_init_lock:
                        proxy = proxies[account_index % len(proxies)] if len(proxies) > 0 else None
                        row = account_index // col
                        col_index = account_index % col
                        size = (screen_width // col, 400)
                        driver = init_driver(
                            proxy=proxy, 
                            email=account['email'], 
                            row=row, 
                            col=col_index, 
                            size=size
                        )
                        drivers.append(driver)
                    
                    process_account(driver, account, account_index)
                    
                except Exception as e:
                    logging.error(f"Lỗi trong worker thread: {repr(e)}")
                
                finally:
                    if driver:
                        try:
                            driver.close()
                            driver.quit()
                            if hasattr(driver, "service") and hasattr(driver.service, "process") and driver.service.process:
                                kill_child_processes(driver.service.process.pid)
                        except Exception as e:
                            logging.warning(f"Lỗi khi dọn dẹp driver: {e}")
                        finally:
                            if driver in drivers:
                                drivers.remove(driver)
                    
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
        cleanup_drivers()

if __name__ == "__main__":
    try:
        signal.signal(signal.SIGTERM, cleanup_drivers)
        signal.signal(signal.SIGINT, cleanup_drivers)
        atexit.register(cleanup_drivers)
        main()
    except KeyboardInterrupt:
        logging.info("Nhận KeyboardInterrupt. Đang dọn dẹp...")
        cleanup_drivers()
        clean_all_user_data()
        logging.info("Dọn dẹp hoàn tất. Thoát...")
        sys.exit(0)
