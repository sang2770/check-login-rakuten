import requests
import random

# GemLogin API client
class GemLoginAPI:
    def __init__(self):
        self.base_url = "http://localhost:1010"
        self.session = requests.Session()

    def create_profile(self, proxy, profile_name="AmazonProfile"):
        # Tạo cấu hình mới với proxy HTTP và hệ điều hành Android
        payload = {
            "profile_name": f"{profile_name}_{random.randint(1000, 9999)}",
            "group_name": "All",
            "raw_proxy": f"http://{proxy}",
            "startup_urls": "https://www.biccamera.com/bc/member/SfrLogin.jsp",
            "is_noise_canvas": False,
            "is_noise_webgl": False,
            "is_noise_client_rect": False,
            "is_noise_audio_context": True,
            "is_random_screen": False,
            "is_masked_webgl_data": True,
            "is_masked_media_device": True,
            "os": {"type": "Android", "version": "14"},
            "webrtc_mode": 2,
            "browser_version": "137",
            "browser_type": "chrome",
            "language": "en",
            "time_zone": "America/New_York",
            "country": "United States",
        }
        response = self.session.post(f"{self.base_url}/api/profiles/create", json=payload)
        if response.status_code == 200 and response.json().get("success"):
            return response.json().get("data", {}).get("id")
        return None

    def start_profile(self, profile_id, win_pos, win_size):
        # Khởi động trình duyệt cho cấu hình
        response = self.session.get(f"{self.base_url}/api/profiles/start/{profile_id}?win_pos={win_pos}&win_size={win_size}")
        if response.status_code == 200 and response.json().get("success"):
            return response.json().get("data", {})
        return None

    def close_profile(self, profile_id):
        # Đóng trình duyệt
        self.session.get(f"{self.base_url}/api/profiles/close/{profile_id}")

    def delete_profile(self, profile_id):
        # Xóa cấu hình
        # response = self.session.get(f"{self.base_url}/api/profiles/delete/{profile_id}")
        # if response.status_code == 200 and response.json().get("success"):
        #     return True
        # logger.error(f"CẢNH BÁO: Không xóa được cấu hình {profile_id} {response.json().get('message')}")
        # return False
        return True