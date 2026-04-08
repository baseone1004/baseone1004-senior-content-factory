import os
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types


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

    def test_connection(self):
        if not self.client:
            return False, "API 키가 설정되지 않았습니다"
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents="연결 테스트입니다. 확인이라고만 답하세요."
            )
            if resp.text:
                return True, "연결 성공"
            return False, "응답이 비어있습니다"
        except Exception as e:
            return False, f"연결 실패: {e}"

    def generate(self, prompt, max_tokens=8192):
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

    def generate_long(self, prompt):
        return self.generate(prompt, max_tokens=65000)

    def generate_long_with_search(self, prompt):
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

    def generate_serial(self, prompts_list, progress_callback=None):
        if not self.client:
            return None, "API 클라이언트가 없습니다"
        all_parts = []
        for i, prompt in enumerate(prompts_list):
            try:
                resp = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=65000,
                        temperature=0.9
                    )
                )
                if resp.text:
                    all_parts.append(resp.text)
                if progress_callback:
                    progress_callback(i + 1, len(prompts_list))
            except Exception as e:
                return None, f"{i+1}번째 파트 생성 실패: {e}"
        return "\n\n".join(all_parts), None
