# utils/api_handler.py 수정 (상단에 추가)

import os
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types
from utils.skywork_handler import SkyworkHandler  # 추가


class APIHandler:
    def __init__(self):
        self.gemini_key = ""
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            self.gemini_key = st.secrets["GEMINI_API_KEY"]
        else:
            self.gemini_key = os.getenv("GEMINI_API_KEY", "")

        self.client = None
        self.model = "gemini-2.5-flash"
        if self.gemini_key:
            self.client = genai.Client(api_key=self.gemini_key)
        
        # 스카이워크 핸들러 추가
        self.skywork = SkyworkHandler()

    def test_connection(self):
        """Gemini와 Skywork 모두 테스트"""
        gemini_status = "❌"
        gemini_msg = "설정 안 됨"
        
        if self.client:
            try:
                resp = self.client.models.generate_content(
                    model=self.model,
                    contents="연결 테스트입니다. 확인이라고만 답하세요."
                )
                if resp.text:
                    gemini_status = "✅"
                    gemini_msg = "Gemini 연결 성공"
            except Exception as e:
                gemini_msg = f"Gemini 실패: {e}"
        
        # 스카이워크 테스트
        skywork_ok, skywork_msg = self.skywork.test_connection()
        
        combined_msg = f"{gemini_status} {gemini_msg}\n{skywork_msg}"
        all_ok = self.client is not None and skywork_ok
        
        return all_ok, combined_msg

    def generate(self, prompt, max_tokens=8192, use_skywork=False):
        if use_skywork:
            return self.skywork.generate(prompt, max_tokens=max_tokens)
        
        if not self.client:
            return None, "API 클라이언트가 없습니다"
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.9
                )
            )
            return resp.text, None
        except Exception as e:
            return None, f"생성 실패: {e}"

    def generate_long(self, prompt, use_skywork=False):
        if use_skywork:
            return self.skywork.generate_long(prompt)
        return self.generate(prompt, max_tokens=65000)

    def generate_long_with_search(self, prompt, use_skywork=False):
        if use_skywork:
            return self.skywork.generate_long(prompt)
        
        if not self.client:
            return None, "API 클라이언트가 없습니다"
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=65000,
                    temperature=0.7,
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            return resp.text, None
        except Exception as e:
            return None, f"검색 생성 실패: {e}"

    def generate_serial(self, prompts_list, progress_callback=None, use_skywork=False):
        if not self.client and not use_skywork:
            return None, "API 클라이언트가 없습니다"
        
        all_parts = []
        for i, prompt in enumerate(prompts_list):
            try:
                if use_skywork:
                    resp, error = self.skywork.generate(prompt, max_tokens=8000)
                    if error:
                        return None, f"{i+1}번째 파트 생성 실패: {error}"
                else:
                    resp = self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            max_output_tokens=65000,
                            temperature=0.9
                        )
                    )
                    resp = resp.text
                
                if resp:
                    all_parts.append(resp)
                if progress_callback:
                    progress_callback(i + 1, len(prompts_list))
            except Exception as e:
                return None, f"{i+1}번째 파트 생성 실패: {e}"
        
        return "\n\n".join(all_parts), None
