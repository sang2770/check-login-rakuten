import subprocess
import time
import socket
import sys
import os

def find_free_port():
    """
    Tìm một cổng TCP đang rảnh trên máy.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Bind vào cổng 0 để hệ điều hành tự chọn cổng rảnh
        s.bind(('127.0.0.1', 0))
        # Lấy thông tin địa chỉ và cổng đã được gán
        port = s.getsockname()[1]
        # Trả về số cổng đã tìm được
        return port
def get_mitmdump_path():
    """
    Tìm đường dẫn đến file thực thi mitmdump.
    Nếu đang chạy từ file .exe đã đóng gói, nó sẽ tìm trong thư mục tạm thời.
    Nếu không, nó chỉ trả về 'mitmdump' để hệ thống tự tìm trong PATH.
    """
    if hasattr(sys, '_MEIPASS'):
        # Đang chạy trong môi trường PyInstaller đã đóng gói
        # sys._MEIPASS là đường dẫn đến thư mục tạm thời
        base_path = sys._MEIPASS
        mitmdump_path = os.path.join(base_path, 'mitmdump.exe')
        return mitmdump_path
    
    # Đang chạy từ source code .py
    return 'mitmdump'
class MitmproxyManager:
    """
    Một Context Manager để tự động khởi động và tắt mitmdump.
    """
    def __init__(self, upstream_proxy_string):
        """
        Khởi tạo với chuỗi proxy gốc dạng 'host:port:user:pass'.
        """
        self.upstream_proxy = upstream_proxy_string
        self.process = None
        self.local_port = find_free_port()

    def __enter__(self):
        """
        Được gọi khi bắt đầu khối 'with'. Khởi động mitmdump.
        """
        # print("--- [Mitmproxy Manager] Đang khởi động proxy trung gian... ---")
        parts = self.upstream_proxy.split(':')
        if len(parts) != 4:
            raise ValueError("Định dạng proxy gốc không hợp lệ. Cần 'host:port:user:password'.")
        
        host, port, user, password = parts
        # print(f"--- [Mitmproxy Manager] Đang sử dụng proxy gốc: {host}:{port} --- {user}:{password}")
        # Xây dựng lệnh để chạy mitmdump
        mitmdump_executable = get_mitmdump_path()
        command = [
            mitmdump_executable,
            '--set', f'upstream_auth={user}:{password}',
            '--mode', f'upstream:http://{host}:{port}',
            '--listen-port', str(self.local_port),
            '--quiet'
        ]
        # print(f"Command: {command}")

        # Khởi chạy tiến trình nền
        # stdout=subprocess.DEVNULL để ẩn output của mitmdump ra console chính
        self.process = subprocess.Popen(command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        
        # Chờ một vài giây để proxy có thời gian khởi động hoàn toàn
        time.sleep(3) 
        
        # print(f"--- [Mitmproxy Manager] Proxy trung gian đang chạy tại 127.0.0.1:{self.local_port} ---")
        return f"127.0.0.1:{self.local_port}"

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Được gọi khi kết thúc khối 'with'. Tắt mitmdump.
        """
        # print("--- [Mitmproxy Manager] Đang tắt proxy trung gian... ---")
        if self.process:
            self.process.terminate() # Gửi tín hiệu yêu cầu dừng
            self.process.wait()    # Chờ tiến trình dừng hẳn
        # print("--- [Mitmproxy Manager] Proxy trung gian đã được tắt. ---")

def main():
    with MitmproxyManager("as.proxys5.net:6200:rakuten24h-zone-custom-region-JP:091101") as proxy:
        print(f"Proxy đang chạy tại: {proxy}")
        input("\nNhấn Enter để tiếp tục và tắt proxy...")

if __name__ == "__main__":
    main()