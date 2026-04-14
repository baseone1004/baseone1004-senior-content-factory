import streamlit as st
import requests
import json
import os
import re
import time
import base64
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="시니어 콘텐츠 공장 v5.0", layout="wide")

# ═══════════════════════════════════════════
# API 키 로드
# ═══════════════════════════════════════════
def load_key(name):
    v = os.environ.get(name, "")
    if not v:
        try:
            v = st.secrets.get(name, "")
        except Exception:
            v = ""
    return v.strip() if v else ""

GEMINI_API_KEY = load_key("GEMINI_API_KEY")
INWORLD_API_KEY = load_key("INWORLD_API_KEY")

# ═══════════════════════════════════════════
# Inworld TTS 한국어 음성 목록
# ═══════════════════════════════════════════
VOICE_OPTIONS = {
    "서윤 (한국어 여성)": "서윤",
    "Hyunwoo (한국어 남성)": "Hyunwoo",
    "Minji (한국어 여성)": "Minji",
    "Seojun (한국어 남성)": "Seojun",
    "Yoona (한국어 여성)": "Yoona",
}

# ═══════════════════════════════════════════
# 폰트 설정
# ═══════════════════════════════════════════
FONT_MAP = {
    "나눔고딕": "NanumGothic",
    "나눔고딕 볼드": "NanumGothicBold",
    "나눔명조": "NanumMyeongjo",
    "나눔명조 볼드": "NanumMyeongjoBold",
    "나눔바른고딕": "NanumBarunGothic",
    "나눔스퀘어": "NanumSquare",
    "나눔스퀘어 볼드": "NanumSquareBold",
    "나눔바른펜": "NanumBarunpen",
    "나눔브러쉬": "NanumBrush",
    "나눔손글씨 펜": "NanumPen",
    "배달의민족 주아": "BMJUA",
    "배달의민족 한나": "BMHanna",
    "배달의민족 도현": "BMDoHyeon",
    "블랙한산스": "BlackHanSans",
    "이사만루 볼드": "East Sea Dokdo",
    "송명체": "Song Myung",
    "감자꽃마을": "Gamja Flower",
    "검은고딕": "Black And White Picture",
    "고딕 A1": "Gothic A1",
    "도현체": "Do Hyeon",
}
FONT_LIST = list(FONT_MAP.keys())

# ═══════════════════════════════════════════
# 자막 기본 스타일
# ═══════════════════════════════════════════
DEFAULT_SUB_LONG = {
    "font": "나눔고딕 볼드",
    "size": 28,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 2,
    "position": "하단",
    "offset_up": 0,
    "offset_down": 0,
    "offset_left": 0,
    "offset_right": 0,
    "bg_opacity": 0.5,
}
DEFAULT_SUB_SHORTS = {
    "font": "배달의민족 주아",
    "size": 36,
    "color": "#FFFF00",
    "outline_color": "#000000",
    "outline_width": 3,
    "position": "중앙",
    "offset_up": 0,
    "offset_down": 0,
    "offset_left": 0,
    "offset_right": 0,
    "bg_opacity": 0.0,
}

# ═══════════════════════════════════════════
# 세션 상태 초기화
# ═══════════════════════════════════════════
defaults = {
    "selected_topic": "",
    "selected_category": "경제/사회",
    "script_text": "",
    "script_lines": [],
    "uploaded_videos": [],
    "tts_audio_data": [],
    "tts_durations": [],
    "subtitle_style_long": dict(DEFAULT_SUB_LONG),
    "subtitle_style_shorts": dict(DEFAULT_SUB_SHORTS),
    "reference_image": None,
    "content_type": "쇼츠",
    "topic_recommendations": "",
    "news_data": "",
    "selected_topic_data": {},
    "auto_script_result": "",
    "srt_content": "",
    "final_video": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════
def clean_special(text):
    if not text:
        return ""
    text = re.sub(r'[*#_~`>|{}\[\]]', '', text)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned.append(line)
    return '\n'.join(cleaned)


def clean_script(text):
    if not text:
        return ""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'[*#_~`>|{}\[\]]', '', text)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        sentences = re.split(r'(?<=[.?])\s+', line)
        for s in sentences:
            s = s.strip()
            if s and len(s) > 2:
                cleaned.append(s)
    return '\n'.join(cleaned)


def safe_generate(prompt, system_prompt="", max_tokens=4096):
    if not GEMINI_API_KEY:
        return "오류: GEMINI_API_KEY가 설정되지 않았습니다."
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    parts = []
    if system_prompt:
        parts.append({"text": f"[System] {system_prompt}"})
    parts.append({"text": prompt})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.8,
        }
    }
    last_error = ""
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=120)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts_out = content.get("parts", [])
                        if parts_out:
                            return parts_out[0].get("text", "")
                    return "오류: Gemini API 응답에 결과가 없습니다."
                elif resp.status_code == 429:
                    last_error = f"할당량 초과 (모델: {model}, 시도: {attempt+1}/3)"
                    wait_time = (attempt + 1) * 10
                    time.sleep(wait_time)
                    continue
                elif resp.status_code == 404:
                    last_error = f"모델 없음 (모델: {model})"
                    break
                else:
                    last_error = f"Gemini API 응답 {resp.status_code} (모델: {model})"
                    break
            except requests.exceptions.Timeout:
                last_error = f"시간 초과 (모델: {model})"
                break
            except requests.exceptions.ConnectionError:
                last_error = f"연결 실패 (모델: {model})"
                break
            except Exception as e:
                last_error = f"{str(e)} (모델: {model})"
                break
    return f"오류: 모든 모델에서 실패했습니다. 마지막 오류: {last_error}"


def inworld_tts(text, voice_id="서윤", model_id="inworld-tts-1.5-max"):
    if not INWORLD_API_KEY:
        return None, "오류: INWORLD_API_KEY가 설정되지 않았습니다."
    url = "https://api.inworld.ai/tts/v1/voice"
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "text": text[:2000],
        "voiceId": voice_id,
        "modelId": model_id,
        "audioConfig": {
            "audioEncoding": "MP3",
            "sampleRateHertz": 24000,
        }
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=("", INWORLD_API_KEY),
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            audio_b64 = data.get("audioContent", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                return audio_bytes, None
            return None, "오류: 응답에 audioContent가 없습니다."
        else:
            return None, f"오류: Inworld API {resp.status_code} - {resp.text[:200]}"
    except Exception as e:
        return None, f"오류: {str(e)}"


def get_audio_duration(audio_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", tmp_path],
            capture_output=True, text=True, timeout=10
        )
        os.unlink(tmp_path)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return max(len(audio_bytes) / 16000, 1.0)


def generate_srt(lines, durations):
    srt = ""
    current_time = 0.0
    for i, line in enumerate(lines):
        dur = durations[i] if i < len(durations) else 3.0
        start_h = int(current_time // 3600)
        start_m = int((current_time % 3600) // 60)
        start_s = int(current_time % 60)
        start_ms = int((current_time % 1) * 1000)
        end_time = current_time + dur
        end_h = int(end_time // 3600)
        end_m = int((end_time % 3600) // 60)
        end_s = int(end_time % 60)
        end_ms = int((end_time % 1) * 1000)
        srt += f"{i+1}\n"
        srt += f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> "
        srt += f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}\n"
        srt += f"{line.strip()}\n\n"
        current_time = end_time
    return srt


def merge_video_audio_subtitle(video_bytes, audio_bytes_list, srt_content, sub_style):
    try:
        work_dir = tempfile.mkdtemp()
        video_path = os.path.join(work_dir, "input_video.mp4")
        audio_path = os.path.join(work_dir, "combined_audio.mp3")
        srt_path = os.path.join(work_dir, "subtitles.srt")
        output_path = os.path.join(work_dir, "final_output.mp4")

        with open(video_path, "wb") as f:
            f.write(video_bytes)

        concat_list_path = os.path.join(work_dir, "audio_list.txt")
        audio_files = []
        for i, ab in enumerate(audio_bytes_list):
            ap = os.path.join(work_dir, f"audio_{i:04d}.mp3")
            with open(ap, "wb") as f:
                f.write(ab)
            audio_files.append(ap)

        with open(concat_list_path, "w") as f:
            for ap in audio_files:
                f.write(f"file '{ap}'\n")

        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_list_path, "-c", "copy", audio_path],
            capture_output=True, timeout=120
        )

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        font_name = FONT_MAP.get(sub_style.get("font", "나눔고딕 볼드"), "NanumGothicBold")
        font_size = sub_style.get("size", 28)
        font_color = sub_style.get("color", "#FFFFFF").replace("#", "&H00") 
        outline_color = sub_style.get("outline_color", "#000000").replace("#", "&H00")
        outline_width = sub_style.get("outline_width", 2)

        pos = sub_style.get("position", "하단")
        if pos == "상단":
            alignment = 8
            margin_v = 30
        elif pos == "중앙":
            alignment = 5
            margin_v = 0
        else:
            alignment = 2
            margin_v = 30

        subtitle_filter = (
            f"subtitles={srt_path}:force_style='"
            f"FontName={font_name},"
            f"FontSize={font_size},"
            f"PrimaryColour={font_color},"
            f"OutlineColour={outline_color},"
            f"Outline={outline_width},"
            f"Alignment={alignment},"
            f"MarginV={margin_v}'"
        )

        subprocess.run(
            ["ffmpeg", "-y",
             "-i", video_path,
             "-i", audio_path,
             "-vf", subtitle_filter,
             "-c:v", "libx264", "-preset", "fast", "-crf", "23",
             "-c:a", "aac", "-b:a", "192k",
             "-shortest",
             output_path],
            capture_output=True, timeout=300
        )

        if os.path.exists(output_path):
            with open(output_path, "rb") as f:
                result = f.read()
            shutil.rmtree(work_dir, ignore_errors=True)
            return result, None
        else:
            shutil.rmtree(work_dir, ignore_errors=True)
            return None, "오류: 최종 영상 생성 실패"
    except Exception as e:
        return None, f"오류: {str(e)}"


# ═══════════════════════════════════════════
# 사이드바
# ═══════════════════════════════════════════
with st.sidebar:
    st.header("설정")
    st.subheader("API 연결 상태")
    if GEMINI_API_KEY:
        st.success("Gemini API: 연결됨")
    else:
        st.error("Gemini API: 키 없음")
    if INWORLD_API_KEY:
        st.success("Inworld TTS: 연결됨")
    else:
        st.error("Inworld TTS: 키 없음")
    st.divider()
    st.subheader("레퍼런스 이미지")
    ref_upload = st.file_uploader("주인공 참고 이미지", type=["png", "jpg", "jpeg", "webp"], key="ref_img_upload")
    if ref_upload:
        st.session_state["reference_image"] = ref_upload.getvalue()
        st.image(ref_upload, caption="레퍼런스 이미지", width=200)
    elif st.session_state.get("reference_image"):
        st.image(st.session_state["reference_image"], caption="레퍼런스 이미지", width=200)
    st.divider()
    st.subheader("콘텐츠 유형")
    st.session_state["content_type"] = st.radio(
        "유형 선택", ["쇼츠", "롱폼"],
        index=0 if st.session_state.get("content_type", "쇼츠") == "쇼츠" else 1,
        key="content_type_radio"
    )

st.title("시니어 콘텐츠 공장 v5.0")
st.caption("주제추천 → 대본 → 영상업로드 → TTS음성 → 자막편집 → 최종합치기")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. 주제 추천",
    "2. 대본 입력",
    "3. 영상 업로드",
    "4. TTS 음성",
    "5. 자막 편집",
    "6. 최종 합치기",
])

# ═══════════════════════════════════════════
# 탭1: 주제 추천
# ═══════════════════════════════════════════
with tab1:
    st.header("주제 추천")
    st.info("카테고리를 선택하면 최신 뉴스를 검색하고, Gemini가 떡상 확률과 함께 10개 주제를 추천합니다.")

    categories = [
        "경제/사회", "부동산", "창업/자영업", "노동/일자리",
        "유흥/향락산업", "먹거리/외식", "범죄/사건사고",
        "심리학", "자기계발"
    ]

    selected_cat = st.selectbox(
        "카테고리 선택",
        categories,
        index=categories.index(st.session_state.get("selected_category", "경제/사회")) if st.session_state.get("selected_category", "경제/사회") in categories else 0,
        key="cat_select"
    )
    st.session_state["selected_category"] = selected_cat

    if st.button("주제 추천 받기", key="btn_recommend", use_container_width=True):
        if not GEMINI_API_KEY:
            st.error("Gemini API 키가 설정되지 않았습니다.")
        else:
            with st.spinner("최신 뉴스를 검색하고 있습니다..."):
                news_search_prompt = f"""당신은 한국 뉴스 전문 리서처입니다.

"{selected_cat}" 카테고리에서 지금 한국에서 가장 화제가 되고 있는 최신 뉴스와 이슈를 15개 찾아주세요.

반드시 포함할 소스:
- 구글 뉴스 한국
- 네이버 뉴스
- 연합뉴스
- 한국경제/매일경제/조선일보 경제면
- 유튜브 인기 채널

각 뉴스마다 아래 형식으로 작성하세요:
뉴스1: (제목) / 출처: (언론사) / 핵심: (한 줄 요약)

가능한 한 최근 1주일 이내 뉴스를 우선하세요.
2026년 4월 현재 한국의 주요 이슈를 반영하세요."""

                news_result = safe_generate(news_search_prompt)

            with st.spinner("뉴스를 분석하고 주제를 추천 중입니다..."):
                content_label = st.session_state.get("content_type", "쇼츠")
                topic_prompt = f"""당신은 유튜브 {content_label} 백만 조회수 전문 기획자입니다.

아래는 "{selected_cat}" 카테고리의 최신 뉴스입니다:

{news_result}

위 뉴스를 바탕으로, 유튜브 {content_label}로 만들면 조회수가 폭발할 주제 10개를 추천하세요.

반드시 아래 JSON 형식으로만 출력하세요. 다른 텍스트는 절대 쓰지 마세요:

[
  {{
    "번호": 1,
    "주제": "유튜브 제목 (20~25자)",
    "출처뉴스": "참고한 뉴스 제목",
    "떡상확률": 85,
    "이유": "왜 이 주제가 떡상할지 한 줄 설명",
    "추천태그": "태그1, 태그2, 태그3",
    "난이도": "쉬움"
  }},
  ...
]

제목 작성 필수 규칙:
1. 주제는 반드시 20자~25자 사이로 작성. 19자 이하나 26자 이상은 절대 금지
2. 유튜브 썸네일과 제목에 바로 쓸 수 있는 완성된 한 줄 제목
3. 시청자가 클릭하지 않고는 못 배기는 자극적 제목으로 작성
4. 제목 기법 반드시 활용: 숫자 넣기, 의문형, 충격 단어, 비교형, 경고형
5. 한 제목에 위 기법을 2개 이상 조합

기타 규칙:
6. 떡상확률은 50~95 사이 숫자로 현실적으로 판단
7. 이유는 30자 이내
8. 난이도는 "쉬움", "보통", "어려움" 중 택1
9. 10개 주제는 서로 겹치지 않아야 함
10. 최신 뉴스와 직접 연관된 주제 우선
11. 추천태그는 3~5개
12. 떡상확률 높은 순서로 정렬

나쁜 예시 (너무 짧음): "유가 상승 영향" (7자) → 금지
나쁜 예시 (너무 김): "중동 전쟁으로 인한 국제 유가 급등이 한국 경제에 미치는 충격적 영향" (32자) → 금지
좋은 예시: "유가 백달러 돌파 당신 지갑이 위험한 세가지 이유" (23자) → 적합
좋은 예시: "자영업자 절반이 빚더미 이 구조가 소름 돋는다" (22자) → 적합"""

                topic_result = safe_generate(topic_prompt, max_tokens=6000)

                if topic_result.startswith("오류:"):
                    st.error(topic_result)
                else:
                    st.session_state["topic_recommendations"] = topic_result
                    st.session_state["news_data"] = news_result
                    st.success("주제 추천 완료!")

    if st.session_state.get("topic_recommendations"):
        with st.expander("참고한 최신 뉴스 원문 보기"):
            st.text(clean_special(st.session_state.get("news_data", "")))

        st.divider()
        st.subheader("추천 주제 TOP 10")

        raw = st.session_state["topic_recommendations"]
        cleaned_raw = raw.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
        json_match = re.search(r'\[.*\]', cleaned_raw, re.DOTALL)

        topics_parsed = None
        if json_match:
            try:
                topics_parsed = json.loads(json_match.group())
            except json.JSONDecodeError:
                topics_parsed = None

        if topics_parsed and isinstance(topics_parsed, list):
            for item in topics_parsed:
                num = item.get("번호", "")
                title = item.get("주제", "")
                source = item.get("출처뉴스", "")
                prob = item.get("떡상확률", 0)
                reason = item.get("이유", "")
                tags = item.get("추천태그", "")
                diff = item.get("난이도", "보통")

                if prob >= 85:
                    prob_color = "#FF4444"
                    prob_emoji = "🔥"
                    border_color = "#FF4444"
                elif prob >= 70:
                    prob_color = "#FF8800"
                    prob_emoji = "⚡"
                    border_color = "#FF8800"
                else:
                    prob_color = "#44AA44"
                    prob_emoji = "💡"
                    border_color = "#44AA44"

                diff_colors = {"쉬움": "#44CC44", "보통": "#FFAA00", "어려움": "#FF4444"}
                diff_color = diff_colors.get(diff, "#FFAA00")

                st.markdown(
                    f"""<div style="border:2px solid {border_color}; border-radius:12px; padding:16px; margin:8px 0; background:#1a1a2e;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:20px; font-weight:bold; color:#FFFFFF;">{prob_emoji} {num}. {title}</span>
                            <span style="font-size:24px; font-weight:bold; color:{prob_color};">떡상 {prob}%</span>
                        </div>
                        <div style="margin:6px 0;">
                            <span style="background:#333; padding:3px 10px; border-radius:20px; font-size:12px; color:#AAA;">출처: {source}</span>
                            <span style="background:{diff_color}22; padding:3px 10px; border-radius:20px; font-size:12px; color:{diff_color}; margin-left:6px;">난이도: {diff}</span>
                        </div>
                        <div style="color:#CCCCCC; font-size:14px; margin:8px 0;">{reason}</div>
                        <div style="color:#888888; font-size:12px;">태그: {tags}</div>
                    </div>""",
                    unsafe_allow_html=True
                )

            st.divider()
            topic_options = [f"{item.get('번호', '')}. {item.get('주제', '')} (떡상 {item.get('떡상확률', 0)}%)" for item in topics_parsed]
            selected_topic_idx = st.selectbox("제작할 주제를 선택하세요", topic_options, key="topic_select_dropdown")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("이 주제로 결정", key="btn_set_topic", use_container_width=True):
                    idx = int(selected_topic_idx.split(".")[0]) - 1
                    if 0 <= idx < len(topics_parsed):
                        chosen = topics_parsed[idx]
                        st.session_state["selected_topic"] = chosen.get("주제", "")
                        st.session_state["selected_topic_data"] = chosen
                        st.success(f"주제가 결정되었습니다: {chosen.get('주제', '')}")
            with col_btn2:
                custom_topic = st.text_input("또는 직접 주제 입력", key="custom_topic_input")
                if st.button("직접 입력한 주제로 결정", key="btn_custom_topic"):
                    if custom_topic.strip():
                        st.session_state["selected_topic"] = custom_topic.strip()
                        st.session_state["selected_topic_data"] = {}
                        st.success(f"주제가 결정되었습니다: {custom_topic.strip()}")
        else:
            st.markdown(f"```\n{clean_special(raw)}\n```")
            topic_input = st.text_input("위 추천 중 사용할 주제를 입력하세요", key="topic_input_fallback")
            if st.button("이 주제로 결정", key="btn_set_topic_fallback"):
                if topic_input.strip():
                    st.session_state["selected_topic"] = topic_input.strip()
                    st.success(f"주제가 결정되었습니다: {topic_input.strip()}")

    if st.session_state.get("selected_topic"):
        st.divider()
        selected_data = st.session_state.get("selected_topic_data", {})
        info_line = ""
        if selected_data:
            info_line = f"""<div style="font-size:14px; color:#AAAAAA;">떡상확률: <span style="color:#FF4444; font-weight:bold;">{selected_data.get("떡상확률", "")}%</span> | 난이도: {selected_data.get("난이도", "")} | 태그: {selected_data.get("추천태그", "")}</div>"""
        st.markdown(
            f"""<div style="border:3px solid #4CAF50; border-radius:12px; padding:20px; background:#0a2e0a; text-align:center;">
                <div style="font-size:14px; color:#88CC88;">현재 선택된 주제</div>
                <div style="font-size:24px; font-weight:bold; color:#FFFFFF; margin:10px 0;">{st.session_state['selected_topic']}</div>
                {info_line}
                <div style="font-size:13px; color:#888888; margin-top:10px;">이 주제로 탭2에서 대본을 생성하거나 붙여넣으세요.</div>
            </div>""",
            unsafe_allow_html=True
        )

# ═══════════════════════════════════════════
# 탭2: 대본 입력
# ═══════════════════════════════════════════
with tab2:
    st.header("대본 입력")

    if st.session_state.get("selected_topic"):
        st.markdown(
            f"""<div style="border:2px solid #4CAF50; border-radius:8px; padding:12px; background:#0a2e0a; margin-bottom:16px;">
                <span style="color:#88CC88; font-size:13px;">현재 주제:</span>
                <span style="color:#FFFFFF; font-size:16px; font-weight:bold; margin-left:8px;">{st.session_state['selected_topic']}</span>
            </div>""",
            unsafe_allow_html=True
        )
    else:
        st.warning("탭1에서 먼저 주제를 선택해주세요.")

    script_mode = st.radio(
        "대본 작성 방법",
        ["Gemini 자동 생성", "Skywork 대본 붙여넣기"],
        horizontal=True,
        key="script_mode"
    )

    st.divider()

    if script_mode == "Gemini 자동 생성":
        st.subheader("Gemini 자동 대본 생성")
        st.caption("선택한 주제를 기반으로 Gemini가 사실 기반 대본을 자동 생성합니다.")

        content_type = st.session_state.get("content_type", "쇼츠")

        col_opt1, col_opt2, col_opt3 = st.columns(3)
        with col_opt1:
            if content_type == "쇼츠":
                num_episodes = st.slider("생성할 편 수", 1, 10, 1, key="num_episodes")
            else:
                num_episodes = 1
                st.info("롱폼은 1편씩 생성합니다.")
        with col_opt2:
            tone = st.selectbox("톤 선택", [
                "충격/폭로형", "분석/해설형", "공감/스토리형", "비교/대조형", "미래전망형"
            ], key="tone_select")
        with col_opt3:
            duration = st.selectbox("영상 길이", [
                "30분 분량", "45분 분량", "1시간 분량"
            ], key="duration_select")

        dur_map = {
            "30분 분량": {"minutes": 30, "label": "250~300문장 / 약 12000자", "parts": 6},
            "45분 분량": {"minutes": 45, "label": "380~450문장 / 약 18000자", "parts": 9},
            "1시간 분량": {"minutes": 60, "label": "500~600문장 / 약 24000자", "parts": 12},
        }
        dur = dur_map.get(duration, dur_map["30분 분량"])

        st.markdown(
            f"""<div style="background:#1a1a2e; border:1px solid #444; border-radius:8px; padding:10px; margin:8px 0;">
                <span style="color:#AAAAAA; font-size:13px;">예상 분량:</span>
                <span style="color:#FFFFFF; font-size:14px; margin-left:6px;">{dur['minutes']}분 / {dur['label']}</span>
                <br><span style="color:#FF8888; font-size:12px;">{dur['parts']}개 파트로 나눠 생성합니다. 파트당 약 2~3분 소요.</span>
            </div>""",
            unsafe_allow_html=True
        )

        if st.button("대본 자동 생성", key="btn_auto_script", use_container_width=True):
            topic = st.session_state.get("selected_topic", "")
            if not topic:
                st.error("탭1에서 주제를 먼저 선택해주세요.")
            elif not GEMINI_API_KEY:
                st.error("Gemini API 키가 없습니다.")
            else:
                if content_type == "쇼츠":
                    with st.spinner("쇼츠 대본 생성 중..."):
                        s_prompt = f"""당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가입니다.

주제: {topic}
톤: {tone}
생성할 편 수: {num_episodes}편

【최우선 원칙: 사실 기반 작성】
- 모든 내용은 검증된 사실과 실제 데이터만 사용한다.
- 추측이나 과장은 절대 금지. 불확실한 정보는 "보도에 의하면"으로 출처를 밝힌다.
- 허위 사실 날조 절대 금지.

【대본 규칙】
1. 인사 자기소개 구독 좋아요 언급 금지.
2. 첫 문장은 현장 투척형, 통념 파괴형, 충격 수치형, 질문 관통형 중 하나.
3. 첫 세 문장 안에 열린 고리를 건다.
4. 접속사는 "근데", "그래서", "결국", "알고 보니", "문제는" 사용. "그리고" "또한" 금지.
5. 한 문장 15~40자. 50자 넘으면 쪼갠다.
6. 번호 매기기 금지. 이야기 흐름으로.
7. 습니다체 기본, 까요체 질문 섞기.
8. 감정 곡선: 충격→공감→분노→반전→여운
9. 마지막 문장은 묵직한 여운 또는 다음 편 유도.
10. 각 편 8~15문장.
11. 모든 숫자 한글 표기. 영어 한글 순화. 마침표만 사용.

【금지어】
안녕하세요, 여러분, 오늘은, 소개해 드릴, 알아볼게요, 구독, 좋아요, 알림, 감사합니다

【출력 형식】
===편1===
(순수 대본 문장만)

===편2===
(순수 대본 문장만)

{num_episodes}편 모두 작성하세요."""

                        result = safe_generate(s_prompt, max_tokens=8000)
                        if result.startswith("오류:"):
                            st.error(result)
                        else:
                            st.session_state["auto_script_result"] = clean_script(result)
                            st.success("쇼츠 대본 생성 완료!")

                else:
                    total_parts = dur["parts"]
                    all_parts = []
                    progress = st.progress(0)
                    status = st.empty()

                    for p in range(total_parts):
                        status.text(f"대본 생성 중... 파트 {p + 1}/{total_parts} (예상 2~3분)")

                        if p == 0:
                            pp = f"""당신은 유튜브 롱폼 콘텐츠 전문 대본 작가입니다.

주제: {topic}
톤: {tone}
전체 목표: {dur['minutes']}분 분량 대본
현재: 파트 {p + 1}/{total_parts} (도입부)

【최우선 원칙: 사실 기반 작성】
- 모든 내용은 검증된 사실과 실제 데이터만 사용한다.
- 추측이나 과장 절대 금지. 불확실한 정보는 출처를 밝힌다.
- 구체적 숫자, 날짜, 기관명, 법률명 포함.
- 허위 사실 날조 절대 금지.

【대본 규칙】
1. 인사 자기소개 구독 좋아요 언급 금지.
2. 첫 문장은 현장 투척형, 통념 파괴형, 충격 수치형, 질문 관통형 중 하나.
3. 첫 세 문장 안에 열린 고리를 건다.
4. 접속사는 "근데" "그래서" "결국" "알고 보니" "문제는" 사용.
5. 한 문장 15~40자. 50자 넘으면 쪼갠다.
6. 번호 매기기 금지. 이야기 흐름.
7. 습니다체 기본, 까요체 질문 섞기.
8. 5문장마다 새로운 미끼 던지기.
9. 모든 숫자 한글. 영어 한글 순화. 마침표만 사용.

【분량 규칙 - 매우 중요】
반드시 최소 50문장 이상 작성하세요.
50문장 미만은 절대 금지입니다.
가능하면 55~60문장까지 작성하세요.

마지막 문장은 다음 파트로 자연스럽게 이어지게 끝내세요.

【금지어】
안녕하세요, 여러분, 오늘은, 소개해 드릴, 알아볼게요, 구독, 좋아요, 감사합니다

【출력 형식 규칙】
- 한 문장을 쓰고 반드시 줄바꿈. 한 줄에 두 문장 금지.
- 마크다운 서식 절대 금지.
- 순수 대본 문장만 출력."""

                        else:
                            prev_last = "\n".join(all_parts[-1].split("\n")[-5:]) if all_parts else ""
                            if p == total_parts - 1:
                                end_rule = "마지막 문장은 묵직한 여운으로 마무리한다."
                            else:
                                end_rule = "마지막 문장은 다음 파트로 자연스럽게 이어지게 끝낸다."

                            pp = f"""당신은 유튜브 롱폼 콘텐츠 전문 대본 작가입니다.

주제: {topic}
톤: {tone}
전체 목표: {dur['minutes']}분 분량
현재: 파트 {p + 1}/{total_parts} ({'결론부' if p == total_parts - 1 else '중반부'})

【이전 파트 마지막 5문장】
{prev_last}

【최우선 원칙: 사실 기반 작성】
- 검증된 사실과 실제 데이터만 사용. 추측 과장 금지.
- 앞 파트와 내용 중복 금지. 새로운 관점으로 확장.

【대본 규칙】
1. 이전 파트에 이어서 자연스럽게 시작.
2. 접속사는 "근데" "그래서" "결국" "알고 보니" "문제는" 사용.
3. 한 문장 15~40자. 번호 매기기 금지.
4. 습니다체 기본, 까요체 섞기.
5. 모든 숫자 한글. 마침표만 사용.

【분량 규칙】
반드시 최소 50문장 이상. 가능하면 55~60문장.
{end_rule}

【출력 형식】
- 한 문장 한 줄. 마크다운 금지. 순수 대본만."""

                        result = safe_generate(pp, max_tokens=8000)

                        if result.startswith("오류:"):
                            status.text(f"파트 {p + 1} 실패: {result}")
                            break
                        else:
                            all_parts.append(clean_script(result))

                        progress.progress((p + 1) / total_parts)

                        if p < total_parts - 1:
                            time.sleep(3)

                    if all_parts:
                        full_script = "\n".join(all_parts)
                        st.session_state["auto_script_result"] = full_script
                        total_lines = len([l for l in full_script.split("\n") if l.strip() and len(l.strip()) > 2])
                        est_min = round(total_lines * 8 / 60)
                        status.text("")
                        st.success(f"대본 생성 완료! {len(all_parts)}개 파트 / 약 {total_lines}문장 / 예상 {est_min}분")

        if st.session_state.get("auto_script_result"):
            st.divider()
            raw_script = st.session_state["auto_script_result"]
            preview_lines = [l.strip() for l in raw_script.split("\n") if l.strip() and len(l.strip()) > 2]
            est_min = round(len(preview_lines) * 8 / 60)

            st.markdown(
                f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px; margin-bottom:12px;">
                    <span style="color:#88CC88; font-size:16px; font-weight:bold;">생성된 대본</span>
                    <span style="color:#FFFFFF; font-size:14px; margin-left:12px;">{len(preview_lines)}문장 / 약 {est_min}분</span>
                </div>""",
                unsafe_allow_html=True
            )

            edited_script = st.text_area("대본 편집", value=raw_script, height=500, key="auto_full_edit")

            with st.expander(f"처음 10문장 미리보기 (총 {len(preview_lines)}문장)"):
                for i, line in enumerate(preview_lines[:10]):
                    st.markdown(
                        f"""<div style="padding:4px 0; border-bottom:1px solid #333;">
                            <span style="color:#888; font-size:12px;">{i+1:03d}</span>
                            <span style="color:#DDD; font-size:14px; margin-left:8px;">{line}</span>
                        </div>""",
                        unsafe_allow_html=True
                    )
                if len(preview_lines) > 10:
                    st.caption(f"... 외 {len(preview_lines) - 10}문장")

            if st.button("이 대본을 최종 저장", key="btn_save_auto_script", use_container_width=True):
                final_text = st.session_state.get("auto_full_edit", raw_script)
                st.session_state["script_text"] = final_text
                final_lines = [l.strip() for l in final_text.split("\n") if l.strip() and len(l.strip()) > 2]
                st.session_state["script_lines"] = final_lines
                est = round(len(final_lines) * 8 / 60)
                st.success(f"대본 저장 완료! {len(final_lines)}문장 / 약 {est}분")

    else:
        st.subheader("Skywork 대본 붙여넣기")
        st.caption("Skywork에서 생성한 대본을 아래에 붙여넣으세요.")

        st.markdown(
            """<div style="background:#1a1a2e; border:1px solid #444; border-radius:8px; padding:12px; margin-bottom:12px;">
                <div style="color:#AAAAAA; font-size:13px;">Skywork 대본 생성 방법</div>
                <div style="color:#DDDDDD; font-size:14px; margin-top:6px;">
                    1. <a href="https://skywork.ai" target="_blank" style="color:#88AAFF;">skywork.ai</a> 접속<br>
                    2. 채팅에서 주제와 대본 규칙을 입력<br>
                    3. 생성된 대본의 순수 대사 부분만 복사<br>
                    4. 아래 텍스트 박스에 붙여넣기
                </div>
            </div>""",
            unsafe_allow_html=True
        )

        script_input = st.text_area(
            "대본 전체 붙여넣기",
            value=st.session_state.get("script_text", ""),
            height=400,
            placeholder="순수 대본을 여기에 붙여넣으세요.\n마침표(.)로 끝나는 각 문장이 하나의 장면이 됩니다.",
            key="script_textarea"
        )

        if st.button("대본 저장 및 분석", key="btn_save_script", use_container_width=True):
            if script_input.strip():
                cleaned = clean_script(script_input.strip())
                st.session_state["script_text"] = cleaned
                lines = [l.strip() for l in cleaned.split("\n") if l.strip() and len(l.strip()) > 2]
                st.session_state["script_lines"] = lines
                st.success(f"대본 저장! {len(lines)}개 문장으로 분리됨.")
            else:
                st.warning("대본을 입력해주세요.")

    if st.session_state.get("script_lines"):
        st.divider()
        lines = st.session_state["script_lines"]
        est = round(len(lines) * 8 / 60)
        st.markdown(
            f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px; margin-bottom:12px;">
                <span style="color:#88CC88; font-size:14px;">저장된 대본:</span>
                <span style="color:#FFFFFF; font-size:16px; font-weight:bold; margin-left:8px;">{len(lines)}개 문장 / 약 {est}분</span>
            </div>""",
            unsafe_allow_html=True
        )
        with st.expander("전체 장면 보기", expanded=False):
            for i, line in enumerate(lines):
                st.markdown(
                    f"""<div style="display:flex; padding:6px 0; border-bottom:1px solid #333;">
                        <span style="color:#888; min-width:60px; font-size:13px;">장면 {i+1:03d}</span>
                        <span style="color:#DDD; font-size:14px; margin-left:8px;">{line}</span>
                    </div>""",
                    unsafe_allow_html=True
                )

# ═══════════════════════════════════════════
# 탭3: 영상 업로드
# ═══════════════════════════════════════════
with tab3:
    st.header("영상 업로드")
    st.info("외부에서 만든 영상 파일(mp4)을 업로드하세요. 이 영상에 TTS 음성과 자막을 입혀서 최종 영상을 만듭니다.")

    video_upload = st.file_uploader(
        "영상 파일 업로드 (mp4)",
        type=["mp4", "mov", "avi", "mkv"],
        key="video_upload"
    )

    if video_upload:
        video_bytes = video_upload.getvalue()
        st.session_state["uploaded_videos"] = [{"name": video_upload.name, "bytes": video_bytes}]
        st.success(f"영상 업로드 완료: {video_upload.name} ({len(video_bytes) / 1024 / 1024:.1f}MB)")
        st.video(video_bytes)

    if st.session_state.get("uploaded_videos"):
        v = st.session_state["uploaded_videos"][0]
        st.markdown(
            f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px; margin-top:12px;">
                <span style="color:#88CC88;">현재 업로드된 영상:</span>
                <span style="color:#FFFFFF; font-weight:bold; margin-left:8px;">{v['name']} ({len(v['bytes']) / 1024 / 1024:.1f}MB)</span>
            </div>""",
            unsafe_allow_html=True
        )

# ═══════════════════════════════════════════
# 탭4: TTS 음성
# ═══════════════════════════════════════════
with tab4:
    st.header("TTS 음성 생성")

    lines = st.session_state.get("script_lines", [])
    if not lines:
        st.warning("탭2에서 먼저 대본을 입력하고 저장해주세요.")
    else:
        st.info(f"대본 {len(lines)}문장에 대해 TTS 음성을 생성합니다.")

        if not INWORLD_API_KEY:
            st.error("Inworld API 키가 없습니다. Secrets에 INWORLD_API_KEY를 추가하세요.")
        else:
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                selected_voice = st.selectbox("음성 선택", list(VOICE_OPTIONS.keys()), key="voice_select")
                voice_id = VOICE_OPTIONS[selected_voice]
            with col_v2:
                tts_model = st.selectbox("TTS 모델", [
                    "inworld-tts-1.5-max (고품질)",
                    "inworld-tts-1.5-mini (빠른 속도)"
                ], key="tts_model_select")
                model_id = "inworld-tts-1.5-max" if "max" in tts_model else "inworld-tts-1.5-mini"

            st.caption("먼저 테스트 문장으로 음성을 확인해보세요.")
            test_text = st.text_input("테스트 문장", value=lines[0] if lines else "테스트 음성입니다.", key="tts_test_text")
            if st.button("테스트 음성 생성", key="btn_tts_test"):
                with st.spinner("음성 생성 중..."):
                    audio, err = inworld_tts(test_text, voice_id, model_id)
                    if err:
                        st.error(err)
                    elif audio:
                        st.audio(audio, format="audio/mp3")
                        st.success("테스트 완료!")

            st.divider()

            if st.button("전체 대본 TTS 생성", key="btn_tts_all", use_container_width=True):
                audio_data = []
                durations = []
                progress = st.progress(0)
                status = st.empty()
                fail_count = 0

                for i, line in enumerate(lines):
                    status.text(f"TTS 생성 중... {i+1}/{len(lines)}: {line[:30]}...")
                    audio, err = inworld_tts(line, voice_id, model_id)

                    if err:
                        st.warning(f"문장 {i+1} 실패: {err}")
                        fail_count += 1
                        audio_data.append(None)
                        durations.append(3.0)
                    elif audio:
                        audio_data.append(audio)
                        dur = get_audio_duration(audio)
                        durations.append(dur)
                    else:
                        audio_data.append(None)
                        durations.append(3.0)
                        fail_count += 1

                    progress.progress((i + 1) / len(lines))

                    if i < len(lines) - 1:
                        time.sleep(0.3)

                st.session_state["tts_audio_data"] = audio_data
                st.session_state["tts_durations"] = durations
                status.text("")

                success_count = len([a for a in audio_data if a is not None])
                total_dur = sum(durations)
                st.success(f"TTS 완료! 성공: {success_count}/{len(lines)}문장 / 총 길이: {total_dur:.1f}초 ({total_dur/60:.1f}분)")
                if fail_count > 0:
                    st.warning(f"실패한 문장 {fail_count}개는 기본 3초로 설정됩니다.")

        if st.session_state.get("tts_audio_data"):
            st.divider()
            st.subheader("생성된 음성 미리듣기")
            audio_data = st.session_state["tts_audio_data"]
            durations = st.session_state["tts_durations"]

            total_dur = sum(durations)
            st.markdown(
                f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">
                    <span style="color:#88CC88;">총 음성 길이:</span>
                    <span style="color:#FFFFFF; font-weight:bold; margin-left:8px;">{total_dur:.1f}초 ({total_dur/60:.1f}분)</span>
                    <span style="color:#AAAAAA; margin-left:12px;">{len([a for a in audio_data if a])}개 성공</span>
                </div>""",
                unsafe_allow_html=True
            )

            with st.expander("개별 음성 확인"):
                for i, (audio, dur) in enumerate(zip(audio_data, durations)):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        line_text = lines[i] if i < len(lines) else ""
                        st.caption(f"{i+1:03d} ({dur:.1f}초): {line_text[:50]}")
                    with col_b:
                        if audio:
                            st.audio(audio, format="audio/mp3")
                        else:
                            st.caption("실패")

# ═══════════════════════════════════════════
# 탭5: 자막 편집
# ═══════════════════════════════════════════
with tab5:
    st.header("자막 편집")

    lines = st.session_state.get("script_lines", [])
    durations = st.session_state.get("tts_durations", [])

    if not lines:
        st.warning("탭2에서 먼저 대본을 저장해주세요.")
    elif not durations:
        st.warning("탭4에서 먼저 TTS 음성을 생성해주세요. 음성 길이 기반으로 자막 싱크가 맞춰집니다.")
    else:
        st.info(f"대본 {len(lines)}문장 / TTS 길이 기반 자동 싱크")

        srt_content = generate_srt(lines, durations)
        st.session_state["srt_content"] = srt_content

        st.subheader("자막 타이밍 확인")
        current_time = 0.0
        with st.expander("전체 자막 타이밍 보기"):
            for i, (line, dur) in enumerate(zip(lines, durations)):
                start_m = int(current_time // 60)
                start_s = int(current_time % 60)
                end_time = current_time + dur
                end_m = int(end_time // 60)
                end_s = int(end_time % 60)
                st.markdown(
                    f"""<div style="display:flex; padding:4px 0; border-bottom:1px solid #333;">
                        <span style="color:#888; min-width:100px; font-size:12px;">{start_m:02d}:{start_s:02d} ~ {end_m:02d}:{end_s:02d}</span>
                        <span style="color:#FF8888; min-width:50px; font-size:12px;">{dur:.1f}초</span>
                        <span style="color:#DDD; font-size:13px; margin-left:8px;">{line}</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                current_time = end_time

        st.divider()
        st.subheader("자막 스타일 설정")

        content_type = st.session_state.get("content_type", "쇼츠")
        if content_type == "쇼츠":
            sub_style = st.session_state["subtitle_style_shorts"]
            style_label = "쇼츠"
        else:
            sub_style = st.session_state["subtitle_style_long"]
            style_label = "롱폼"

        col_set, col_prev = st.columns([1, 1])
        with col_set:
            sub_style["font"] = st.selectbox(f"{style_label} 글꼴", FONT_LIST, index=FONT_LIST.index(sub_style["font"]) if sub_style["font"] in FONT_LIST else 0, key="sub_font")
            sub_style["size"] = st.slider(f"{style_label} 크기", 16, 72, sub_style["size"], key="sub_size")
            sub_style["color"] = st.color_picker("글자 색상", sub_style["color"], key="sub_color")
            sub_style["outline_color"] = st.color_picker("외곽선 색상", sub_style["outline_color"], key="sub_outline_color")
            sub_style["outline_width"] = st.slider("외곽선 두께", 0, 6, sub_style["outline_width"], key="sub_outline_w")
            sub_style["position"] = st.selectbox("위치", ["상단", "중앙", "하단"], index=["상단", "중앙", "하단"].index(sub_style["position"]), key="sub_pos")
            sub_style["bg_opacity"] = st.slider("배경 투명도", 0.0, 1.0, sub_style["bg_opacity"], 0.1, key="sub_bg")

        with col_prev:
            st.caption("미리보기")
            pos_map = {"상단": "top:15%", "중앙": "top:50%", "하단": "bottom:15%"}
            pos_css = pos_map.get(sub_style["position"], "bottom:15%")
            bg_rgba = f"rgba(0,0,0,{sub_style['bg_opacity']})"

            if content_type == "쇼츠":
                w, h = 180, 320
            else:
                w, h = 320, 180

            st.markdown(
                f"""<div style="position:relative; width:{w}px; height:{h}px; background:#222; border-radius:8px; overflow:hidden;">
                    <div style="position:absolute; {pos_css}; left:50%; transform:translateX(-50%);
                        font-family:'{FONT_MAP.get(sub_style['font'], 'sans-serif')}', sans-serif;
                        font-size:{sub_style['size']//2}px; color:{sub_style['color']};
                        text-shadow: {sub_style['outline_width']}px {sub_style['outline_width']}px 0 {sub_style['outline_color']},
                        -{sub_style['outline_width']}px -{sub_style['outline_width']}px 0 {sub_style['outline_color']};
                        background:{bg_rgba}; padding:4px 12px; border-radius:4px; white-space:nowrap;">
                        자막 미리보기 샘플
                    </div>
                </div>""",
                unsafe_allow_html=True
            )

        st.divider()
        st.subheader("SRT 파일")
        st.download_button(
            "SRT 자막 파일 다운로드",
            data=srt_content,
            file_name="subtitles.srt",
            mime="text/plain",
            use_container_width=True
        )
        with st.expander("SRT 미리보기"):
            st.code(srt_content)

# ═══════════════════════════════════════════
# 탭6: 최종 합치기
# ═══════════════════════════════════════════
with tab6:
    st.header("최종 합치기")

    lines = st.session_state.get("script_lines", [])
    videos = st.session_state.get("uploaded_videos", [])
    audio_data = st.session_state.get("tts_audio_data", [])
    durations = st.session_state.get("tts_durations", [])
    srt_content = st.session_state.get("srt_content", "")

    st.subheader("진행 상황")
    check_items = {
        "주제 선택": bool(st.session_state.get("selected_topic")),
        "대본 저장": len(lines) > 0,
        "영상 업로드": len(videos) > 0,
        "TTS 음성 생성": len(audio_data) > 0,
        "자막 생성": bool(srt_content),
    }
    all_ready = True
    for item, done in check_items.items():
        if done:
            st.success(f"{item}: 완료")
        else:
            st.warning(f"{item}: 미완료")
            all_ready = False

    st.divider()

    if all_ready:
        st.subheader("최종 영상 생성")
        st.markdown(
            """<div style="background:#1a1a2e; border:1px solid #444; border-radius:8px; padding:12px;">
                <div style="color:#FFFFFF; font-size:14px;">영상 + TTS 음성 + 자막을 합쳐서 최종 mp4 파일을 생성합니다.</div>
                <div style="color:#FF8888; font-size:12px; margin-top:6px;">영상 길이에 따라 1~5분 소요될 수 있습니다.</div>
            </div>""",
            unsafe_allow_html=True
        )

        if st.button("최종 영상 합치기", key="btn_final_merge", use_container_width=True):
            video_bytes = videos[0]["bytes"]
            valid_audio = [a for a in audio_data if a is not None]

            if not valid_audio:
                st.error("유효한 TTS 음성이 없습니다. 탭4에서 다시 생성해주세요.")
            else:
                content_type = st.session_state.get("content_type", "쇼츠")
                if content_type == "쇼츠":
                    sub_style = st.session_state["subtitle_style_shorts"]
                else:
                    sub_style = st.session_state["subtitle_style_long"]

                with st.spinner("최종 영상 합치는 중... (1~5분 소요)"):
                    final_bytes, err = merge_video_audio_subtitle(
                        video_bytes, valid_audio, srt_content, sub_style
                    )

                if err:
                    st.error(err)
                else:
                    st.session_state["final_video"] = final_bytes
                    st.success(f"최종 영상 생성 완료! ({len(final_bytes) / 1024 / 1024:.1f}MB)")

    if st.session_state.get("final_video"):
        st.divider()
        st.subheader("최종 영상")
        st.video(st.session_state["final_video"])
        st.download_button(
            "최종 영상 다운로드 (mp4)",
            data=st.session_state["final_video"],
            file_name=f"final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
            mime="video/mp4",
            use_container_width=True
        )

    st.divider()
    st.subheader("프로젝트 내보내기")
    if st.button("프로젝트 JSON 생성", key="btn_export_project", use_container_width=True):
        project = {
            "created_at": datetime.now().isoformat(),
            "topic": st.session_state.get("selected_topic", ""),
            "content_type": st.session_state.get("content_type", "쇼츠"),
            "total_sentences": len(lines),
            "script_lines": lines,
            "tts_durations": durations,
            "video_file": videos[0]["name"] if videos else "",
            "subtitle_style": st.session_state.get("subtitle_style_shorts" if st.session_state.get("content_type") == "쇼츠" else "subtitle_style_long", {}),
        }
        project_json = json.dumps(project, ensure_ascii=False, indent=2)
        st.download_button(
            "프로젝트 JSON 다운로드",
            data=project_json,
            file_name=f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
