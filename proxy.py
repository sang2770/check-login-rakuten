import subprocess
import time
import socket
import sys
import os

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def get_mitmdump_path():
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
        mitmdump_path = os.path.join(base_path, 'mitmdump.exe')
        if os.path.exists(mitmdump_path):
            return mitmdump_path
        # fallback to 'mitmdump' if .exe not found in _MEIPASS
    # normal dev environment - rely on PATH
    return 'mitmdump'

class MitmproxyManager:
    """
    Manages a mitmdump subprocess. Use .start() to start, .stop() to stop.
    Optionally usable as context manager.
    """
    def __init__(self, upstream_proxy_string, mitmdump_path=None, log_path=None, startup_timeout=8):
        self.upstream_proxy = upstream_proxy_string
        self.process = None
        self.local_port = find_free_port()
        self.mitmdump_path = mitmdump_path or get_mitmdump_path()
        self.log_path = log_path  # if set, redirect stdout/stderr to this file
        self.startup_timeout = startup_timeout

    @property
    def address(self):
        return f"127.0.0.1:{self.local_port}"

    def _check_mitmdump_exists(self):
        # if mitmdump_path is a path (contains slash or backslash) check exists
        if os.path.isabs(self.mitmdump_path) or os.path.sep in self.mitmdump_path:
            if not os.path.exists(self.mitmdump_path):
                return False
        # otherwise assume in PATH and let subprocess fail if not found
        return True

    def _wait_port_open(self, timeout=None):
        timeout = timeout or self.startup_timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.settimeout(0.5)
                    s.connect(('127.0.0.1', self.local_port))
                    return True
                except Exception:
                    time.sleep(0.2)
        return False

    def start(self):
        if not self._check_mitmdump_exists():
            raise FileNotFoundError(f"mitmdump not found at {self.mitmdump_path}")

        parts = self.upstream_proxy.split(':')
        if len(parts) != 4:
            raise ValueError("Định dạng proxy gốc phải 'host:port:user:password'")

        host, port, user, password = parts

        command = [
            self.mitmdump_path,
            '--set', f'upstream_auth={user}:{password}',
            '--mode', f'upstream:http://{host}:{port}',
            '--listen-port', str(self.local_port),
            # you can remove --quiet for more logs
        ]

        # open log file if requested
        stdout = stderr = None
        if self.log_path:
            logf = open(self.log_path, 'ab')
            stdout = stderr = logf

        # Start process (don't DEVNULL stderr so we can see errors when debugging)
        try:
            self.process = subprocess.Popen(command, stdout=stdout or subprocess.PIPE,
                                            stderr=stderr or subprocess.STDOUT)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Failed to start mitmdump ({self.mitmdump_path}). Ensure it's installed and in PATH.") from e

        # Wait until mitmdump actually listens on the port
        if not self._wait_port_open(timeout=self.startup_timeout):
            # capture a bit of output if available for debugging
            out = None
            try:
                if self.process and self.process.stdout:
                    out = self.process.stdout.read(1024).decode(errors='ignore')
            except Exception:
                out = None
            self.stop()
            raise RuntimeError(f"mitmdump did not open listening port within {self.startup_timeout}s. output: {out!r}")

        return True

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            try:
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None

    # context manager support
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def main():
    with MitmproxyManager("as.proxys5.net:6200:rakuten24h-zone-custom-region-JP:091101") as proxy:
        print(f"Proxy đang chạy tại: {proxy}")
        input("\nNhấn Enter để tiếp tục và tắt proxy...")

if __name__ == "__main__":
    main()