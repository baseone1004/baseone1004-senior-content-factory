import os
import json
import base64
import requests
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class InworldHandler:
    def __init__(self):
        self.api_key = ""
        if hasattr(st, "secrets") and "INWORLD_API_KEY" in st.secrets:
            self.api_key = st.secrets["INWORLD_API_KEY"]
        else:
            self.api_key = os.getenv("INWORLD_API_KEY", "")
        self.tts_url = "https://api.inworld.ai/tts/v1/voice"
        self.voices_url = "https://api.inworld.ai/voices/v1/voices"

    def _auth(self):
        return {"Authorization": f"Basic {self.api_key}", "Content-Type": "application/json"}

    def test_connection(self):
        if not self.api_key:
            return False, "❌ 인월드 API 키 미설정"
        try:
            r = requests.get(self.voices_url, headers={"Authorization": f"Basic {self.api_key}"}, timeout=15)
            if r.status_code == 200:
                voices = r.json().get("voices", [])
                return True, f"✅ 인월드 연결 성공 (음성 {len(voices)}개)"
            return False, f"❌ HTTP {r.status_code}"
        except Exception as e:
            return False, f"❌ 연결 실패: {e}"

    def list_voices(self):
        try:
            r = requests.get(self.voices_url, headers={"Authorization": f"Basic {self.api_key}"}, timeout=15)
            r.raise_for_status()
            return r.json().get("voices", []), None
        except Exception as e:
            return [], str(e)

    def synthesize(self, text, voice_id="Sarah", model_id="inworld-tts-1.5-max"):
        body = {
            "text": text[:2000],
            "voiceId": voice_id,
            "modelId": model_id,
            "audioConfig": {"audioEncoding": "MP3", "sampleRateHertz": 24000},
            "timestampType": "WORD"
        }
        try:
            r = requests.post(self.tts_url, headers=self._auth(), json=body, timeout=60)
            r.raise_for_status()
            data = r.json()
            audio_b64 = data.get("audioContent", "")
            timestamps = data.get("timestampInfo", {})
            if not audio_b64:
                return None, None, "음성 데이터 비어있음"
            return base64.b64decode(audio_b64), timestamps, None
        except Exception as e:
            return None, None, str(e)

    def save_audio(self, audio_bytes, save_path):
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(audio_bytes)
        return save_path
