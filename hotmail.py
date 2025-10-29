import requests
# import re
# import sys
# from pathlib import Path
# import html
# import json
class Hotmail:
    def __init__(self, mail: str, password: str, refresh_token: str, client_id: str):
        self.mail = mail
        self.password = password
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.access_token = None

    def get_access_token(self):
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": "https://graph.microsoft.com/.default offline_access"
        }

        res = requests.post(token_url, data=data).json()
        self.access_token = res['access_token']

    def get_messages(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
        response = requests.get(url, headers=headers)
        emails = response.json()["value"]
        messages = []
        for count, mail in enumerate(emails):
            # print(f'Html: {mail["body"]["content"]}')
            messages.append(mail["body"]["content"])
        return messages


# email_string = "geoffreyamburgideon3@hotmail.com|8B6mxN1534|M.C517_BAY.0.U.-Crkob6ZkosCVReLGKPRHdHdSQGfcqIJChKy!gvAHwEUWEvnRJY0P5liXXE4rUq9TCU0!lsj3Nilc7f8oSbXI!LbN0uhxvc09TesaaeXDmA2ZeQJ!dxc1XcCtJq61SsGp*xrPT69mB7TD3kyfAmEcJsOK!PacymmAwgHSRm2G1WkH6Rs1DhvATNs1P44GUoHQfdVjX0aiC!GkhM*wDz*sbEXgue3hpFMNUFw1BowPZpZHDvGxMEwO2rE8w4E0HkKMhO9O0L1QGgKnltJa6t3qPAnmSItdYnrfMv8s027RaLFWM1J2d3lYKJqzWFvXRpAIm*ROnRyvqaRq*ZHWqf513DkfEXFWBDV5dSuEy8naSuRC|9e5f94bc-e8a4-4e73-b8be-63364c29d753"
# email, password, refresh_token, client_id = email_string.split("|")
# h = Hotmail(email, password, refresh_token, client_id)
# h.get_access_token()
# messages = h.get_messages()

# def extract_otp_from_html(html_content):
#     if not html_content:
#         return None

#     # Normalize / unescape
#     s = html.unescape(html_content)

#     # --- Original methods kept first (preserve behaviour) ---
#     pattern1 = r'your verification code is:</span></div></td></tr>.*?<div[^>]*><span>(\d{6})</span></div>'
#     m = re.search(pattern1, s, re.IGNORECASE | re.DOTALL)
#     if m:
#         return m.group(1).strip()

#     pattern2 = r'verification code.*?(\d{6})'
#     m = re.search(pattern2, s, re.IGNORECASE | re.DOTALL)
#     if m:
#         return m.group(1).strip()

#     # Find 6-digit codes but exclude hex color codes
#     pattern3 = r'\b(\d{6})\b'
#     for match in re.finditer(pattern3, s):
#         # Get the position and the 6-digit code
#         start_pos = match.start()
#         end_pos = match.end()
#         six_digit_code = match.group(1)
        
#         # Check if it's part of a color code by looking at characters before it
#         prefix = s[max(0, start_pos-1):start_pos]
#         if prefix == '#':
#             # Skip this match as it's likely a color code
#             continue
            
#         # Also check for "color code" text nearby (20 chars before)
#         nearby_text = s[max(0, start_pos-20):start_pos].lower()
#         if 'color' in nearby_text and 'code' in nearby_text:
#             # Skip this match as it's described as a color code
#             continue
            
#         # If we got here, it's not a color code, so return it
#         return six_digit_code.strip()
        
#     return None

# for message in messages:
#     otp = extract_otp_from_html(message)
#     if otp:
#         print(f"OTP code: {otp}")