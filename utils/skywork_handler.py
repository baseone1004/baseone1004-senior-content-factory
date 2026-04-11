# utils/skywork_handler.py
import os
import requests
from typing import Tuple, List, Dict
import json
import streamlit as st


class SkyworkHandler:
    """스카이워크 API 핸들러"""
    
    def __init__(self):
        # Streamlit secrets 또는 환경변수에서 API 키 가져오기
        self.api_key = ""
        if hasattr(st, "secrets") and "SKYWORK_API_KEY" in st.secrets:
            self.api_key = st.secrets["SKYWORK_API_KEY"]
        else:
            self.api_key = os.getenv("SKYWORK_API_KEY", "")
        
        self.base_url = "https://api.skywork.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.model = "Skywork-Qwen-72B-MAGAmax"
    
    def test_connection(self) -> Tuple[bool, str]:
        """스카이워크 API 연결 테스트"""
        if not self.api_key:
            return False, "❌ 스카이워크 API 키가 설정되지 않았습니다"
        
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "안녕하세요"}
                ],
                "max_tokens": 10,
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                return True, "✅ 스카이워크 API 연결 성공"
            elif response.status_code == 401:
                return False, "❌ API 키 인증 실패 (유효하지 않은 키)"
            elif response.status_code == 429:
                return False, "❌ 요청 한도 초과"
            else:
                return False, f"❌ 연결 실패: HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "❌ 연결 시간 초과"
        except requests.exceptions.ConnectionError:
            return False, "❌ 네트워크 연결 실패"
        except Exception as e:
            return False, f"❌ 연결 오류: {str(e)}"
    
    def generate(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> Tuple[str, str]:
        """스카이워크 AI로 텍스트 생성"""
        if not self.api_key:
            return None, "스카이워크 API 키가 설정되지 않았습니다"
        
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가입니다."
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.95
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    return content, None
                else:
                    return None, "응답 내용이 비어있습니다"
            else:
                error_detail = response.text
                return None, f"API 오류: HTTP {response.status_code} - {error_detail}"
                
        except requests.exceptions.Timeout:
            return None, "요청 시간 초과 (60초)"
        except requests.exceptions.ConnectionError:
            return None, "네트워크 연결 실패"
        except json.JSONDecodeError:
            return None, "응답 파싱 실패"
        except Exception as e:
            return None, f"생성 오류: {str(e)}"
    
    def generate_long(self, prompt: str) -> Tuple[str, str]:
        """긴 텍스트 생성 (최대 토큰)"""
        return self.generate(prompt, max_tokens=8000, temperature=0.8)
    
    def generate_shorts_10_set(self, main_topic: str) -> Tuple[str, str]:
        """쇼츠 10편 세트 생성"""
        prompt = f"""당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가야.

【대주제】
{main_topic}

【역할】
하나의 대주제를 받으면 그 주제에서 파생되는 연관성 높고 중복 없는 쇼츠 십 편을 세트로 기획하고 각 편마다 대본과 이미지 프롬프트를 완성해.

【세트 기획 규칙】
하나의 대주제에서 십 개의 소주제를 도출한다. 십 개의 소주제는 반드시 서로 중복되지 않아야 한다. 각 소주제는 대주제와 연관성이 높아야 한다.

소주제 도출 방식은 아래 여덟 가지 관점에서 골고루 뽑는다:

1. 몰락 원인 분석 - 왜 망했는가
2. 전성기 실태 - 가장 잘 나가던 시절
3. 내부 폭로 - 업계 종사자만 아는 비밀
4. 비교 분석 - 비슷한 업종끼리 뭐가 다른가
5. 수익 구조 - 돈은 어떻게 벌었는가
6. 피해자 시점 - 누가 가장 큰 피해를 입었는가
7. 현재 상황 - 지금은 어떻게 변했는가
8. 미래 전망 - 앞으로 어떻게 될 것인가

십 개를 채울 때 위 여덟 관점에서 최소 하나씩 뽑고 나머지 둘은 가장 흥미로운 관점에서 추가한다.

【각 쇼츠 편별 출력 형식】

=001=

제목: (숫자는 아라비아 숫자 표기. 오십 자 이내)

상단제목 첫째 줄: (십오 자 이내)
상단제목 둘째 줄: (십오 자 이내)

설명글: (약 이백 자. 해시태그 삼 개에서 다섯 개 포함)

태그: (쉼표로 구분. 십오 개에서 이십 개)

순수 대본: (문장만 마침표로 나열한다. 앞에 대본이라는 단어를 쓰지 않는다. 편 번호를 쓰지 않는다. 대사 번호를 쓰지 않는다. 최소 팔 문장 최대 십오 문장)

이미지 프롬프트: SD 2D anime style, (장면 묘사), 9:16 vertical aspect ratio (각 문장마다 하나씩 생성)

【백만 조회수 대본 핵심 원칙】

원칙 하나. 일초 법칙. 첫 문장이 곧 생사다. 첫 문장은 반드시 현장 한가운데에 시청자를 던져 넣는 문장이어야 한다. 날짜로 시작하지 않는다. 정의로 시작하지 않는다. 인사로 시작하지 않는다.

원칙 둘. 삼초 궁금증 폭탄. 처음 세 문장 안에 열린 고리를 건다.

원칙 셋. 근데의 힘. 접속사로 긴장을 조절한다. 사용해야 하는 접속사는 근데 그래서 결국 알고 보니 문제는이다.

원칙 넷. 한 문장 한 호흡. 쇼츠 한 문장의 최적 길이는 열다섯 자에서 마흔 자 사이다.

원칙 다섯. 번호 매기기 금지. 하나의 이야기 흐름으로 이어간다.

원칙 여섯. 습니다 까요 혼합체. 습니다체를 기본으로 깔되 중간중간 까요체로 질문을 던진다.

원칙 일곱. 감정 곡선 설계. 충격으로 시작하고 공감으로 끌어당기고 분노 또는 안타까움으로 몰입시키고 반전으로 뒤집고 여운으로 마무리한다.

원칙 여덟. 중간 고리. 오 초마다 새로운 미끼를 던진다.

원칙 아홉. 마무리. 묵직한 여운형은 지금도 이 구조는 바뀌지 않았습니다처럼 시청자를 멍하게 만든다.

원칙 열. 반복 시청 유도. 마지막 문장의 끝이 첫 문장의 시작과 자연스럽게 이어지게 만든다.

지금부터 위 모든 규칙을 완벽히 따르면서 쇼츠 10편 세트를 만들어줘."""
        
        return self.generate_long(prompt)
    
    def optimize_script(self, script: str) -> Tuple[str, str]:
        """대본 최적화"""
        prompt = f"""당신은 유튜브 쇼츠 대본 최적화 전문가입니다.

다음 대본을 이 규칙에 따라 최적화하세요:

1. 번호 매기기 제거 (첫 번째, 두 번째, 1번, 2번 등 모두)
2. 반복 표현 제거 및 다양한 표현 사용
3. 첫 문장을 더 임팩트있게 강화 (현장감 있는 묘사로 시작)
4. 구어체 사용 극대화 (습니다체와 까요체 혼합)
5. 한 문장을 15-40자 사이로 유지
6. 같은 감정이 3문장 연속으로 나오지 않도록 조정
7. 접속사를 "근데", "그래서", "결국", "알고 보니"로 통일
8. 마지막 문장이 첫 번째 문장으로 자연스럽게 이어지도록 (반복 시청 유도)
9. 마침표만 사용 (느낌표, 물음표 반복 금지)

원본 대본:
{script}

최적화된 대본만 출력하세요. 추가 설명이나 주석은 없습니다."""
        
        return self.generate_long(prompt)
    
    def generate_image_prompts(self, script_lines: List[str]) -> Tuple[Dict[int, str], str]:
        """각 대본 라인에 대한 이미지 프롬프트 생성"""
        try:
            prompts_dict = {}
            
            for i, line in enumerate(script_lines):
                if not line.strip():
                    continue
                
                img_prompt = f"""당신은 Stable Diffusion (SD) 이미지 생성용 프롬프트 전문가입니다.

다음 유튜브 쇼츠 대본 텍스트에 맞는 이미지를 생성하기 위한 SD 프롬프트를 작성하세요.

텍스트: "{line}"

프롬프트 작성 규칙:
1. 반드시 "SD 2D anime style,"로 시작
2. 장면을 구체적으로 영어로 묘사 (50-100단어)
3. 반드시 "9:16 vertical aspect ratio"로 끝남
4. 특수기호 없음
5. 애니메이션 스타일의 생생한 장면 묘사

예시:
SD 2D anime style, a shocked person with wide eyes in a dark office, sweat drops on face, neon lighting, dramatic atmosphere, 9:16 vertical aspect ratio

프롬프트만 출력하세요. 추가 설명 없음."""
                
                result, error = self.generate(img_prompt, max_tokens=500, temperature=0.6)
                if error:
                    # 오류 시 기본 프롬프트 사용
                    prompts_dict[i] = f"SD 2D anime style, {line[:50]}, dramatic scene, 9:16 vertical aspect ratio"
                else:
                    prompts_dict[i] = result.strip()
            
            return prompts_dict, None
            
        except Exception as e:
            return None, f"이미지 프롬프트 생성 오류: {str(e)}"
