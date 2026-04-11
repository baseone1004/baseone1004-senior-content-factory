import os
import json
import requests
import urllib.request
import urllib.error
import streamlit as st
from typing import Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class SkyworkHandler:
    def __init__(self):
        self.api_key = ""
        if hasattr(st, "secrets") and "SKYWORK_API_KEY" in st.secrets:
            self.api_key = st.secrets["SKYWORK_API_KEY"]
        else:
            self.api_key = os.getenv("SKYWORK_API_KEY", "")
        self.gateway = "https://api-tools.skywork.ai"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }

    def test_connection(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, "❌ 스카이워크 API 키 미설정"
        try:
            body = {"title": "test", "content": "테스트입니다. 확인이라고만 답하세요.", "language": "Korean", "format": "md"}
            r = requests.post(f"{self.gateway}/theme-gateway", headers=self._headers(), json=body, stream=True, timeout=30)
            if r.status_code == 200:
                return True, "✅ 스카이워크 연결 성공"
            return False, f"❌ HTTP {r.status_code}"
        except Exception as e:
            return False, f"❌ 연결 실패: {e}"

    def generate(self, prompt: str, max_tokens: int = 8000) -> Tuple[str, str]:
        return self.generate_long(prompt)

    def generate_long(self, prompt: str) -> Tuple[str, str]:
        if not self.api_key:
            return None, "스카이워크 API 키가 설정되지 않았습니다"
        body = {"title": "output", "content": prompt, "language": "Korean", "format": "md"}
        try:
            r = requests.post(f"{self.gateway}/theme-gateway", headers=self._headers(), json=body, stream=True, timeout=600)
            r.raise_for_status()
            full = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    d = line[5:].strip()
                    if d == "[DONE]":
                        break
                    try:
                        obj = json.loads(d)
                        for k in ["content", "text", "message"]:
                            if k in obj:
                                full += str(obj[k])
                                break
                    except json.JSONDecodeError:
                        full += d
            return (full, None) if full else (None, "응답이 비어있습니다")
        except Exception as e:
            return None, f"생성 실패: {e}"

    def generate_long_with_search(self, prompt: str) -> Tuple[str, str]:
        return self.generate_long(prompt)

    def generate_image(self, prompt: str, aspect_ratio: str = "9:16", resolution: str = "2K") -> Tuple[str, str]:
        if not self.api_key:
            return None, "스카이워크 API 키가 설정되지 않았습니다"
        body = {
            "title": prompt[:60],
            "content": prompt,
            "style": {},
            "options": {"resolution": resolution},
            "source_platform": ""
        }
        if aspect_ratio:
            body["style"]["aspect_ratio"] = aspect_ratio
        url = f"{self.gateway}/api/sse/image/create"
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        file_url = None
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                cur_event = None
                cur_data = None
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line == "":
                        if cur_event and cur_data:
                            try:
                                data = json.loads(cur_data)
                            except:
                                data = {}
                            if cur_event == "success":
                                file_url = data.get("file_url", "")
                            elif cur_event == "error":
                                return None, data.get("message", "이미지 생성 오류")
                        cur_event = None
                        cur_data = None
                        continue
                    if line.startswith("event:"):
                        cur_event = line[6:].strip()
                    elif line.startswith("data:"):
                        cur_data = line[5:].strip()
            return (file_url, None) if file_url else (None, "이미지 URL을 받지 못했습니다")
        except Exception as e:
            return None, f"이미지 생성 실패: {e}"

    def download_image(self, file_url: str, save_path: str) -> Tuple[str, str]:
        try:
            r = requests.get(file_url, timeout=120)
            r.raise_for_status()
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(r.content)
            return save_path, None
        except Exception as e:
            return None, f"다운로드 실패: {e}"
