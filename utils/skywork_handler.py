import os
import json
import io
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
        self.gateway = "https://api-tools.skywork.ai/theme-gateway"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }

    def _parse_sse_doc(self, resp):
        reader = io.TextIOWrapper(resp, encoding="utf-8", errors="replace")
        buf = ""
        for ch in iter(lambda: reader.read(1), ""):
            buf += ch
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                ev_type = None
                ev_data = None
                for line in block.strip().split("\n"):
                    if line.startswith("event: "):
                        ev_type = line[7:].strip()
                    elif line.startswith("data: "):
                        ev_data = line[6:]
                if ev_data:
                    try:
                        data = json.loads(ev_data)
                        yield ev_type or data.get("type", "message"), data
                    except json.JSONDecodeError:
                        pass

    def test_connection(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, "❌ 스카이워크 API 키 미설정"
        try:
            body = {
                "type": "create_doc",
                "request_id": "test-conn",
                "title": "test",
                "content": "테스트입니다. 확인이라고만 답하세요.",
                "format": "md",
                "source_platform": ""
            }
            payload = json.dumps(body).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            url = f"{self.gateway}/api/sse/doc/create"
            req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                for ev_type, data in self._parse_sse_doc(resp):
                    if ev_type == "error":
                        msg = data.get("message", "알 수 없는 오류")
                        return False, f"❌ {msg}"
                    if ev_type in ("progress", "success", "content_chunk"):
                        return True, "✅ 스카이워크 연결 성공"
            return True, "✅ 스카이워크 연결 성공"
        except urllib.error.HTTPError as e:
            return False, f"❌ HTTP {e.code}"
        except Exception as e:
            return False, f"❌ 연결 실패: {e}"

    def generate(self, prompt: str, max_tokens: int = 8000) -> Tuple[str, str]:
        return self.generate_long(prompt)

    def generate_long(self, prompt: str) -> Tuple[str, str]:
        if not self.api_key:
            return None, "스카이워크 API 키가 설정되지 않았습니다"
        body = {
            "type": "create_doc",
            "request_id": f"gen-{id(prompt)}",
            "title": "output",
            "content": prompt,
            "format": "md",
            "source_platform": ""
        }
        url = f"{self.gateway}/api/sse/doc/create"
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        full = ""
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                for ev_type, data in self._parse_sse_doc(resp):
                    if ev_type == "content_chunk":
                        chunk = data.get("chunk", "")
                        full += chunk
                    elif ev_type == "deepsearch":
                        chunk = data.get("chunk", "")
                        full += chunk
                    elif ev_type == "success":
                        file_url = data.get("file_url", "")
                        if file_url and not full:
                            try:
                                r = requests.get(file_url, timeout=120)
                                r.raise_for_status()
                                full = r.text
                            except:
                                pass
                    elif ev_type == "error":
                        msg = data.get("message", "알 수 없는 오류")
                        return None, f"생성 실패: {msg}"
            return (full, None) if full else (None, "응답이 비어있습니다")
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            return None, f"HTTP {e.code}: {body_text[:200]}"
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
