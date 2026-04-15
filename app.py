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

VOICE_OPTIONS = {
    "민지 (활기찬 여성)": "Minji",
    "윤아 (차분한 여성)": "Yoona",
    "현우 (젊은 남성)": "Hyunwoo",
    "서준 (성숙한 남성)": "Seojun",
}

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

DEFAULT_SUB_LONG = {
    "font": "나눔고딕 볼드",
    "size": 28,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 2,
    "position": "하단",
    "margin_v": 30,
    "margin_l": 10,
    "margin_r": 10,
    "bg_opacity": 0.5,
}
DEFAULT_SUB_SHORTS = {
    "font": "배달의민족 주아",
    "size": 36,
    "color": "#FFFF00",
    "outline_color": "#000000",
    "outline_width": 3,
    "position": "중앙",
    "margin_v": 0,
    "margin_l": 10,
    "margin_r": 10,
    "bg_opacity": 0.0,
}

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
    "edited_sub_lines": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


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
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8}
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
                    time.sleep((attempt + 1) * 10)
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


def inworld_tts(text, voice_id="Minji", model_id="inworld-tts-1.5-max"):
    if not INWORLD_API_KEY:
        return None, "오류: INWORLD_API_KEY가 설정되지 않았습니다."
    url = "https://api.inworld.ai/tts/v1/voice"
    headers = {
        "Authorization": f"Basic {INWORLD_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": text[:2000],
        "voiceId": voice_id,
        "modelId": model_id,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            audio_b64 = data.get("audioContent", "")
            if audio_b64:
                return base64.b64decode(audio_b64), None
            return None, "오류: 응답에 audioContent가 없습니다."
        else:
            return None, f"오류: Inworld API {resp.status_code} - {resp.text[:300]}"
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


def merge_final_video(video_list, audio_bytes_list, srt_content, sub_style):
    try:
        work_dir = tempfile.mkdtemp()
        segment_paths = []

        for i, audio_bytes in enumerate(audio_bytes_list):
            if audio_bytes is None:
                continue
            vid_idx = min(i, len(video_list) - 1)
            vid_bytes = video_list[vid_idx]["bytes"]

            vid_path = os.path.join(work_dir, f"vid_{i:04d}.mp4")
            aud_path = os.path.join(work_dir, f"aud_{i:04d}.mp3")
            seg_path = os.path.join(work_dir, f"seg_{i:04d}.ts")

            with open(vid_path, "wb") as f:
                f.write(vid_bytes)
            with open(aud_path, "wb") as f:
                f.write(audio_bytes)

            subprocess.run(
                ["ffmpeg", "-y", "-i", vid_path, "-i", aud_path,
                 "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                 "-c:a", "aac", "-b:a", "192k", "-shortest",
                 "-f", "mpegts", seg_path],
                capture_output=True, timeout=60
            )

            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                segment_paths.append(seg_path)

        if not segment_paths:
            shutil.rmtree(work_dir, ignore_errors=True)
            return None, "오류: 합칠 수 있는 영상이 없습니다."

        concat_input = "concat:" + "|".join(segment_paths)
        merged_path = os.path.join(work_dir, "merged.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-i", concat_input,
             "-c:v", "libx264", "-preset", "fast", "-crf", "23",
             "-c:a", "aac", "-b:a", "192k", merged_path],
            capture_output=True, timeout=300
        )

        if not os.path.exists(merged_path):
            shutil.rmtree(work_dir, ignore_errors=True)
            return None, "오류: 영상 병합 실패"

        srt_path = os.path.join(work_dir, "subtitles.srt")
        output_path = os.path.join(work_dir, "final_output.mp4")

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        font_name = FONT_MAP.get(sub_style.get("font", "나눔고딕 볼드"), "NanumGothicBold")
        font_size = sub_style.get("size", 28)
        outline_w = sub_style.get("outline_width", 2)
        margin_v = sub_style.get("margin_v", 30)
        margin_l = sub_style.get("margin_l", 10)
        margin_r = sub_style.get("margin_r", 10)

        pos = sub_style.get("position", "하단")
        if pos == "상단":
            alignment = 8
        elif pos == "중앙":
            alignment = 5
        else:
            alignment = 2

        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

        subtitle_filter = (
            f"subtitles='{srt_escaped}':force_style='"
            f"FontName={font_name},"
            f"FontSize={font_size},"
            f"Outline={outline_w},"
            f"Alignment={alignment},"
            f"MarginV={margin_v},"
            f"MarginL={margin_l},"
            f"MarginR={margin_r}'"
        )

        subprocess.run(
            ["ffmpeg", "-y", "-i", merged_path,
             "-vf", subtitle_filter,
             "-c:v", "libx264", "-preset", "fast", "-crf", "23",
             "-c:a", "copy", output_path],
            capture_output=True, timeout=300
        )

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path, "rb") as f:
                result = f.read()
            shutil.rmtree(work_dir, ignore_errors=True)
            return result, None
        else:
            shutil.rmtree(work_dir, ignore_errors=True)
            return None, "오류: 최종 영상 생성 실패"
    except Exception as e:
        return None, f"오류: {str(e)}"


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
    "1. 주제 추천", "2. 대본 입력", "3. 영상 업로드",
    "4. TTS 음성", "5. 자막 편집", "6. 최종 합치기",
])

with tab1:
    st.header("주제 추천")
    st.info("카테고리를 선택하면 최신 뉴스를 검색하고, Gemini가 떡상 확률과 함께 10개 주제를 추천합니다.")

    categories = [
        "경제/사회", "부동산", "창업/자영업", "노동/일자리",
        "유흥/향락산업", "먹거리/외식", "범죄/사건사고",
        "심리학", "자기계발"
    ]

    selected_cat = st.selectbox(
        "카테고리 선택", categories,
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
각 뉴스마다: 뉴스1: (제목) / 출처: (언론사) / 핵심: (한 줄 요약)
최근 1주일 이내 뉴스 우선. 2026년 4월 현재 한국 이슈 반영."""
                news_result = safe_generate(news_search_prompt)

            with st.spinner("뉴스를 분석하고 주제를 추천 중입니다..."):
                content_label = st.session_state.get("content_type", "쇼츠")
                topic_prompt = f"""당신은 유튜브 {content_label} 백만 조회수 전문 기획자입니다.
아래는 "{selected_cat}" 카테고리의 최신 뉴스입니다:
{news_result}

유튜브 {content_label}로 만들면 조회수가 폭발할 주제 10개를 추천하세요.
반드시 아래 JSON 형식으로만 출력하세요:
[
  {{"번호": 1, "주제": "유튜브 제목 (20~25자)", "출처뉴스": "참고한 뉴스 제목", "떡상확률": 85, "이유": "한 줄 설명", "추천태그": "태그1, 태그2, 태그3", "난이도": "쉬움"}},
  ...
]
규칙: 주제 20~25자, 자극적 제목, 떡상확률 50~95, 난이도 쉬움/보통/어려움, 10개 비중복, 떡상확률 높은 순 정렬"""
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
                    pc, pe, bc = "#FF4444", "🔥", "#FF4444"
                elif prob >= 70:
                    pc, pe, bc = "#FF8800", "⚡", "#FF8800"
                else:
                    pc, pe, bc = "#44AA44", "💡", "#44AA44"
                dc = {"쉬움": "#44CC44", "보통": "#FFAA00", "어려움": "#FF4444"}.get(diff, "#FFAA00")
                st.markdown(
                    f"""<div style="border:2px solid {bc}; border-radius:12px; padding:16px; margin:8px 0; background:#1a1a2e;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:20px; font-weight:bold; color:#FFF;">{pe} {num}. {title}</span>
                            <span style="font-size:24px; font-weight:bold; color:{pc};">떡상 {prob}%</span>
                        </div>
                        <div style="margin:6px 0;">
                            <span style="background:#333; padding:3px 10px; border-radius:20px; font-size:12px; color:#AAA;">출처: {source}</span>
                            <span style="background:{dc}22; padding:3px 10px; border-radius:20px; font-size:12px; color:{dc}; margin-left:6px;">난이도: {diff}</span>
                        </div>
                        <div style="color:#CCC; font-size:14px; margin:8px 0;">{reason}</div>
                        <div style="color:#888; font-size:12px;">태그: {tags}</div>
                    </div>""", unsafe_allow_html=True)

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
                        st.success(f"주제 결정: {chosen.get('주제', '')}")
            with col_btn2:
                custom_topic = st.text_input("또는 직접 주제 입력", key="custom_topic_input")
                if st.button("직접 입력 주제로 결정", key="btn_custom_topic"):
                    if custom_topic.strip():
                        st.session_state["selected_topic"] = custom_topic.strip()
                        st.session_state["selected_topic_data"] = {}
                        st.success(f"주제 결정: {custom_topic.strip()}")
        else:
            st.markdown(f"```\n{clean_special(raw)}\n```")
            topic_input = st.text_input("사용할 주제를 입력하세요", key="topic_input_fallback")
            if st.button("이 주제로 결정", key="btn_set_topic_fallback"):
                if topic_input.strip():
                    st.session_state["selected_topic"] = topic_input.strip()
                    st.success(f"주제 결정: {topic_input.strip()}")

    if st.session_state.get("selected_topic"):
        st.divider()
        sd = st.session_state.get("selected_topic_data", {})
        info_line = ""
        if sd:
            info_line = f"""<div style="font-size:14px; color:#AAA;">떡상확률: <span style="color:#FF4444; font-weight:bold;">{sd.get("떡상확률", "")}%</span> | 난이도: {sd.get("난이도", "")} | 태그: {sd.get("추천태그", "")}</div>"""
        st.markdown(
            f"""<div style="border:3px solid #4CAF50; border-radius:12px; padding:20px; background:#0a2e0a; text-align:center;">
                <div style="font-size:14px; color:#88CC88;">현재 선택된 주제</div>
                <div style="font-size:24px; font-weight:bold; color:#FFF; margin:10px 0;">{st.session_state['selected_topic']}</div>
                {info_line}
            </div>""", unsafe_allow_html=True)

with tab2:
    st.header("대본 입력")
    if st.session_state.get("selected_topic"):
        st.markdown(
            f"""<div style="border:2px solid #4CAF50; border-radius:8px; padding:12px; background:#0a2e0a; margin-bottom:16px;">
                <span style="color:#88CC88;">현재 주제:</span>
                <span style="color:#FFF; font-weight:bold; margin-left:8px;">{st.session_state['selected_topic']}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.warning("탭1에서 먼저 주제를 선택해주세요.")

    script_mode = st.radio("대본 작성 방법", ["Gemini 자동 생성", "Skywork 대본 붙여넣기"], horizontal=True, key="script_mode")
    st.divider()

    if script_mode == "Gemini 자동 생성":
        st.subheader("Gemini 자동 대본 생성")
        content_type = st.session_state.get("content_type", "쇼츠")
        col_o1, col_o2, col_o3 = st.columns(3)
        with col_o1:
            if content_type == "쇼츠":
                num_episodes = st.slider("생성할 편 수", 1, 10, 1, key="num_episodes")
            else:
                num_episodes = 1
                st.info("롱폼은 1편씩 생성합니다.")
        with col_o2:
            tone = st.selectbox("톤 선택", ["충격/폭로형", "분석/해설형", "공감/스토리형", "비교/대조형", "미래전망형"], key="tone_select")
        with col_o3:
            duration = st.selectbox("영상 길이", ["30분 분량", "45분 분량", "1시간 분량"], key="duration_select")

        dur_map = {
            "30분 분량": {"minutes": 30, "label": "250~300문장", "parts": 6},
            "45분 분량": {"minutes": 45, "label": "380~450문장", "parts": 9},
            "1시간 분량": {"minutes": 60, "label": "500~600문장", "parts": 12},
        }
        dur = dur_map.get(duration, dur_map["30분 분량"])

        if st.button("대본 자동 생성", key="btn_auto_script", use_container_width=True):
            topic = st.session_state.get("selected_topic", "")
            if not topic:
                st.error("탭1에서 주제를 먼저 선택해주세요.")
            elif not GEMINI_API_KEY:
                st.error("Gemini API 키가 없습니다.")
            else:
                if content_type == "쇼츠":
                    with st.spinner("쇼츠 대본 생성 중..."):
                        s_prompt = f"""유튜브 쇼츠 대본 작가. 주제: {topic}, 톤: {tone}, {num_episodes}편.
사실 기반. 인사/구독/좋아요 금지. 첫 문장 충격형. 8~15문장. 숫자 한글. 마침표만.
===편1=== 형식으로 출력."""
                        result = safe_generate(s_prompt, max_tokens=8000)
                        if not result.startswith("오류:"):
                            st.session_state["auto_script_result"] = clean_script(result)
                            st.success("쇼츠 대본 생성 완료!")
                        else:
                            st.error(result)
                else:
                    total_parts = dur["parts"]
                    all_parts = []
                    progress = st.progress(0)
                    status = st.empty()
                    for p in range(total_parts):
                        status.text(f"파트 {p+1}/{total_parts} 생성 중...")
                        if p == 0:
                            pp = f"""유튜브 롱폼 대본 작가. 주제: {topic}, 톤: {tone}, {dur['minutes']}분, 파트 {p+1}/{total_parts} 도입부.
사실 기반. 최소 50문장. 한 문장 한 줄. 마크다운 금지."""
                        else:
                            prev = "\n".join(all_parts[-1].split("\n")[-5:]) if all_parts else ""
                            end_r = "묵직한 여운으로 마무리." if p == total_parts - 1 else "다음 파트로 이어지게."
                            pp = f"""유튜브 롱폼 대본. 주제: {topic}, 톤: {tone}, 파트 {p+1}/{total_parts}.
이전 마지막: {prev}
최소 50문장. 중복 금지. {end_r} 한 문장 한 줄. 마크다운 금지."""
                        result = safe_generate(pp, max_tokens=8000)
                        if result.startswith("오류:"):
                            status.text(f"파트 {p+1} 실패")
                            break
                        all_parts.append(clean_script(result))
                        progress.progress((p + 1) / total_parts)
                        if p < total_parts - 1:
                            time.sleep(3)
                    if all_parts:
                        full = "\n".join(all_parts)
                        st.session_state["auto_script_result"] = full
                        tl = len([l for l in full.split("\n") if l.strip() and len(l.strip()) > 2])
                        status.text("")
                        st.success(f"대본 완료! {len(all_parts)}파트 / {tl}문장")

        if st.session_state.get("auto_script_result"):
            st.divider()
            raw_script = st.session_state["auto_script_result"]
            preview = [l.strip() for l in raw_script.split("\n") if l.strip() and len(l.strip()) > 2]
            st.markdown(f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">
                <span style="color:#88CC88; font-weight:bold;">생성된 대본: {len(preview)}문장</span></div>""", unsafe_allow_html=True)
            edited_script = st.text_area("대본 편집", value=raw_script, height=400, key="auto_full_edit")
            if st.button("대본 최종 저장", key="btn_save_auto", use_container_width=True):
                final = st.session_state.get("auto_full_edit", raw_script)
                st.session_state["script_text"] = final
                fl = [l.strip() for l in final.split("\n") if l.strip() and len(l.strip()) > 2]
                st.session_state["script_lines"] = fl
                st.session_state["edited_sub_lines"] = list(fl)
                st.success(f"저장 완료! {len(fl)}문장")

    else:
        st.subheader("Skywork 대본 붙여넣기")
        script_input = st.text_area("대본 붙여넣기", value=st.session_state.get("script_text", ""), height=400, key="script_textarea")
        if st.button("대본 저장", key="btn_save_script", use_container_width=True):
            if script_input.strip():
                cleaned = clean_script(script_input.strip())
                st.session_state["script_text"] = cleaned
                lines = [l.strip() for l in cleaned.split("\n") if l.strip() and len(l.strip()) > 2]
                st.session_state["script_lines"] = lines
                st.session_state["edited_sub_lines"] = list(lines)
                st.success(f"저장! {len(lines)}문장")

    if st.session_state.get("script_lines"):
        st.divider()
        lines = st.session_state["script_lines"]
        st.markdown(f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">
            <span style="color:#88CC88;">저장된 대본:</span>
            <span style="color:#FFF; font-weight:bold; margin-left:8px;">{len(lines)}개 문장</span></div>""", unsafe_allow_html=True)
        with st.expander("전체 장면 보기"):
            for i, line in enumerate(lines):
                st.markdown(f"""<div style="padding:4px 0; border-bottom:1px solid #333;">
                    <span style="color:#888; font-size:12px;">{i+1:03d}</span>
                    <span style="color:#DDD; font-size:14px; margin-left:8px;">{line}</span></div>""", unsafe_allow_html=True)

with tab3:
    st.header("영상 업로드")
    num_lines = len(st.session_state.get("script_lines", []))
    if num_lines == 0:
        st.warning("탭2에서 먼저 대본을 저장해주세요.")
    else:
        st.info(f"대본 {num_lines}문장 → 영상 {num_lines}개 필요. 장면별 영상(mp4)을 업로드하세요.")
        video_upload = st.file_uploader("영상 파일 선택 (복수 가능)", type=["mp4", "mov", "avi", "mkv"], accept_multiple_files=True, key="video_upload")
        if video_upload:
            if st.button("영상 저장", key="btn_save_videos", use_container_width=True):
                uploaded = []
                for f in sorted(video_upload, key=lambda x: x.name):
                    uploaded.append({"name": f.name, "bytes": f.getvalue()})
                st.session_state["uploaded_videos"] = uploaded
                st.success(f"{len(uploaded)}개 영상 저장됨.")
                if len(uploaded) < num_lines:
                    st.warning(f"영상 {len(uploaded)}개 < 문장 {num_lines}개. 부족분은 마지막 영상 반복.")
                elif len(uploaded) > num_lines:
                    st.warning(f"영상 {len(uploaded)}개 > 문장 {num_lines}개. 초과분 무시.")

        if st.session_state.get("uploaded_videos"):
            st.divider()
            videos = st.session_state["uploaded_videos"]
            total_size = sum(len(v["bytes"]) for v in videos) / 1024 / 1024
            st.markdown(f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">
                <span style="color:#88CC88;">저장된 영상:</span>
                <span style="color:#FFF; font-weight:bold; margin-left:8px;">{len(videos)}개 / {total_size:.1f}MB</span>
                <span style="color:#AAA; margin-left:12px;">(필요: {num_lines}개)</span></div>""", unsafe_allow_html=True)
            with st.expander("영상 목록"):
                for i, v in enumerate(videos):
                    sz = len(v["bytes"]) / 1024 / 1024
                    lt = st.session_state["script_lines"][i] if i < num_lines else ""
                    st.markdown(f"""<div style="padding:4px 0; border-bottom:1px solid #333;">
                        <span style="color:#888;">{i+1:03d}</span>
                        <span style="color:#FFF; margin-left:8px;">{v['name']} ({sz:.1f}MB)</span>
                        <span style="color:#AAA; margin-left:8px; font-size:12px;">{lt[:40]}</span></div>""", unsafe_allow_html=True)

with tab4:
    st.header("TTS 음성 생성")
    lines = st.session_state.get("script_lines", [])
    if not lines:
        st.warning("탭2에서 먼저 대본을 저장해주세요.")
    elif not INWORLD_API_KEY:
        st.error("Inworld API 키가 없습니다. Secrets에 INWORLD_API_KEY를 추가하세요.")
    else:
        st.info(f"대본 {len(lines)}문장에 대해 TTS 음성을 생성합니다.")
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            selected_voice = st.selectbox("음성 선택", list(VOICE_OPTIONS.keys()), key="voice_select")
            voice_id = VOICE_OPTIONS[selected_voice]
        with col_v2:
            tts_model = st.selectbox("TTS 모델", ["inworld-tts-1.5-max (고품질)", "inworld-tts-1.5-mini (빠른 속도)"], key="tts_model_select")
            model_id = "inworld-tts-1.5-max" if "max" in tts_model else "inworld-tts-1.5-mini"

        test_text = st.text_input("테스트 문장", value=lines[0] if lines else "테스트입니다.", key="tts_test")
        if st.button("테스트 음성", key="btn_tts_test"):
            with st.spinner("생성 중..."):
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
            fail = 0
            for i, line in enumerate(lines):
                status.text(f"TTS {i+1}/{len(lines)}: {line[:30]}...")
                audio, err = inworld_tts(line, voice_id, model_id)
                if err:
                    fail += 1
                    audio_data.append(None)
                    durations.append(3.0)
                elif audio:
                    audio_data.append(audio)
                    durations.append(get_audio_duration(audio))
                else:
                    fail += 1
                    audio_data.append(None)
                    durations.append(3.0)
                progress.progress((i + 1) / len(lines))
                if i < len(lines) - 1:
                    time.sleep(0.3)

            st.session_state["tts_audio_data"] = audio_data
            st.session_state["tts_durations"] = durations
            status.text("")
            ok = len([a for a in audio_data if a])
            td = sum(durations)
            st.success(f"TTS 완료! 성공: {ok}/{len(lines)} / 총 {td:.1f}초 ({td/60:.1f}분)")
            if fail:
                st.warning(f"실패 {fail}개는 기본 3초 적용.")

        if st.session_state.get("tts_audio_data"):
            st.divider()
            ad = st.session_state["tts_audio_data"]
            dr = st.session_state["tts_durations"]
            td = sum(dr)
            st.markdown(f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">
                <span style="color:#88CC88;">총 음성:</span>
                <span style="color:#FFF; font-weight:bold; margin-left:8px;">{td:.1f}초 ({td/60:.1f}분)</span></div>""", unsafe_allow_html=True)
            with st.expander("개별 음성 확인"):
                for i, (a, d) in enumerate(zip(ad, dr)):
                    lt = lines[i] if i < len(lines) else ""
                    st.caption(f"{i+1:03d} ({d:.1f}초): {lt[:50]}")
                    if a:
                        st.audio(a, format="audio/mp3")

with tab5:
    st.header("자막 편집")
    lines = st.session_state.get("script_lines", [])
    durations = st.session_state.get("tts_durations", [])

    if not lines:
        st.warning("탭2에서 먼저 대본을 저장해주세요.")
    elif not durations:
        st.warning("탭4에서 먼저 TTS 음성을 생성해주세요.")
    else:
        st.info("TTS 음성 길이에 맞춰 자막이 자동 싱크됩니다. 자막 텍스트와 스타일을 수정할 수 있습니다.")

        st.subheader("자막 텍스트 편집")
        if not st.session_state.get("edited_sub_lines") or len(st.session_state["edited_sub_lines"]) != len(lines):
            st.session_state["edited_sub_lines"] = list(lines)

        edited_lines = st.session_state["edited_sub_lines"]
        with st.expander("자막 텍스트 수정 (클릭해서 열기)", expanded=False):
            new_lines = []
            for i, line in enumerate(edited_lines):
                dur = durations[i] if i < len(durations) else 3.0
                new_text = st.text_input(
                    f"{i+1:03d} ({dur:.1f}초)",
                    value=line,
                    key=f"sub_edit_{i}"
                )
                new_lines.append(new_text)
            if st.button("자막 수정 저장", key="btn_save_sub_edit"):
                st.session_state["edited_sub_lines"] = new_lines
                st.success("자막 텍스트 수정 저장됨!")

        sub_lines = st.session_state["edited_sub_lines"]

        st.subheader("자막 타이밍 (자동 싱크)")
        current_time = 0.0
        with st.expander("전체 자막 타이밍 보기"):
            for i, (line, dur) in enumerate(zip(sub_lines, durations)):
                sm = int(current_time // 60)
                ss = int(current_time % 60)
                et = current_time + dur
                em = int(et // 60)
                es = int(et % 60)
                st.markdown(f"""<div style="padding:4px 0; border-bottom:1px solid #333;">
                    <span style="color:#888; min-width:100px;">{sm:02d}:{ss:02d}~{em:02d}:{es:02d}</span>
                    <span style="color:#F88; min-width:50px; margin-left:8px;">{dur:.1f}초</span>
                    <span style="color:#DDD; margin-left:8px;">{line}</span></div>""", unsafe_allow_html=True)
                current_time = et

        st.divider()
        st.subheader("자막 스타일")

        ct = st.session_state.get("content_type", "쇼츠")
        if ct == "쇼츠":
            sty = st.session_state["subtitle_style_shorts"]
        else:
            sty = st.session_state["subtitle_style_long"]

        col_s, col_p = st.columns([1, 1])
        with col_s:
            sty["font"] = st.selectbox("글꼴", FONT_LIST, index=FONT_LIST.index(sty["font"]) if sty["font"] in FONT_LIST else 0, key="sf")
            sty["size"] = st.slider("글자 크기", 16, 72, sty["size"], key="ss")
            sty["color"] = st.color_picker("글자 색상", sty["color"], key="sc")
            sty["outline_color"] = st.color_picker("외곽선 색상", sty["outline_color"], key="soc")
            sty["outline_width"] = st.slider("외곽선 두께", 0, 6, sty["outline_width"], key="sow")
            sty["position"] = st.selectbox("세로 위치", ["상단", "중앙", "하단"], index=["상단", "중앙", "하단"].index(sty["position"]), key="sp")
            sty["bg_opacity"] = st.slider("배경 투명도", 0.0, 1.0, sty["bg_opacity"], 0.1, key="sbg")

            st.caption("미세 조절 (픽셀)")
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                sty["margin_v"] = st.number_input("상하 여백", 0, 300, sty.get("margin_v", 30), key="smv")
            with mc2:
                sty["margin_l"] = st.number_input("왼쪽 여백", 0, 300, sty.get("margin_l", 10), key="sml")
            with mc3:
                sty["margin_r"] = st.number_input("오른쪽 여백", 0, 300, sty.get("margin_r", 10), key="smr")

        with col_p:
            st.caption("미리보기")
            pos_map = {"상단": "top:15%", "중앙": "top:50%", "하단": "bottom:15%"}
            pcss = pos_map.get(sty["position"], "bottom:15%")
            bgr = f"rgba(0,0,0,{sty['bg_opacity']})"
            if ct == "쇼츠":
                pw, ph = 180, 320
            else:
                pw, ph = 320, 180
            st.markdown(
                f"""<div style="position:relative; width:{pw}px; height:{ph}px; background:#222; border-radius:8px; overflow:hidden; margin-top:20px;">
                    <div style="position:absolute; {pcss}; left:50%; transform:translateX(-50%);
                        font-family:'{FONT_MAP.get(sty['font'], 'sans-serif')}', sans-serif;
                        font-size:{sty['size']//2}px; color:{sty['color']};
                        text-shadow: {sty['outline_width']}px {sty['outline_width']}px 0 {sty['outline_color']},
                        -{sty['outline_width']}px -{sty['outline_width']}px 0 {sty['outline_color']};
                        background:{bgr}; padding:4px 12px; border-radius:4px; white-space:nowrap;">
                        자막 미리보기
                    </div>
                </div>""", unsafe_allow_html=True)

        srt_content = generate_srt(sub_lines, durations)
        st.session_state["srt_content"] = srt_content

        st.divider()
        st.download_button("SRT 자막 파일 다운로드", data=srt_content, file_name="subtitles.srt", mime="text/plain", use_container_width=True)
        with st.expander("SRT 미리보기"):
            st.code(srt_content)

with tab6:
    st.header("최종 합치기")
    lines = st.session_state.get("script_lines", [])
    videos = st.session_state.get("uploaded_videos", [])
    audio_data = st.session_state.get("tts_audio_data", [])
    durations = st.session_state.get("tts_durations", [])
    srt_content = st.session_state.get("srt_content", "")

    st.subheader("진행 상황")
    checks = {
        "주제 선택": bool(st.session_state.get("selected_topic")),
        "대본 저장": len(lines) > 0,
        "영상 업로드": len(videos) > 0,
        "TTS 음성": len(audio_data) > 0,
        "자막 생성": bool(srt_content),
    }
    all_ok = True
    for item, done in checks.items():
        if done:
            st.success(f"{item}: 완료")
        else:
            st.warning(f"{item}: 미완료")
            all_ok = False

    st.divider()

    if all_ok:
        st.subheader("최종 영상 생성")
        st.markdown("""<div style="background:#1a1a2e; border:1px solid #444; border-radius:8px; padding:12px;">
            <div style="color:#FFF;">영상 + TTS 음성 + 자막을 합쳐서 최종 mp4를 생성합니다.</div>
            <div style="color:#F88; font-size:12px; margin-top:6px;">영상 수에 따라 1~10분 소요.</div>
        </div>""", unsafe_allow_html=True)

        if st.button("최종 영상 합치기", key="btn_final_merge", use_container_width=True):
            valid_audio = [a for a in audio_data if a is not None]
            if not valid_audio:
                st.error("유효한 TTS 음성이 없습니다.")
            else:
                ct = st.session_state.get("content_type", "쇼츠")
                sub_style = st.session_state["subtitle_style_shorts"] if ct == "쇼츠" else st.session_state["subtitle_style_long"]

                with st.spinner("최종 영상 합치는 중..."):
                    final_bytes, err = merge_final_video(videos, valid_audio, srt_content, sub_style)

                if err:
                    st.error(err)
                else:
                    st.session_state["final_video"] = final_bytes
                    st.success(f"최종 영상 완료! ({len(final_bytes)/1024/1024:.1f}MB)")

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
    if st.button("프로젝트 JSON 생성", key="btn_export", use_container_width=True):
        project = {
            "created_at": datetime.now().isoformat(),
            "topic": st.session_state.get("selected_topic", ""),
            "content_type": st.session_state.get("content_type", "쇼츠"),
            "total_sentences": len(lines),
            "script_lines": lines,
            "tts_durations": durations,
            "video_files": [v["name"] for v in videos] if videos else [],
        }
        pj = json.dumps(project, ensure_ascii=False, indent=2)
        st.download_button("프로젝트 JSON 다운로드", data=pj, file_name=f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True)
