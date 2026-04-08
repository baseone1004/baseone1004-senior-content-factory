import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

class APIHandler:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.client = None
        self.model = "gemini-2.5-flash"
        if self.gemini_key:
            self.client = genai.Client(api_key=self.gemini_key)

    def test_connection(self):
        if not self.client:
            return False, "API 키가 설정되지 않았습니다"
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents="연결 테스트입니다. 확인이라고만 답하세요."
            )
            if response.text:
                return True, "연결 성공"
            return False, "응답이 비어있습니다"
        except Exception as e:
            return False, f"연결 실패: {str(e)}"

    def generate(self, prompt, max_tokens=8192):
        if not self.client:
            return None, "API 클라이언트가 없습니다"
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.9
                )
            )
            return response.text, None
        except Exception as e:
            return None, f"생성 실패: {str(e)}"

    def generate_with_search(self, prompt, max_tokens=8192):
        if not self.client:
            return None, "API 클라이언트가 없습니다"
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.7,
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            return response.text, None
        except Exception as e:
            return None, f"검색 생성 실패: {str(e)}"

    def generate_long(self, prompt):
        return self.generate(prompt, max_tokens=65000)

    def generate_long_with_search(self, prompt):
        return self.generate_with_search(prompt, max_tokens=65000)
