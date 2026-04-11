import os
import json
import requests
import time
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class KieHandler:
    def __init__(self):
        self.api_key = ""
        if hasattr(st, "secrets") and "KIE_API_KEY" in st.secrets:
            self.api_key = st.secrets["KIE_API_KEY"]
        else:
            self.api_key = os.getenv("KIE_API_KEY", "")
        self.base = "https://api.kie.ai/api/v1"

    def _h(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def image_to_video(self, image_url, prompt="", duration=5):
        body = {
            "model": "kling-2.6/image-to-video",
            "input": {
                "prompt": prompt if prompt else "Gentle natural movement, cinematic quality",
                "image_urls": [image_url],
                "duration": str(duration),
                "sound": False
            }
        }
        try:
            r = requests.post(f"{self.base}/jobs/createTask", headers=self._h(), json=body, timeout=30)
            r.raise_for_status()
            task_id = r.json().get("data", {}).get("taskId", "")
            return (task_id, None) if task_id else (None, "태스크 ID 없음")
        except Exception as e:
            return None, str(e)

    def check_task(self, task_id):
        try:
            r = requests.get(f"{self.base}/jobs/getTaskDetail", headers=self._h(), params={"taskId": task_id}, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", {})
            state = data.get("state", "")
            video_url = ""
            rj = data.get("resultJson", "")
            if rj:
                try:
                    res = json.loads(rj)
                    urls = res.get("resultUrls", [])
                    if urls:
                        video_url = urls[0]
                except:
                    pass
            return state, video_url, None
        except Exception as e:
            return None, None, str(e)

    def wait_for_task(self, task_id, timeout=600, interval=10):
        start = time.time()
        while time.time() - start < timeout:
            state, url, err = self.check_task(task_id)
            if err:
                return None, err
            if state == "success" and url:
                return url, None
            if state == "failed":
                return None, "영상 변환 실패"
            time.sleep(interval)
        return None, "시간 초과 (10분)"

    def download_video(self, video_url, save_path):
        try:
            r = requests.get(video_url, timeout=120)
            r.raise_for_status()
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(r.content)
            return save_path, None
        except Exception as e:
            return None, str(e)
