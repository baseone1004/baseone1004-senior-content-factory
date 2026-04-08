# ============================================================
# 내보내기 핸들러
# 생성된 콘텐츠를 다양한 형태로 내보내기
# ============================================================

import json
from datetime import datetime


class ExportHandler:
    """콘텐츠 내보내기 처리"""

    @staticmethod
    def to_text(content, title=""):
        """텍스트 파일 형태로 변환"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        header = f"시니어 콘텐츠 팩토리 출력물\n"
        header += f"생성 일시: {timestamp}\n"
        if title:
            header += f"주제: {title}\n"
        header += "=" * 60 + "\n\n"
        return header + content

    @staticmethod
    def extract_shorts_scripts(full_output):
        """쇼츠 10편 출력물에서 순수 대본만 추출"""
        scripts = []
        current_script = ""
        current_title = ""
        in_script = False

        for line in full_output.split("\n"):
            line = line.strip()

            # 편 번호 감지
            if line.startswith("=") and line.endswith("=") and len(line) <= 7:
                if current_script and current_title:
                    scripts.append({
                        "title": current_title,
                        "script": current_script.strip()
                    })
                current_script = ""
                current_title = ""
                in_script = False

            # 제목 감지
            if line.startswith("제목:"):
                current_title = line.replace("제목:", "").strip()

            # 순수 대본 감지
            if line.startswith("순수 대본:"):
                in_script = True
                remaining = line.replace("순수 대본:", "").strip()
                if remaining:
                    current_script = remaining
                continue

            # 장면 시작이면 순수 대본 영역 종료
            if line.startswith("=장면"):
                in_script = False
                continue

            if in_script and line:
                current_script += " " + line

        # 마지막 편 처리
        if current_script and current_title:
            scripts.append({
                "title": current_title,
                "script": current_script.strip()
            })

        return scripts

    @staticmethod
    def extract_image_prompts(full_output):
        """쇼츠 출력물에서 이미지 프롬프트만 추출"""
        prompts = []
        current_episode = ""

        for line in full_output.split("\n"):
            line = line.strip()

            if line.startswith("=") and line.endswith("=") and len(line) <= 7:
                current_episode = line

            if line.startswith("프롬프트:"):
                prompt_text = line.replace("프롬프트:", "").strip()
                prompts.append({
                    "episode": current_episode,
                    "prompt": prompt_text
                })

        return prompts

    @staticmethod
    def format_for_tts(script_text):
        """음성 변환용 포맷으로 정리"""
        # 마침표 기준으로 문장 분리
        sentences = []
        for sentence in script_text.split("."):
            sentence = sentence.strip()
            if sentence:
                sentences.append(sentence + ".")
        return "\n".join(sentences)

    @staticmethod
    def generate_pinned_comment(longform_title, longform_link_placeholder="[롱폼 영상 링크]"):
        """고정댓글 템플릿 생성"""
        comment = f"이 내용이 더 궁금하시다면\n"
        comment += f"'{longform_title}'에서\n"
        comment += f"모든 이야기를 풀어놓았습니다\n"
        comment += f"{longform_link_placeholder}\n\n"
        comment += f"여러분의 소중한 시간이\n"
        comment += f"낭비되지 않도록\n"
        comment += f"핵심만 담았습니다"
        return comment
