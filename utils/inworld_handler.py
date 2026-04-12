import os
import base64
import requests
import streamlit as st

class InworldHandler:
    """Inworld TTS API Handler - 한국어 음성 지원"""
    
    # Inworld TTS API 엔드포인트
    SYNTHESIZE_URL = "https://api.inworld.ai/tts/v1/synthesize"
    SYNTHESIZE_STREAM_URL = "https://api.inworld.ai/tts/v1/synthesize:stream"
    LIST_VOICES_URL = "https://api.inworld.ai/tts/v1/voices"
    
    # 한국어 음성 프리셋
    KOREAN_VOICES = {
        "현우": {"voiceId": "Hyunwoo", "desc": "젊은 성인 남성 목소리", "gender": "male"},
        "민지": {"voiceId": "Minji", "desc": "활기차고 친근한 젊은 여성 목소리", "gender": "female"},
        "서준": {"voiceId": "Seojun", "desc": "깊고 성숙한 남성 목소리", "gender": "male"},
        "윤아": {"voiceId": "Yoona", "desc": "부드럽고 차분한 여성 목소리", "gender": "female"},
    }
    
    # 모델 옵션
    MODELS = {
        "TTS 1.5 Max (고품질)": "inworld-tts-1.5-max",
        "TTS 1.5 Mini (빠른속도)": "inworld-tts-1.5-mini",
        "TTS 1.0 Max": "inworld-tts-1-max",
        "TTS 1.0": "inworld-tts-1",
    }
    
    def __init__(self):
        self.api_key = self._load_api_key()
    
    def _load_api_key(self):
        """API 키 로드 (Streamlit secrets 우선, 환경변수 대체)"""
        try:
            return st.secrets["INWORLD_API_KEY"]
        except Exception:
            key = os.environ.get("INWORLD_API_KEY", "")
            if not key:
                print("INWORLD_API_KEY가 설정되지 않았습니다.")
            return key
    
    def _headers(self):
        """인증 헤더"""
        return {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def test_connection(self):
        """API 연결 테스트"""
        if not self.api_key:
            return False, "INWORLD_API_KEY가 설정되지 않았습니다."
        try:
            resp = requests.get(self.LIST_VOICES_URL, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                voices = data.get("voices", [])
                return True, f"연결 성공 (음성 {len(voices)}개 확인)"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, f"연결 오류: {str(e)}"
    
    def list_voices(self, language_filter=None):
        """사용 가능한 음성 목록 조회"""
        try:
            resp = requests.get(self.LIST_VOICES_URL, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            voices = data.get("voices", [])
            if language_filter:
                voices = [v for v in voices if language_filter in v.get("languages", [])]
            return voices
        except Exception as e:
            return f"음성 목록 조회 오류: {str(e)}"
    
    def synthesize(self, text, voice_id="Hyunwoo", model_id="inworld-tts-1.5-max",
                   audio_format="MP3", sample_rate=24000, timestamp_type="WORD",
                   speaking_rate=1.0, temperature=1.0):
        """
        텍스트를 음성으로 변환 (비스트리밍)
        
        Returns:
            tuple: (audio_bytes, timestamp_info, error_message)
        """
        if not self.api_key:
            return None, None, "API 키가 설정되지 않았습니다."
        
        # 텍스트 길이 제한 (최대 2000자)
        if len(text) > 2000:
            text = text[:2000]
        
        payload = {
            "text": text,
            "voiceId": voice_id,
            "modelId": model_id,
            "audioConfig": {
                "audioEncoding": audio_format,
                "sampleRateHertz": sample_rate,
                "speakingRate": speaking_rate,
            },
            "temperature": temperature,
            "timestampType": timestamp_type,
        }
        
        try:
            resp = requests.post(
                self.SYNTHESIZE_URL,
                headers=self._headers(),
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            
            # 오디오 디코딩
            audio_b64 = data.get("audioContent", "")
            if not audio_b64:
                return None, None, "오디오 데이터가 비어있습니다."
            
            audio_bytes = base64.b64decode(audio_b64)
            timestamp_info = data.get("timestampInfo", {})
            
            return audio_bytes, timestamp_info, None
            
        except requests.exceptions.HTTPError as e:
            return None, None, f"HTTP 오류: {e.response.status_code} - {e.response.text[:300]}"
        except Exception as e:
            return None, None, f"합성 오류: {str(e)}"
    
    def synthesize_long_text(self, text, voice_id="Hyunwoo", model_id="inworld-tts-1.5-max",
                              audio_format="MP3", sample_rate=24000, speaking_rate=1.0,
                              temperature=1.0):
        """
        긴 텍스트를 여러 청크로 나눠서 합성
        2000자 제한을 자동으로 분할 처리
        
        Returns:
            list of tuples: [(audio_bytes, timestamp_info, chunk_text), ...]
        """
        if not text:
            return []
        
        # 문장 단위로 분할
        sentences = []
        current = ""
        for char in text:
            current += char
            if char in ".?!":
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())
        
        # 2000자 이내의 청크로 묶기
        chunks = []
        current_chunk = ""
        for sent in sentences:
            if len(current_chunk) + len(sent) + 1 > 1900:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sent
            else:
                current_chunk += " " + sent if current_chunk else sent
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        results = []
        for chunk in chunks:
            audio_bytes, ts_info, error = self.synthesize(
                text=chunk,
                voice_id=voice_id,
                model_id=model_id,
                audio_format=audio_format,
                sample_rate=sample_rate,
                timestamp_type="WORD",
                speaking_rate=speaking_rate,
                temperature=temperature,
            )
            if error:
                results.append((None, None, chunk, error))
            else:
                results.append((audio_bytes, ts_info, chunk, None))
        
        return results
    
    def save_audio(self, audio_bytes, filepath):
        """오디오 바이트를 파일로 저장"""
        try:
            directory = os.path.dirname(filepath)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
            return True, filepath
        except Exception as e:
            return False, f"저장 오류: {str(e)}"
    
    def get_korean_voice_id(self, display_name):
        """한글 이름으로 voiceId 조회"""
        voice_info = self.KOREAN_VOICES.get(display_name)
        if voice_info:
            return voice_info["voiceId"]
        # 영문 이름으로도 검색
        for k, v in self.KOREAN_VOICES.items():
            if v["voiceId"].lower() == display_name.lower():
                return v["voiceId"]
        return "Hyunwoo"  # 기본값
