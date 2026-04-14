import streamlit as st
import requests
import json
import os
import re
import time
import base64
from datetime import datetime

st.set_page_config(page_title="시니어 콘텐츠 공장 v4.0", layout="wide")

def load_key(name):
    v = os.environ.get(name, "")
    if not v:
        try:
            v = st.secrets.get(name, "")
        except Exception:
            v = ""
    return v.strip() if v else ""

GEMINI_API_KEY = load_key("GEMINI_API_KEY")
KIE_API_KEY = load_key("KIE_API_KEY")
INWORLD_API_KEY = load_key("INWORLD_API_KEY")

VOICE_OPTIONS = {
    "한국어 여성 1": {"lang": "ko", "voice_id": "ko-KR-SunHiNeural"},
    "한국어 여성 2": {"lang": "ko", "voice_id": "ko-KR-JiMinNeural"},
    "한국어 남성 1": {"lang": "ko", "voice_id": "ko-KR-InJoonNeural"},
    "한국어 남성 2": {"lang": "ko", "voice_id": "ko-KR-HyunsuNeural"},
    "일본어 여성": {"lang": "ja", "voice_id": "ja-JP-NanamiNeural"},
    "일본어 남성": {"lang": "ja", "voice_id": "ja-JP-KeitaNeural"},
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

defaults = {
    "selected_topic": "",
    "selected_category": "경제/사회",
    "script_text": "",
    "script_lines": [],
    "uploaded_images": [],
    "image_paths": [],
    "video_urls": [],
    "tts_audio_bytes": [],
    "subtitle_style_long": dict(DEFAULT_SUB_LONG),
    "subtitle_style_shorts": dict(DEFAULT_SUB_SHORTS),
    "reference_image": None,
    "reference_image_path": "",
    "content_type": "쇼츠",
    "topic_recommendations": "",
    "news_data": "",
    "selected_topic_data": {},
    "auto_script_result": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def clean_special(text):
    if not text:
        return ""
    text = re.sub(r'[*#_~`>|]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

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

def generate_srt(lines, durations=None):
    srt = ""
    current_time = 0.0
    for i, line in enumerate(lines):
        dur = durations[i] if durations and i < len(durations) else 5.0
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
        srt += f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}\n"
        srt += f"{line.strip()}\n\n"
        current_time = end_time
    return srt

with st.sidebar:
    st.header("설정")
    st.subheader("API 연결 상태")
    if GEMINI_API_KEY:
        st.success("Gemini API: 연결됨")
    else:
        st.error("Gemini API: 키 없음")
    if KIE_API_KEY:
        st.success("KIE API: 연결됨")
    else:
        st.warning("KIE API: 키 없음")
    if INWORLD_API_KEY:
        st.success("Inworld API: 연결됨")
    else:
        st.warning("Inworld API: 키 없음")
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

st.title("시니어 콘텐츠 공장 v4.0")
st.caption("Gemini 주제추천 → 대본(Gemini자동/Skywork붙여넣기) → 이미지 → 영상변환 → TTS → 자막 → 합치기")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "1. 주제 추천",
    "2. 대본 입력",
    "3. 이미지 업로드",
    "4. 영상 변환",
    "5. TTS 음성",
    "6. 자막 스타일",
    "7. 최종 합치기",
])

# ═══════════════════════════════════════════
# 탭1: 주제 추천
# ═══════════════════════════════════════════
with tab1:
    st.header("주제 추천")
    st.info("카테고리를 선택하면 최신 뉴스를 검색하고, Gemini가 떡상 확률과 함께 10개 주제를 추천합니다.")

    categories = [
        "경제/사회", "부동산", "창업/자영업", "노동/일자리",
        "유흥/향락산업", "먹거리/외식", "건강/의료",
        "교육", "IT/기술", "범죄/사건사고"
    ]

    selected_cat = st.selectbox(
        "카테고리 선택",
        categories,
        index=categories.index(st.session_state.get("selected_category", "경제/사회")),
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
- 유튜브 인기 경제 채널

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
        # 마크다운 코드블록 제거
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

        duration_map = {
            "30분 분량": {"minutes": 30, "sentences": "200~250", "words": "약 9000자"},
            "45분 분량": {"minutes": 45, "sentences": "300~370", "words": "약 13500자"},
            "1시간 분량": {"minutes": 60, "sentences": "400~500", "words": "약 18000자"},
        }
        dur_info = duration_map.get(duration, duration_map["30분 분량"])

        st.markdown(
            f"""<div style="background:#1a1a2e; border:1px solid #444; border-radius:8px; padding:10px; margin:8px 0;">
                <span style="color:#AAAAAA; font-size:13px;">예상 분량:</span>
                <span style="color:#FFFFFF; font-size:14px; margin-left:6px;">{dur_info['minutes']}분 / {dur_info['sentences']}문장 / {dur_info['words']}</span>
                <br><span style="color:#FF8888; font-size:12px;">긴 대본은 여러 파트로 나눠 생성 후 자동으로 이어 붙입니다.</span>
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
                        script_prompt = f"""당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가입니다.

주제: {topic}
톤: {tone}
생성할 편 수: {num_episodes}편

【최우선 원칙: 사실 기반 작성】
- 모든 내용은 검증된 사실과 실제 데이터만 사용한다.
- 추측이나 과장은 절대 금지. 불확실한 정보는 "보도에 의하면"으로 출처를 밝힌다.
- 구체적 숫자, 날짜, 기관명을 최대한 포함한다.
- 허위 사실 날조 절대 금지.

【대본 규칙】
1. 인사 자기소개 구독 좋아요 언급 금지.
2. 첫 문장은 현장 투척형, 통념 파괴형, 충격 수치형, 질문 관통형 중 하나.
3. 첫 세 문장 안에 열린 고리를 건다.
4. 접속사는 "근데", "그래서", "결국", "알고 보니", "문제는" 사용. "그리고", "또한" 금지.
5. 한 문장 15~40자. 50자 넘으면 쪼갠다.
6. 번호 매기기 금지. 이야기 흐름으로.
7. 습니다체 기본, 까요체 질문 섞기.
8. 감정 곡선: 충격→공감→분노→반전→여운
9. 마지막 문장은 묵직한 여운 또는 다음 편 유도.
10. 각 편 8~15문장.
11. 모든 숫자 한글 표기. 영어 한글 순화. 마침표만 사용.

【금지어】
안녕하세요, 여러분, 오늘은, 소개해 드릴, 알아볼게요, 구독, 좋아요, 알림, 눌러주세요, 도움이 되셨다면, 감사합니다

【출력 형식】
===편1===
(순수 대본 문장만)

===편2===
(순수 대본 문장만)

{num_episodes}편 모두 작성하세요."""

                        result = safe_generate(script_prompt, max_tokens=8000)
                        if result.startswith("오류:"):
                            st.error(result)
                        else:
                            st.session_state["auto_script_result"] = result
                            st.success("쇼츠 대본 생성 완료!")

                else:
                    target_sentences = int(dur_info["sentences"].split("~")[1])
                    sentences_per_part = 80
                    num_parts = max(1, (target_sentences + sentences_per_part - 1) // sentences_per_part)

                    all_parts = []
                    progress = st.progress(0)
                    status = st.empty()

                    for part in range(num_parts):
                        status.text(f"대본 생성 중... 파트 {part + 1}/{num_parts}")

                        if part == 0:
                            part_prompt = f"""당신은 유튜브 롱폼 콘텐츠 전문 대본 작가입니다.

주제: {topic}
톤: {tone}
전체 목표 분량: {dur_info['minutes']}분 ({dur_info['sentences']}문장)
현재 작성: 파트 {part + 1}/{num_parts} (도입부)

【최우선 원칙: 사실 기반 작성】
- 모든 내용은 검증된 사실과 실제 데이터만 사용한다.
- 추측이나 과장은 절대 금지. 불확실한 정보는 출처를 밝힌다.
- 구체적 숫자, 날짜, 기관명, 법률명 등을 최대한 포함한다.
- 허위 사실 날조 절대 금지. 모르는 건 쓰지 않는다.

【대본 규칙】
1. 인사 자기소개 구독 좋아요 언급 금지.
2. 첫 문장은 현장 투척형, 통념 파괴형, 충격 수치형, 질문 관통형 중 하나.
3. 첫 세 문장 안에 열린 고리를 건다.
4. 접속사는 "근데", "그래서", "결국", "알고 보니", "문제는" 사용.
5. 한 문장 15~40자. 50자 넘으면 쪼갠다.
6. 번호 매기기 금지. 이야기 흐름.
7. 습니다체 기본, 까요체 질문 섞기.
8. 5문장마다 새로운 미끼 던지기.
9. 모든 숫자 한글 표기. 영어 한글 순화. 마침표만 사용.
10. 약 {sentences_per_part}문장 작성.
11. 마지막 문장은 다음 파트로 자연스럽게 이어지게.

【금지어】
안녕하세요, 여러분, 오늘은, 소개해 드릴, 알아볼게요, 구독, 좋아요, 알림, 감사합니다

순수 대본 문장만 출력. 편 번호, 대사 번호, 소제목, 주석 금지."""

                        else:
                            previous_last = "\n".join(all_parts[-1].split("\n")[-5:]) if all_parts else ""
                            if part == num_parts - 1:
                                ending = "마지막 문장은 묵직한 여운으로 마무리한다."
                            else:
                                ending = "마지막 문장은 다음 파트로 자연스럽게 이어지게."

                            part_prompt = f"""당신은 유튜브 롱폼 콘텐츠 전문 대본 작가입니다.

주제: {topic}
톤: {tone}
전체 목표: {dur_info['minutes']}분
현재: 파트 {part + 1}/{num_parts} ({'결론부' if part == num_parts - 1 else '중반부'})

【이전 파트 마지막 부분】
{previous_last}

【최우선 원칙: 사실 기반 작성】
- 검증된 사실과 실제 데이터만 사용. 추측 과장 금지.
- 구체적 숫자, 날짜, 기관명 포함. 허위 날조 금지.
- 앞 파트와 내용 중복 금지. 새로운 관점으로 확장.

【대본 규칙】
1. 이전 파트에 이어서 자연스럽게 시작.
2. 접속사는 "근데", "그래서", "결국", "알고 보니", "문제는" 사용.
3. 한 문장 15~40자.
4. 번호 매기기 금지.
5. 습니다체 기본, 까요체 섞기.
6. 5문장마다 새 미끼.
7. 모든 숫자 한글. 마침표만 사용.
8. 약 {sentences_per_part}문장 작성.
9. {ending}

순수 대본 문장만 출력."""

                        result = safe_generate(part_prompt, max_tokens=8000)

                        if result.startswith("오류:"):
                            status.text(f"파트 {part + 1} 실패: {result}")
                            break
                        else:
                            all_parts.append(result.strip())

                        progress.progress((part + 1) / num_parts)

                        if part < num_parts - 1:
                            time.sleep(2)

                    if all_parts:
                        full_script = "\n".join(all_parts)
                        st.session_state["auto_script_result"] = full_script
                        total_lines = len([l for l in re.split(r'(?<=[.?])\s*', full_script) if l.strip() and len(l.strip()) > 2])
                        estimated_minutes = round(total_lines * 7.5 / 60)
                        status.text("")
                        st.success(f"대본 생성 완료! {len(all_parts)}개 파트 / 약 {total_lines}문장 / 예상 {estimated_minutes}분")

        if st.session_state.get("auto_script_result"):
            st.divider()
            raw_script = st.session_state["auto_script_result"]
            preview_lines = [l.strip() for l in re.split(r'(?<=[.?])\s*', raw_script.strip()) if l.strip() and len(l.strip()) > 2]
            est_min = round(len(preview_lines) * 7.5 / 60)

            st.markdown(
                f"""<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px; margin-bottom:12px;">
                    <span style="color:#88CC88; font-size:16px; font-weight:bold;">생성된 대본</span>
                    <span style="color:#FFFFFF; font-size:14px; margin-left:12px;">{len(preview_lines)}문장 / 약 {est_min}분 분량</span>
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
                final_lines = [l.strip() for l in re.split(r'(?<=[.?])\s*', final_text.strip()) if l.strip() and len(l.strip()) > 2]
                st.session_state["script_lines"] = final_lines
                est = round(len(final_lines) * 7.5 / 60)
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
            placeholder="Skywork에서 생성한 순수 대본을 여기에 붙여넣으세요.\n마침표(.)로 끝나는 각 문장이 하나의 장면이 됩니다.",
            key="script_textarea"
        )

        if st.button("대본 저장 및 분석", key="btn_save_script", use_container_width=True):
            if script_input.strip():
                st.session_state["script_text"] = script_input.strip()
                raw_lines = re.split(r'(?<=[.?])\s*', script_input.strip())
                lines = [l.strip() for l in raw_lines if l.strip() and len(l.strip()) > 2]
                st.session_state["script_lines"] = lines
                st.success(f"대본 저장! {len(lines)}개 문장(장면)으로 분리됨.")
            else:
                st.warning("대본을 입력해주세요.")

    if st.session_state.get("script_lines"):
        st.divider()
        lines = st.session_state["script_lines"]
        est = round(len(lines) * 7.5 / 60)
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
        with st.expander("문장 수동 편집"):
            edited_lines = []
            for i, line in enumerate(lines):
                edited = st.text_input(f"장면 {i+1:03d}", value=line, key=f"edit_line_{i}")
                edited_lines.append(edited)
            if st.button("수정사항 저장", key="btn_save_edits"):
                st.session_state["script_lines"] = [l.strip() for l in edited_lines if l.strip()]
                st.success("수정사항 저장됨.")
                st.rerun()

# ═══════════════════════════════════════════
# 탭3: 이미지 업로드
# ═══════════════════════════════════════════
with tab3:
    st.header("이미지 업로드")
    num_lines = len(st.session_state.get("script_lines", []))
    if num_lines == 0:
        st.warning("탭2에서 먼저 대본을 입력하고 저장해주세요.")
    else:
        st.info(f"대본 문장 수: {num_lines}개 → 이미지 {num_lines}장이 필요합니다.")
        st.caption("Skywork에서 생성한 이미지를 장면 번호 순서대로 업로드하세요.")
        st.subheader("일괄 업로드")
        batch_upload = st.file_uploader(
            "이미지 파일 선택 (복수 선택 가능)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="batch_img_upload"
        )
        if batch_upload:
            if st.button("업로드한 이미지 저장", key="btn_save_images", use_container_width=True):
                uploaded = []
                for f in sorted(batch_upload, key=lambda x: x.name):
                    uploaded.append({"name": f.name, "bytes": f.getvalue(), "type": f.type})
                st.session_state["uploaded_images"] = uploaded
                st.success(f"{len(uploaded)}개 이미지 저장됨.")
                if len(uploaded) < num_lines:
                    st.warning(f"이미지 {len(uploaded)}개 < 문장 {num_lines}개. 부족분은 마지막 이미지 반복.")
                elif len(uploaded) > num_lines:
                    st.warning(f"이미지 {len(uploaded)}개 > 문장 {num_lines}개. 초과분 무시.")
        if st.session_state.get("uploaded_images"):
            st.divider()
            st.subheader("저장된 이미지 미리보기")
            images = st.session_state["uploaded_images"]
            cols_per_row = 4
            for row_start in range(0, len(images), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    idx = row_start + j
                    if idx < len(images):
                        with col:
                            st.image(images[idx]["bytes"], caption=f"장면 {idx+1:03d}", width=180)
                            if idx < num_lines:
                                lp = st.session_state["script_lines"][idx]
                                st.caption(lp[:30] + "..." if len(lp) > 30 else lp)

# ═══════════════════════════════════════════
# 탭4: 영상 변환
# ═══════════════════════════════════════════
with tab4:
    st.header("영상 변환")
    images = st.session_state.get("uploaded_images", [])
    lines = st.session_state.get("script_lines", [])
    if not images:
        st.warning("탭3에서 먼저 이미지를 업로드해주세요.")
    elif not lines:
        st.warning("탭2에서 먼저 대본을 입력해주세요.")
    else:
        st.info(f"이미지 {len(images)}장 / 대본 {len(lines)}문장 준비됨")
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            scene_duration = st.slider("장면당 길이(초)", 3, 10, 5, key="scene_dur")
        with col_v2:
            motion_type = st.selectbox("모션 유형", ["줌인", "줌아웃", "패닝", "정지"], key="motion_type")
        if not KIE_API_KEY:
            st.warning("KIE API 키가 없습니다. 장면 매칭 JSON을 다운받아 외부 툴에서 사용하세요.")
        match_data = []
        for i, line in enumerate(lines):
            img_idx = min(i, len(images) - 1)
            match_data.append({"scene": i+1, "script": line, "image_file": images[img_idx]["name"], "duration_sec": scene_duration})
        st.download_button("장면 매칭 정보 다운로드 (JSON)", data=json.dumps(match_data, ensure_ascii=False, indent=2), file_name="scene_matching.json", mime="application/json", use_container_width=True)

# ═══════════════════════════════════════════
# 탭5: TTS 음성
# ═══════════════════════════════════════════
with tab5:
    st.header("TTS 음성 생성")
    lines = st.session_state.get("script_lines", [])
    if not lines:
        st.warning("탭2에서 먼저 대본을 입력해주세요.")
    else:
        st.info(f"대본 {len(lines)}문장에 대해 음성을 생성합니다.")
        selected_voice = st.selectbox("음성 선택", list(VOICE_OPTIONS.keys()), key="voice_select")
        voice_info = VOICE_OPTIONS[selected_voice]
        if not INWORLD_API_KEY:
            st.warning("Inworld API 키가 없습니다. INWORLD_API_KEY를 Secrets에 추가하세요.")
        else:
            st.caption("TTS 기능은 Inworld API 연동 후 사용 가능합니다.")

# ═══════════════════════════════════════════
# 탭6: 자막 스타일
# ═══════════════════════════════════════════
with tab6:
    st.header("자막 스타일 설정")
    sub_tab_long, sub_tab_shorts = st.tabs(["롱폼 자막", "쇼츠 자막"])

    with sub_tab_long:
        st.subheader("롱폼 자막 스타일")
        col_set, col_prev = st.columns([1, 1])
        with col_set:
            sl = st.session_state["subtitle_style_long"]
            sl["font"] = st.selectbox("글꼴", FONT_LIST, index=FONT_LIST.index(sl["font"]) if sl["font"] in FONT_LIST else 0, key="long_font")
            sl["size"] = st.slider("크기", 16, 60, sl["size"], key="long_size")
            sl["color"] = st.color_picker("글자 색상", sl["color"], key="long_color")
            sl["outline_color"] = st.color_picker("외곽선 색상", sl["outline_color"], key="long_outline_color")
            sl["outline_width"] = st.slider("외곽선 두께", 0, 5, sl["outline_width"], key="long_outline_w")
            sl["position"] = st.selectbox("위치", ["상단", "중앙", "하단"], index=["상단", "중앙", "하단"].index(sl["position"]), key="long_pos")
            sl["bg_opacity"] = st.slider("배경 투명도", 0.0, 1.0, sl["bg_opacity"], 0.1, key="long_bg")
            st.caption("미세 조정 오프셋 (픽셀)")
            oc1, oc2 = st.columns(2)
            with oc1:
                sl["offset_up"] = st.number_input("위로", 0, 200, sl["offset_up"], key="long_off_up")
                sl["offset_left"] = st.number_input("왼쪽으로", 0, 200, sl["offset_left"], key="long_off_left")
            with oc2:
                sl["offset_down"] = st.number_input("아래로", 0, 200, sl["offset_down"], key="long_off_down")
                sl["offset_right"] = st.number_input("오른쪽으로", 0, 200, sl["offset_right"], key="long_off_right")
        with col_prev:
            st.caption("미리보기")
            pos_map = {"상단": "top:15%", "중앙": "top:50%", "하단": "bottom:15%"}
            pos_css = pos_map.get(sl["position"], "bottom:15%")
            bg_rgba = f"rgba(0,0,0,{sl['bg_opacity']})"
            st.markdown(
                f"""<div style="position:relative; width:320px; height:180px; background:#222; border-radius:8px; overflow:hidden;">
                    <div style="position:absolute; {pos_css}; left:50%; transform:translateX(-50%);
                        font-family:'{FONT_MAP.get(sl['font'], 'sans-serif')}', sans-serif;
                        font-size:{sl['size']//2}px; color:{sl['color']};
                        text-shadow: {sl['outline_width']}px {sl['outline_width']}px 0 {sl['outline_color']},
                        -{sl['outline_width']}px -{sl['outline_width']}px 0 {sl['outline_color']};
                        background:{bg_rgba}; padding:4px 12px; border-radius:4px; white-space:nowrap;">
                        롱폼 자막 미리보기
                    </div>
                </div>""",
                unsafe_allow_html=True
            )

    with sub_tab_shorts:
        st.subheader("쇼츠 자막 스타일")
        col_set2, col_prev2 = st.columns([1, 1])
        with col_set2:
            ss = st.session_state["subtitle_style_shorts"]
            ss["font"] = st.selectbox("글꼴", FONT_LIST, index=FONT_LIST.index(ss["font"]) if ss["font"] in FONT_LIST else 0, key="shorts_font")
            ss["size"] = st.slider("크기", 16, 72, ss["size"], key="shorts_size")
            ss["color"] = st.color_picker("글자 색상", ss["color"], key="shorts_color")
            ss["outline_color"] = st.color_picker("외곽선 색상", ss["outline_color"], key="shorts_outline_color")
            ss["outline_width"] = st.slider("외곽선 두께", 0, 6, ss["outline_width"], key="shorts_outline_w")
            ss["position"] = st.selectbox("위치", ["상단", "중앙", "하단"], index=["상단", "중앙", "하단"].index(ss["position"]), key="shorts_pos")
            ss["bg_opacity"] = st.slider("배경 투명도", 0.0, 1.0, ss["bg_opacity"], 0.1, key="shorts_bg")
            st.caption("미세 조정 오프셋 (픽셀)")
            oc3, oc4 = st.columns(2)
            with oc3:
                ss["offset_up"] = st.number_input("위로", 0, 200, ss["offset_up"], key="shorts_off_up")
                ss["offset_left"] = st.number_input("왼쪽으로", 0, 200, ss["offset_left"], key="shorts_off_left")
            with oc4:
                ss["offset_down"] = st.number_input("아래로", 0, 200, ss["offset_down"], key="shorts_off_down")
                ss["offset_right"] = st.number_input("오른쪽으로", 0, 200, ss["offset_right"], key="shorts_off_right")
        with col_prev2:
            st.caption("미리보기 (9:16)")
            pos_css2 = pos_map.get(ss["position"], "bottom:15%")
            bg_rgba2 = f"rgba(0,0,0,{ss['bg_opacity']})"
            st.markdown(
                f"""<div style="position:relative; width:180px; height:320px; background:#111; border-radius:8px; overflow:hidden;">
                    <div style="position:absolute; {pos_css2}; left:50%; transform:translateX(-50%);
                        font-family:'{FONT_MAP.get(ss['font'], 'sans-serif')}', sans-serif;
                        font-size:{ss['size']//2}px; color:{ss['color']};
                        text-shadow: {ss['outline_width']}px {ss['outline_width']}px 0 {ss['outline_color']},
                        -{ss['outline_width']}px -{ss['outline_width']}px 0 {ss['outline_color']};
                        background:{bg_rgba2}; padding:4px 12px; border-radius:4px; white-space:nowrap;">
                        쇼츠 자막
                    </div>
                </div>""",
                unsafe_allow_html=True
            )

    st.divider()
    if st.button("자막 스타일 JSON 내보내기", key="btn_export_sub", use_container_width=True):
        export_data = {
            "long_form": st.session_state["subtitle_style_long"],
            "shorts": st.session_state["subtitle_style_shorts"],
            "long_form_font_file": FONT_MAP.get(st.session_state["subtitle_style_long"]["font"], ""),
            "shorts_font_file": FONT_MAP.get(st.session_state["subtitle_style_shorts"]["font"], ""),
        }
        export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button("다운로드", data=export_json, file_name="subtitle_styles.json", mime="application/json", use_container_width=True)
        st.code(export_json, language="json")

# ═══════════════════════════════════════════
# 탭7: 최종 합치기
# ═══════════════════════════════════════════
with tab7:
    st.header("최종 합치기")
    lines = st.session_state.get("script_lines", [])
    images = st.session_state.get("uploaded_images", [])
    videos = st.session_state.get("video_urls", [])
    audios = st.session_state.get("tts_audio_bytes", [])

    st.subheader("진행 상황")
    check_items = {
        "주제 선택": bool(st.session_state.get("selected_topic")),
        "대본 입력": len(lines) > 0,
        "이미지 업로드": len(images) > 0,
        "영상 변환": len(videos) > 0,
        "TTS 음성": len(audios) > 0,
        "자막 스타일": True,
    }
    for item, done in check_items.items():
        if done:
            st.success(f"{item}: 완료")
        else:
            st.warning(f"{item}: 미완료")

    st.divider()
    st.subheader("자막 파일 생성")
    if lines:
        scene_dur = st.session_state.get("scene_dur", 5)
        srt_content = generate_srt(lines, [scene_dur] * len(lines))
        st.download_button("SRT 자막 파일 다운로드", data=srt_content, file_name="subtitles.srt", mime="text/plain", use_container_width=True)
        with st.expander("SRT 미리보기"):
            st.code(srt_content)

    st.divider()
    st.subheader("프로젝트 전체 내보내기")
    if st.button("프로젝트 JSON 생성", key="btn_export_project", use_container_width=True):
        project = {
            "created_at": datetime.now().isoformat(),
            "topic": st.session_state.get("selected_topic", ""),
            "content_type": st.session_state.get("content_type", "쇼츠"),
            "total_scenes": len(lines),
            "script_lines": lines,
            "image_files": [img["name"] for img in images] if images else [],
            "subtitle_style_long": st.session_state.get("subtitle_style_long", {}),
            "subtitle_style_shorts": st.session_state.get("subtitle_style_shorts", {}),
            "scene_duration_sec": st.session_state.get("scene_dur", 5),
        }
        project_json = json.dumps(project, ensure_ascii=False, indent=2)
        st.download_button("프로젝트 JSON 다운로드", data=project_json, file_name=f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True)
        with st.expander("프로젝트 JSON 미리보기"):
            st.code(project_json, language="json")
