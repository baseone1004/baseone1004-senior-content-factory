# ─────────────────────────────────────────────
# 시니어 콘텐츠 팩토리 v3.1
# 파일명: app.py
# 실행: streamlit run app.py
# 모든 API를 Skywork(APIFree) 하나로 통일
# ─────────────────────────────────────────────

import streamlit as st
import requests
import json
import re
import os
import time
import base64
from datetime import datetime

# ═══════════════════════════════════════════════
# 페이지 설정 (반드시 최상단)
# ═══════════════════════════════════════════════

st.set_page_config(page_title="시니어 콘텐츠 팩토리", page_icon="", layout="wide")

# ═══════════════════════════════════════════════
# API 키 로드
# ═══════════════════════════════════════════════

def load_key(name):
    val = os.environ.get(name, "")
    if not val:
        try:
            val = st.secrets.get(name, "")
        except Exception:
            pass
    return val

SKYWORK_API_KEY = load_key("SKYWORK_API_KEY")
RUNWAY_API_KEY = load_key("RUNWAY_API_KEY")
INWORLD_API_KEY = load_key("INWORLD_API_KEY")

# Skywork APIFree 엔드포인트 (OpenAI 호환 - LLM용)
SKYWORK_LLM_BASE = "https://api.apifree.ai"
# Skywork 이미지 생성 엔드포인트
SKYWORK_IMG_ENDPOINT = "https://api-tools.skywork.ai/theme-gateway"
# Runway 엔드포인트
RUNWAY_ENDPOINT = "https://api.runwayml.com/v1"
# Inworld TTS 엔드포인트
INWORLD_TTS_ENDPOINT = "https://studio.inworld.ai/v1/tts"

# ═══════════════════════════════════════════════
# 공통 유틸 함수
# ═══════════════════════════════════════════════

def clean_special(text):
    if not text:
        return ""
    cleaned = re.sub(r'[^\uAC00-\uD7A3\u3131-\u3163\u1100-\u11FFa-zA-Z0-9\s.,?]', '', text)
    return cleaned.strip()


def clean_script_output(full_script):
    if not full_script:
        return ""
    c = full_script
    c = re.sub(r'[=\-─━]{2,}[^\n]*파트[^\n]*[=\-─━]{2,}', '', c)
    c = re.sub(r'【[^】]*파트[^】]*】', '', c)
    c = re.sub(r'[▶▷►][^\n]*파트[^\n]*', '', c)
    c = re.sub(r'#{1,6}\s*파트[^\n]*', '', c)
    c = re.sub(r'\[[^\]]*파트[^\]]*\]', '', c)
    c = re.sub(r'파트\s*[일이삼사오육칠팔구십]\s*[:：]?\s*', '', c)
    c = re.sub(r'파트\s*\d+\s*[:：]?\s*', '', c)
    c = re.sub(r'Part\s*\d+\s*[:：]?\s*', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\*+', '', c)
    c = re.sub(r'#{1,6}\s*', '', c)
    c = re.sub(r'[【】\[\]{}▶▷►◆◇■□●○★☆→←↑↓《》〈〉「」『』\-]', '', c)
    c = re.sub(r'---+', '', c)
    c = re.sub(r'===+', '', c)
    c = re.sub(r'\n\s*\n+', '\n', c)
    return c.strip()


def extract_section(text, section_name):
    pattern = rf'==={section_name}===\s*(.*?)(?====|$)'
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    pattern2 = rf'{section_name}\s*[:：]\s*(.*?)(?=\n[가-힣A-Z]|\n\n|$)'
    m2 = re.search(pattern2, text, re.DOTALL)
    if m2:
        return m2.group(1).strip()
    return ""


def safe_generate(messages, max_tokens=4096, temperature=0.7):
    """Skywork APIFree (OpenAI 호환) 를 통한 LLM 호출"""
    if not SKYWORK_API_KEY:
        st.error("Skywork API 키가 설정되지 않았습니다. .streamlit/secrets.toml 또는 환경변수에 SKYWORK_API_KEY 를 넣어주세요.")
        return ""
    try:
        headers = {
            "Authorization": f"Bearer {SKYWORK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        resp = requests.post(
            f"{SKYWORK_LLM_BASE}/v1/chat/completions",
            headers=headers, json=payload, timeout=180
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            st.error(f"LLM API 오류: {resp.status_code} - {resp.text[:300]}")
            return ""
    except Exception as e:
        st.error(f"LLM 요청 실패: {e}")
        return ""


def generate_image_skywork(prompt, filename="output.png", ref_image_path=None):
    """Skywork 이미지 생성 API 호출"""
    if not SKYWORK_API_KEY:
        st.warning("Skywork API 키가 없습니다.")
        return None
    headers = {
        "Authorization": f"Bearer {SKYWORK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"prompt": prompt, "width": 720, "height": 1280}
    if ref_image_path and os.path.exists(ref_image_path):
        with open(ref_image_path, "rb") as f:
            payload["reference_image"] = base64.b64encode(f.read()).decode()
    try:
        resp = requests.post(SKYWORK_IMG_ENDPOINT, json=payload,
                             headers=headers, timeout=120)
        if resp.status_code == 200:
            result = resp.json()
            img_raw = result.get("image", result.get("data", ""))
            if img_raw:
                img_data = base64.b64decode(img_raw)
                save_dir = "generated_images"
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, filename)
                with open(save_path, "wb") as f:
                    f.write(img_data)
                return save_path
        st.warning(f"이미지 생성 실패: {resp.status_code}")
        return None
    except Exception as e:
        st.warning(f"이미지 요청 실패: {e}")
        return None


def runway_create_task(image_path, motion_prompt=""):
    if not RUNWAY_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json"
    }
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": "gen3a_turbo",
        "promptImage": f"data:image/png;base64,{img_b64}",
        "promptText": motion_prompt if motion_prompt else "subtle camera movement",
        "duration": 5
    }
    try:
        resp = requests.post(f"{RUNWAY_ENDPOINT}/image_to_video",
                             headers=headers, json=payload, timeout=60)
        if resp.status_code in [200, 201]:
            return resp.json().get("id", "")
        return None
    except Exception:
        return None


def runway_check_task(task_id):
    if not RUNWAY_API_KEY or not task_id:
        return None, None
    headers = {"Authorization": f"Bearer {RUNWAY_API_KEY}"}
    try:
        resp = requests.get(f"{RUNWAY_ENDPOINT}/tasks/{task_id}",
                            headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("status", ""), data.get("output", [None])[0]
        return None, None
    except Exception:
        return None, None


def inworld_tts(text, voice="Hyunsoo", speed=1.0, temperature=0.5):
    if not INWORLD_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {INWORLD_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": text, "voice": voice,
        "speed": speed, "temperature": temperature,
        "language": "ko"
    }
    try:
        resp = requests.post(INWORLD_TTS_ENDPOINT,
                             headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception:
        return None


def generate_srt(sentences, avg_per_sentence=3.5):
    srt_lines = []
    current_time = 0.0
    for i, sent in enumerate(sentences):
        if not sent.strip():
            continue
        start = current_time
        duration = max(2.0, len(sent) * 0.12)
        end = start + duration
        sh, sm, ss = int(start // 3600), int((start % 3600) // 60), start % 60
        eh, em, es = int(end // 3600), int((end % 3600) // 60), end % 60
        srt_lines.append(f"{i + 1}")
        srt_lines.append(
            f"{sh:02d}:{sm:02d}:{ss:06.3f} --> {eh:02d}:{em:02d}:{es:06.3f}".replace('.', ','))
        srt_lines.append(sent.strip())
        srt_lines.append("")
        current_time = end + 0.2
    return "\n".join(srt_lines)


# ═══════════════════════════════════════════════
# 세션 초기화
# ═══════════════════════════════════════════════

session_defaults = {
    "selected_topic": "",
    "selected_category": "",
    "topics_list": [],
    "structure": "",
    "parts": {},
    "full_script": "",
    "long_title": "",
    "long_tags": "",
    "long_desc": "",
    "shorts_scripts": [],
    "shorts_scenes": {},
    "longform_link": "",
    "pinned_comments": {},
    "reference_image_path": "",
    "gen_images_long": {},
    "gen_images_shorts": {},
    "runway_tasks": {},
    "tts_audio_long": None,
    "tts_audio_shorts": {},
    "subtitle_style_long": {
        "font": "본고딕 Bold", "size": 48,
        "color": "#FFFFFF", "outline_color": "#000000",
        "outline_width": 3, "position": "하단 중앙", "bg_opacity": 0.0
    },
    "subtitle_style_shorts": {
        "font": "본고딕 Bold", "size": 52,
        "color": "#FFFF00", "outline_color": "#000000",
        "outline_width": 4, "position": "중앙", "bg_opacity": 0.5
    },
}
for k, v in session_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════
# 사이드바: 공통 설정 + 주인공 이미지
# ═══════════════════════════════════════════════

with st.sidebar:
    st.header("공통 설정")

    # API 키 상태 표시
    st.subheader("API 연결 상태")
    if SKYWORK_API_KEY:
        st.success("Skywork API: 연결됨")
    else:
        st.error("Skywork API: 키 없음")
    if RUNWAY_API_KEY:
        st.success("Runway API: 연결됨")
    else:
        st.warning("Runway API: 키 없음 (영상생성 불가)")
    if INWORLD_API_KEY:
        st.success("Inworld API: 연결됨")
    else:
        st.warning("Inworld API: 키 없음 (TTS 불가)")

    st.divider()

    # 주인공 레퍼런스 이미지 업로드
    st.subheader("주인공 레퍼런스 이미지")
    st.caption("쇼츠 이미지 생성 시 주인공 얼굴을 일관되게 유지하기 위한 참조 이미지입니다.")

    ref_img = st.file_uploader(
        "이미지 업로드 (PNG/JPG)",
        type=["png", "jpg", "jpeg"],
        key="sidebar_ref_upload"
    )
    if ref_img:
        save_dir = "reference"
        os.makedirs(save_dir, exist_ok=True)
        ref_path = os.path.join(save_dir, "reference.png")
        with open(ref_path, "wb") as f:
            f.write(ref_img.getvalue())
        st.session_state["reference_image_path"] = ref_path
        st.image(ref_path, caption="현재 레퍼런스", use_container_width=True)
    elif st.session_state.get("reference_image_path") and os.path.exists(st.session_state["reference_image_path"]):
        st.image(st.session_state["reference_image_path"], caption="현재 레퍼런스", use_container_width=True)
    else:
        st.info("아직 업로드된 이미지가 없습니다.")

    st.divider()

    # 현재 선택된 주제 표시
    if st.session_state.get("selected_topic"):
        st.subheader("현재 주제")
        st.write(st.session_state["selected_topic"])
        st.caption(st.session_state.get("selected_category", ""))

# ═══════════════════════════════════════════════
# 메인 타이틀
# ═══════════════════════════════════════════════

st.title("시니어 콘텐츠 팩토리")

# ═══════════════════════════════════════════════
# 탭 구성
# ═══════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "1.주제추천", "2.롱폼대본", "3.쇼츠대본",
    "4.이미지생성", "5.영상생성", "6.TTS",
    "7.자막스타일", "8.최종합치기"
])

# ═══════════════════════════════════════════════
# 탭1: 주제 추천
# ═══════════════════════════════════════════════

with tab1:
    st.header("주제 추천")

    category = st.selectbox("카테고리 선택", [
        "경제/사회",
        "시니어 창작 민담/설화",
        "창작 미스터리/괴담",
        "창작 역사"
    ], key="cat_select")

    extract_prompts = {
        "경제/사회": """시니어 유튜브 채널 주제 기획자로서 최근 한국 경제 사회 이슈 중
시니어 시청자가 관심 가질 만한 주제 10개를 추천하세요.
규칙:
- 제목은 반드시 20자 이내 한글
- 특수기호 물음표 느낌표 금지
- 숫자는 아라비아 숫자
- 핵심 키워드를 앞에 배치
- 한 줄에 하나씩 번호 없이 출력
- 자극적이고 클릭을 유도하는 제목""",

        "시니어 창작 민담/설화": """시니어 유튜브 채널 주제 기획자로서
한국 전통 민담 설화를 현대적으로 재해석한 창작 주제 10개를 추천하세요.
규칙:
- 제목은 반드시 20자 이내 한글
- 특수기호 물음표 느낌표 금지
- 숫자는 아라비아 숫자
- 핵심 키워드를 앞에 배치
- 한 줄에 하나씩 번호 없이 출력
- 시니어 감성에 맞는 서사적 제목""",

        "창작 미스터리/괴담": """시니어 유튜브 채널 주제 기획자로서
한국 배경의 창작 미스터리 괴담 주제 10개를 추천하세요.
규칙:
- 제목은 반드시 20자 이내 한글
- 특수기호 물음표 느낌표 금지
- 숫자는 아라비아 숫자
- 핵심 키워드를 앞에 배치
- 한 줄에 하나씩 번호 없이 출력
- 몰입감 있는 공포 서스펜스 제목""",

        "창작 역사": """시니어 유튜브 채널 주제 기획자로서
한국 역사 속 흥미로운 사건을 재조명하는 주제 10개를 추천하세요.
규칙:
- 제목은 반드시 20자 이내 한글
- 특수기호 물음표 느낌표 금지
- 숫자는 아라비아 숫자
- 핵심 키워드를 앞에 배치
- 한 줄에 하나씩 번호 없이 출력
- 역사적 사실 기반 자극적 제목"""
    }

    if st.button("주제 추천 받기", key="btn_topic"):
        with st.spinner("주제를 추천받는 중..."):
            prompt_text = extract_prompts.get(category, extract_prompts["경제/사회"])
            result = safe_generate([
                {"role": "system", "content": "당신은 시니어 유튜브 채널 전문 기획자입니다. 요청에 맞는 주제만 출력하세요."},
                {"role": "user", "content": prompt_text}
            ], max_tokens=1024, temperature=0.9)
            if result:
                lines = [l.strip() for l in result.strip().split('\n') if l.strip()]
                cleaned = []
                for l in lines:
                    t = re.sub(r'^\d+[\.\)]\s*', '', l)
                    t = re.sub(r'^[-*]\s*', '', t)
                    t = t.strip()
                    if t and len(t) <= 25:
                        cleaned.append(t)
                st.session_state["topics_list"] = cleaned[:10]
                st.session_state["selected_category"] = category

    if st.session_state["topics_list"]:
        st.subheader(f"추천 주제 ({st.session_state.get('selected_category', '')})")
        for i, topic in enumerate(st.session_state["topics_list"]):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{i + 1}. {topic}")
            with col2:
                if st.button("선택", key=f"sel_{i}"):
                    st.session_state["selected_topic"] = topic
                    st.success(f"선택됨: {topic}")

    if st.session_state["selected_topic"]:
        st.info(f"현재 선택된 주제: {st.session_state['selected_topic']}")

# ═══════════════════════════════════════════════
# 탭2: 롱폼 대본
# ═══════════════════════════════════════════════

with tab2:
    st.header("롱폼 대본 생성 (30~40분)")

    if st.session_state["selected_topic"]:
        st.info(f"주제: {st.session_state['selected_topic']} / 카테고리: {st.session_state.get('selected_category', '')}")
    else:
        st.warning("먼저 탭1에서 주제를 선택하세요.")

    part_names = ['일', '이', '삼', '사', '오', '육', '칠', '팔']

    def build_structure_prompt(topic, cat):
        return f"""당신은 30~40분 분량의 시니어 유튜브 롱폼 대본 구조를 설계하는 전문가입니다.

주제: {topic}
카테고리: {cat}

8파트 구조를 설계하세요.

파트 일: 도입부. 충격적 현장 묘사로 시작.
파트 이: 배경 설명. 왜 일어났는지 맥락.
파트 삼: 핵심 원인 분석.
파트 사: 내부 실태와 폭로.
파트 오: 충돌과 갈등. 감정적 클라이맥스.
파트 육: 반전과 새로운 시각.
파트 칠: 현재 상황.
파트 팔: 마무리와 여운.

각 파트별로 핵심 내용 요약 2~3줄을 출력하세요.
전체 감정 곡선도 한 줄로 요약하세요."""

    def build_part_prompt(topic, cat, structure, part_num, part_name):
        return f"""당신은 시니어 유튜브 롱폼 대본 작가입니다.

주제: {topic}
카테고리: {cat}
전체 구조:
{structure}

지금 파트 {part_name} (8파트 중 {part_num}번째)을 작성하세요.

대본 작성 규칙:
- 이 파트는 약 4~5분 분량입니다.
- 30~45개 문장으로 작성하세요.
- 한 문장은 15자에서 50자 사이입니다. 50자 넘으면 두 문장으로 쪼개세요.
- 마침표만 사용하세요. 느낌표 물음표 외 특수기호 금지.
- 물음표는 질문 문장에서만 사용하세요.
- 모든 숫자는 한글로 쓰세요.
- 모든 영어는 한글 순화어로 바꾸세요.
- 습니다체를 기본으로 하되 까요체 질문을 중간중간 넣으세요.
- 파트 제목이나 번호를 대본 안에 절대 쓰지 마세요.
- 소제목을 넣지 마세요.
- 번호 매기기를 하지 마세요.
- 하나의 이야기 흐름으로 자연스럽게 이어가세요.
- 인사 자기소개 구독 좋아요 알림 언급 금지.
- 접속사는 근데 그래서 결국 알고 보니 문제는 만 사용하세요.

파트 헤더나 제목 없이 순수 대본 문장만 출력하세요."""

    def build_meta_prompt(topic, full_script):
        return f"""다음 롱폼 대본의 제목 태그 설명을 만드세요.

주제: {topic}
대본 첫 부분: {full_script[:500]}

===제목===
- 한글 20자 이내 (공백 포함)
- 특수기호 물음표 느낌표 금지
- 숫자는 아라비아 숫자
- 핵심 키워드를 앞에 배치

===태그===
- 쉼표로 구분 15~20개
- 한글로만

===설명===
- 약 200자
- 해시태그 3~5개 포함

위 형식 그대로 출력하세요."""

    if st.button("롱폼 대본 전체 생성", key="btn_longform"):
        topic = st.session_state["selected_topic"]
        cat = st.session_state.get("selected_category", "")
        if not topic:
            st.error("주제를 먼저 선택하세요.")
        else:
            progress = st.progress(0)
            status = st.empty()

            # 구조 설계
            status.text("구조 설계 중...")
            structure = safe_generate([
                {"role": "system", "content": "시니어 유튜브 롱폼 대본 구조 설계 전문가입니다."},
                {"role": "user", "content": build_structure_prompt(topic, cat)}
            ], max_tokens=2048)
            st.session_state["structure"] = structure
            progress.progress(10)

            # 파트별 생성
            all_parts = []
            for i in range(8):
                pname = part_names[i]
                status.text(f"파트 {pname} 생성 중... ({i + 1}/8)")
                part_script = safe_generate([
                    {"role": "system",
                     "content": "시니어 유튜브 롱폼 대본 작가입니다. 파트 제목이나 번호 없이 순수 대본만 출력하세요."},
                    {"role": "user",
                     "content": build_part_prompt(topic, cat, structure, i + 1, pname)}
                ], max_tokens=4096)
                cleaned_part = clean_script_output(part_script)
                st.session_state["parts"][pname] = cleaned_part
                all_parts.append(cleaned_part)
                progress.progress(10 + int((i + 1) * 10))

            # 합치기
            full = "\n".join(all_parts)
            full = clean_script_output(full)
            st.session_state["full_script"] = full
            progress.progress(95)

            # 메타 생성
            status.text("제목 태그 설명 생성 중...")
            meta = safe_generate([
                {"role": "system", "content": "유튜브 메타데이터 전문가입니다."},
                {"role": "user", "content": build_meta_prompt(topic, full)}
            ], max_tokens=1024)

            title_v = extract_section(meta, "제목")
            tags_v = extract_section(meta, "태그")
            desc_v = extract_section(meta, "설명")
            st.session_state["long_title"] = clean_special(title_v) if title_v else topic
            st.session_state["long_tags"] = tags_v
            st.session_state["long_desc"] = desc_v
            progress.progress(100)
            status.text("완료")

    # 결과 표시
    if st.session_state.get("full_script"):
        st.subheader("제목")
        st.code(st.session_state["long_title"], language=None)

        st.subheader("태그")
        st.code(st.session_state["long_tags"], language=None)

        st.subheader("설명")
        st.code(st.session_state["long_desc"], language=None)

        st.subheader("전체 대본 (순수 대본)")
        st.code(st.session_state["full_script"], language=None)

        wc = len(st.session_state["full_script"])
        sc = len([s for s in st.session_state["full_script"].split('.') if s.strip()])
        em = round(sc * 0.12, 1)
        st.caption(f"글자 수: {wc} / 문장 수: {sc} / 예상 시간: 약 {em}분")

# ═══════════════════════════════════════════════
# 탭3: 쇼츠 대본
# ═══════════════════════════════════════════════

with tab3:
    st.header("쇼츠 대본 생성 (3편 세트)")

    if st.session_state["selected_topic"]:
        st.info(f"주제: {st.session_state['selected_topic']}")
    else:
        st.warning("먼저 탭1에서 주제를 선택하세요.")

    longform_link = st.text_input(
        "롱폼 영상 링크 (고정 댓글에 삽입)",
        value=st.session_state.get("longform_link", ""),
        placeholder="https://youtu.be/...",
        key="link_input"
    )
    st.session_state["longform_link"] = longform_link

    # 사이드바에 이미 레퍼런스 이미지가 있음을 안내
    if st.session_state.get("reference_image_path"):
        st.success("주인공 레퍼런스 이미지: 적용됨 (사이드바에서 변경 가능)")
    else:
        st.warning("주인공 레퍼런스 이미지가 없습니다. 왼쪽 사이드바에서 업로드하세요.")

    def build_shorts_prompt(topic, cat):
        return f"""당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가입니다.

대주제: {topic}
카테고리: {cat}

아래 규칙에 따라 쇼츠 3편 세트를 기획하고 각 편마다 대본과 이미지 프롬프트를 작성하세요.

세트 기획 규칙:
- 대주제에서 3개의 소주제를 도출
- 3개는 서로 중복 없이 연관성 높게
- 8가지 관점에서 골고루: 몰락 원인 / 전성기 실태 / 내부 폭로 / 비교 분석 / 수익 구조 / 피해자 시점 / 현재 상황 / 미래 전망

대본 규칙:
- 각 편당 8~15문장
- 첫 문장은 현장 한가운데에 시청자를 던져넣는 문장
- 첫 세 문장 안에 열린 고리 설치
- 접속사는 근데 그래서 결국 알고 보니 문제는 만 사용
- 한 문장 15~40자
- 습니다체 기본에 까요체 질문 혼합
- 번호 매기기 금지 소제목 금지
- 인사 자기소개 구독 좋아요 금지
- 영어 숫자 모두 한글로
- 마침표만 사용
- 마지막 문장은 묵직한 여운 또는 다음 편 유도

이미지 프롬프트 규칙:
- 대사 문장 수와 장면 수 일대일 매칭
- 모든 프롬프트는 SD 2D anime style,로 시작
- 모든 프롬프트는 9:16 vertical aspect ratio로 끝남
- 주인공 등장 장면은 끝에 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 9:16 vertical aspect ratio
- 주인공 미등장 장면은 끝에 9:16 vertical aspect ratio

상단제목 규칙:
- 한 줄당 15자 이내 두 줄
- 숫자는 아라비아 숫자 특수기호 금지

출력 형식:

=001=

제목: (50자 이내)

상단제목 첫째 줄: (15자 이내)
상단제목 둘째 줄: (15자 이내)

설명글: (약 200자 해시태그 3~5개)

태그: (쉼표 구분 15~20개)

순수 대본:
(문장만 마침표로 나열)

=장면001=
대사: (첫 번째 문장)
프롬프트: SD 2D anime style, (영어 묘사), (접미어)

=장면002=
대사: (두 번째 문장)
프롬프트: SD 2D anime style, (영어 묘사), (접미어)

(문장 수만큼 반복)

=002=
(동일 형식)

=003=
(동일 형식)"""

    if st.button("쇼츠 3편 세트 생성", key="btn_shorts"):
        topic = st.session_state["selected_topic"]
        cat = st.session_state.get("selected_category", "")
        if not topic:
            st.error("주제를 먼저 선택하세요.")
        else:
            with st.spinner("쇼츠 3편 생성 중... (약 1~2분)"):
                result = safe_generate([
                    {"role": "system",
                     "content": "유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가입니다. 형식을 정확히 따르세요."},
                    {"role": "user", "content": build_shorts_prompt(topic, cat)}
                ], max_tokens=8192, temperature=0.8)

                if result:
                    shorts_blocks = re.split(r'=00[1-3]=', result)
                    shorts_blocks = [b.strip() for b in shorts_blocks if b.strip()]

                    parsed_shorts = []
                    all_scenes = {}

                    for idx, block in enumerate(shorts_blocks[:3]):
                        short_num = idx + 1
                        title_m = re.search(r'제목:\s*(.+)', block)
                        top1_m = re.search(r'상단제목\s*첫째\s*줄:\s*(.+)', block)
                        top2_m = re.search(r'상단제목\s*둘째\s*줄:\s*(.+)', block)
                        desc_m = re.search(r'설명글:\s*(.+?)(?=태그:|$)', block, re.DOTALL)
                        tags_m = re.search(r'태그:\s*(.+?)(?=순수|$)', block, re.DOTALL)
                        script_m = re.search(r'순수\s*대본[:\s]*(.+?)(?==장면|$)', block, re.DOTALL)

                        scenes = []
                        scene_pat = r'=장면(\d+)=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?==장면|=00|$)'
                        for sm in re.finditer(scene_pat, block, re.DOTALL):
                            scenes.append({
                                "scene_id": sm.group(1).strip(),
                                "dialogue": sm.group(2).strip(),
                                "prompt": sm.group(3).strip()
                            })

                        short_data = {
                            "num": short_num,
                            "title": clean_special(title_m.group(1)) if title_m else f"쇼츠 {short_num}",
                            "top_line1": clean_special(top1_m.group(1)) if top1_m else "",
                            "top_line2": clean_special(top2_m.group(1)) if top2_m else "",
                            "description": desc_m.group(1).strip() if desc_m else "",
                            "tags": tags_m.group(1).strip() if tags_m else "",
                            "script": clean_script_output(script_m.group(1)) if script_m else "",
                            "scenes": scenes
                        }
                        parsed_shorts.append(short_data)
                        all_scenes[short_num] = scenes

                    st.session_state["shorts_scripts"] = parsed_shorts
                    st.session_state["shorts_scenes"] = all_scenes

                    # 고정 댓글 생성
                    if longform_link:
                        for sd in parsed_shorts:
                            summary = sd["script"][:80] if sd["script"] else sd["title"]
                            comment = f"{summary}...\n더 자세한 이야기가 궁금하다면 여기서 확인하세요\n{longform_link}"
                            st.session_state["pinned_comments"][sd["num"]] = comment

    # 결과 표시
    if st.session_state.get("shorts_scripts"):
        for sd in st.session_state["shorts_scripts"]:
            st.subheader(f"쇼츠 {sd['num']}편")
            st.code(f"제목: {sd['title']}", language=None)
            if sd["top_line1"] or sd["top_line2"]:
                st.code(f"상단제목: {sd['top_line1']}\n{sd['top_line2']}", language=None)
            st.code(f"설명글: {sd['description']}", language=None)
            st.code(f"태그: {sd['tags']}", language=None)

            st.write("순수 대본:")
            st.code(sd["script"], language=None)

            if sd["scenes"]:
                with st.expander(f"장면 프롬프트 ({len(sd['scenes'])}개)"):
                    for sc in sd["scenes"]:
                        st.write(f"장면 {sc['scene_id']}")
                        st.write(f"대사: {sc['dialogue']}")
                        st.code(sc["prompt"], language=None)

            if sd["num"] in st.session_state.get("pinned_comments", {}):
                st.write("고정 댓글:")
                st.code(st.session_state["pinned_comments"][sd["num"]], language=None)

            st.divider()

# ═══════════════════════════════════════════════
# 탭4: 이미지 생성
# ═══════════════════════════════════════════════

with tab4:
    st.header("이미지 생성 (Skywork AI)")

    if not SKYWORK_API_KEY:
        st.error("Skywork API 키가 설정되지 않았습니다.")

    # 레퍼런스 이미지 상태 표시
    ref_path = st.session_state.get("reference_image_path", "")
    if ref_path and os.path.exists(ref_path):
        st.success(f"주인공 레퍼런스 이미지: 적용됨")
    else:
        st.warning("주인공 레퍼런스 이미지 없음. 사이드바에서 업로드하면 주인공 장면에 자동 적용됩니다.")

    img_tab_long, img_tab_shorts = st.tabs(["롱폼 이미지", "쇼츠 이미지"])

    with img_tab_long:
        st.subheader("롱폼 대표 이미지 생성")

        long_img_prompt = st.text_area(
            "롱폼 썸네일 프롬프트 (영어)",
            value="SD 2D anime style, dramatic cinematic scene, Korean senior man looking at collapsed building, dark atmosphere, neon signs with Korean text, 16:9 aspect ratio",
            height=100,
            key="long_img_prompt"
        )

        if st.button("롱폼 대표 이미지 생성", key="btn_long_img"):
            with st.spinner("이미지 생성 중..."):
                path = generate_image_skywork(long_img_prompt, "longform_thumb.png")
                if path:
                    st.session_state["gen_images_long"]["thumbnail"] = path
                    st.image(path, caption="롱폼 썸네일", width=400)
                    st.success("생성 완료")
                else:
                    st.error("생성 실패")

    with img_tab_shorts:
        st.subheader("쇼츠 장면 이미지 일괄 생성")

        if not st.session_state.get("shorts_scenes"):
            st.warning("먼저 탭3에서 쇼츠 대본을 생성하세요.")
        else:
            for short_num, scenes in st.session_state["shorts_scenes"].items():
                st.write(f"쇼츠 {short_num}편: {len(scenes)}개 장면")

            if st.button("쇼츠 이미지 일괄 생성", key="btn_shorts_img"):
                total = sum(len(s) for s in st.session_state["shorts_scenes"].values())
                progress = st.progress(0)
                count = 0

                for short_num, scenes in st.session_state["shorts_scenes"].items():
                    st.write(f"쇼츠 {short_num}편 생성 중...")
                    for sc in scenes:
                        prompt = sc.get("prompt", "")
                        sid = sc.get("scene_id", "0")
                        fname = f"shorts_{short_num}_{sid}.png"

                        has_ref = "reference" in prompt.lower() or "main character" in prompt.lower()
                        img_path = generate_image_skywork(
                            prompt, fname,
                            ref_image_path=ref_path if has_ref and ref_path else None
                        )

                        if img_path:
                            sc["image_path"] = img_path
                            key = f"s{short_num}_{sid}"
                            st.session_state["gen_images_shorts"][key] = img_path
                            st.image(img_path,
                                     caption=f"쇼츠{short_num} 장면{sid}: {sc.get('dialogue', '')[:20]}",
                                     width=180)
                        else:
                            st.warning(f"쇼츠{short_num} 장면{sid} 실패")

                        count += 1
                        progress.progress(count / total)
                        time.sleep(1)

                st.success("쇼츠 이미지 일괄 생성 완료")

# ═══════════════════════════════════════════════
# 탭5: 영상 생성 (Runway)
# ═══════════════════════════════════════════════

with tab5:
    st.header("영상 생성 (Runway)")

    if not RUNWAY_API_KEY:
        st.warning("Runway API 키가 설정되지 않았습니다.")

    vid_tab_create, vid_tab_check = st.tabs(["영상 생성 요청", "상태 확인"])

    with vid_tab_create:
        st.subheader("이미지를 영상으로 변환")

        all_images = {}
        for k, v in st.session_state.get("gen_images_long", {}).items():
            all_images[f"롱폼_{k}"] = v
        for k, v in st.session_state.get("gen_images_shorts", {}).items():
            all_images[f"쇼츠_{k}"] = v

        if not all_images:
            st.info("먼저 탭4에서 이미지를 생성하세요.")
        else:
            selected_imgs = st.multiselect("변환할 이미지 선택", list(all_images.keys()), key="vid_select")
            motion = st.text_input("카메라 모션", value="slow zoom in, subtle camera movement", key="motion_input")

            if st.button("영상 생성 시작", key="btn_vid"):
                for img_key in selected_imgs:
                    img_path = all_images[img_key]
                    task_id = runway_create_task(img_path, motion)
                    if task_id:
                        st.session_state["runway_tasks"][img_key] = {
                            "task_id": task_id, "status": "요청됨", "output": None
                        }
                        st.success(f"{img_key}: 작업 ID {task_id}")
                    else:
                        st.error(f"{img_key}: 요청 실패")

    with vid_tab_check:
        st.subheader("영상 생성 상태 확인")

        if not st.session_state.get("runway_tasks"):
            st.info("생성 요청한 작업이 없습니다.")
        else:
            if st.button("전체 상태 확인", key="btn_vid_check"):
                for key, task in st.session_state["runway_tasks"].items():
                    s, o = runway_check_task(task["task_id"])
                    if s:
                        task["status"] = s
                    if o:
                        task["output"] = o

            for key, task in st.session_state["runway_tasks"].items():
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.write(key)
                with c2:
                    st.write(f"상태: {task['status']}")
                with c3:
                    if task.get("output"):
                        st.write(f"[다운로드]({task['output']})")

# ═══════════════════════════════════════════════
# 탭6: TTS (Inworld)
# ═══════════════════════════════════════════════

with tab6:
    st.header("TTS 음성 생성 (Inworld)")

    if not INWORLD_API_KEY:
        st.warning("Inworld API 키가 설정되지 않았습니다.")

    voice_options = {
        "현수 (남성, 차분)": "Hyunsoo",
        "민지 (여성, 밝음)": "Minji",
    }

    tts_tab_long, tts_tab_shorts = st.tabs(["롱폼 TTS", "쇼츠 TTS"])

    with tts_tab_long:
        st.subheader("롱폼 대본 음성 생성")

        voice_sel = st.selectbox("목소리 선택", list(voice_options.keys()), key="tts_voice_long")
        speed = st.slider("속도", 0.5, 2.0, 1.0, 0.1, key="tts_speed_long")
        temp = st.slider("자연스러움", 0.0, 1.0, 0.5, 0.1, key="tts_temp_long")

        if st.button("롱폼 TTS 생성", key="btn_tts_long"):
            script = st.session_state.get("full_script", "")
            if not script:
                st.error("먼저 롱폼 대본을 생성하세요.")
            else:
                with st.spinner("음성 생성 중..."):
                    voice_code = voice_options[voice_sel]
                    audio_data = inworld_tts(script, voice_code, speed, temp)
                    if audio_data:
                        save_dir = "tts_output"
                        os.makedirs(save_dir, exist_ok=True)
                        audio_path = os.path.join(save_dir, "longform_tts.mp3")
                        with open(audio_path, "wb") as f:
                            f.write(audio_data)
                        st.session_state["tts_audio_long"] = audio_path
                        st.audio(audio_data, format="audio/mp3")
                        st.success("TTS 생성 완료")

                        sentences = [s.strip() for s in script.split('.') if s.strip()]
                        srt = generate_srt(sentences)
                        srt_path = os.path.join(save_dir, "longform.srt")
                        with open(srt_path, "w", encoding="utf-8") as f:
                            f.write(srt)
                        st.download_button("SRT 자막 다운로드", srt, "longform.srt", key="dl_srt_long")
                        st.download_button("MP3 다운로드", audio_data, "longform_tts.mp3", key="dl_mp3_long")
                    else:
                        st.error("TTS 생성 실패")

    with tts_tab_shorts:
        st.subheader("쇼츠 대본 음성 생성")

        voice_sel_s = st.selectbox("목소리 선택", list(voice_options.keys()), key="tts_voice_shorts")
        speed_s = st.slider("속도", 0.5, 2.0, 1.1, 0.1, key="tts_speed_shorts")
        temp_s = st.slider("자연스러움", 0.0, 1.0, 0.5, 0.1, key="tts_temp_shorts")

        if not st.session_state.get("shorts_scripts"):
            st.info("먼저 쇼츠 대본을 생성하세요.")
        else:
            if st.button("쇼츠 전체 TTS 생성", key="btn_tts_shorts"):
                voice_code_s = voice_options[voice_sel_s]
                for sd in st.session_state["shorts_scripts"]:
                    script = sd.get("script", "")
                    if not script:
                        continue
                    st.write(f"쇼츠 {sd['num']}편 TTS 생성 중...")
                    audio_data = inworld_tts(script, voice_code_s, speed_s, temp_s)
                    if audio_data:
                        save_dir = "tts_output"
                        os.makedirs(save_dir, exist_ok=True)
                        fname = f"shorts_{sd['num']}_tts.mp3"
                        path = os.path.join(save_dir, fname)
                        with open(path, "wb") as f:
                            f.write(audio_data)
                        st.session_state["tts_audio_shorts"][sd["num"]] = path
                        st.audio(audio_data, format="audio/mp3")
                        st.success(f"쇼츠 {sd['num']}편 완료")
                    else:
                        st.error(f"쇼츠 {sd['num']}편 실패")

# ═══════════════════════════════════════════════
# 탭7: 자막 스타일 (한국어 글씨체)
# ═══════════════════════════════════════════════

with tab7:
    st.header("자막 스타일 설정")

    font_options_kr = [
        "본고딕 Bold",
        "본고딕 Regular",
        "본명조 Bold",
        "본명조 Regular",
        "나눔고딕 Bold",
        "나눔고딕 ExtraBold",
        "나눔고딕 Regular",
        "나눔명조 Bold",
        "나눔명조 Regular",
        "나눔바른고딕 Bold",
        "나눔바른고딕 Regular",
        "나눔스퀘어라운드 Bold",
        "나눔스퀘어라운드 ExtraBold",
        "나눔스퀘어라운드 Regular",
        "나눔손글씨 펜",
        "나눔손글씨 붓",
        "배달의민족 주아",
        "배달의민족 한나는열한살",
        "배달의민족 도현",
        "배달의민족 연성",
        "에스코어드림 Bold",
        "에스코어드림 Medium",
        "에스코어드림 Light",
        "프리텐다드 Bold",
        "프리텐다드 SemiBold",
        "프리텐다드 Regular",
        "마루부리 Bold",
        "마루부리 Regular",
        "검은고딕",
        "이서윤체",
        "여기어때 잘난체",
        "카페24 써라운드",
        "카페24 당당해",
        "카페24 아네모네",
        "쿠키런 Bold",
        "쿠키런 Regular",
        "잉크립퀴드체",
        "학교안심 돋움",
        "학교안심 바탕",
        "강원교육 튼튼체",
    ]

    font_map_to_eng = {
        "본고딕 Bold": "NotoSansKR-Bold",
        "본고딕 Regular": "NotoSansKR-Regular",
        "본명조 Bold": "NotoSerifKR-Bold",
        "본명조 Regular": "NotoSerifKR-Regular",
        "나눔고딕 Bold": "NanumGothicBold",
        "나눔고딕 ExtraBold": "NanumGothicExtraBold",
        "나눔고딕 Regular": "NanumGothic",
        "나눔명조 Bold": "NanumMyeongjoBold",
        "나눔명조 Regular": "NanumMyeongjo",
        "나눔바른고딕 Bold": "NanumBarunGothicBold",
        "나눔바른고딕 Regular": "NanumBarunGothic",
        "나눔스퀘어라운드 Bold": "NanumSquareRoundB",
        "나눔스퀘어라운드 ExtraBold": "NanumSquareRoundEB",
        "나눔스퀘어라운드 Regular": "NanumSquareRoundR",
        "나눔손글씨 펜": "NanumPen",
        "나눔손글씨 붓": "NanumBrush",
        "배달의민족 주아": "BMJUA",
        "배달의민족 한나는열한살": "BMHANNApro",
        "배달의민족 도현": "BMDOHYEON",
        "배달의민족 연성": "BMYeonSung",
        "에스코어드림 Bold": "SCDream5",
        "에스코어드림 Medium": "SCDream4",
        "에스코어드림 Light": "SCDream3",
        "프리텐다드 Bold": "Pretendard-Bold",
        "프리텐다드 SemiBold": "Pretendard-SemiBold",
        "프리텐다드 Regular": "Pretendard-Regular",
        "마루부리 Bold": "MaruBuri-Bold",
        "마루부리 Regular": "MaruBuri-Regular",
        "검은고딕": "BlackHanSans-Regular",
        "이서윤체": "LeeSeoyun",
        "여기어때 잘난체": "Jalnan",
        "카페24 써라운드": "Cafe24Ssurround",
        "카페24 당당해": "Cafe24Dangdanghae",
        "카페24 아네모네": "Cafe24Ohsquare",
        "쿠키런 Bold": "CookieRun-Bold",
        "쿠키런 Regular": "CookieRun-Regular",
        "잉크립퀴드체": "InkLipquid",
        "학교안심 돋움": "HakgyoansimDotum",
        "학교안심 바탕": "HakgyoansimBatang",
        "강원교육 튼튼체": "GangwonEduTunTun",
    }

    position_options_kr = [
        "하단 중앙", "하단 좌측", "하단 우측",
        "중앙",
        "상단 중앙", "상단 좌측", "상단 우측",
    ]

    position_map_to_eng = {
        "하단 중앙": "bottom-center",
        "하단 좌측": "bottom-left",
        "하단 우측": "bottom-right",
        "중앙": "center",
        "상단 중앙": "top-center",
        "상단 좌측": "top-left",
        "상단 우측": "top-right",
    }

    sub_long, sub_shorts = st.tabs(["롱폼 자막", "쇼츠 자막"])

    with sub_long:
        st.subheader("롱폼 자막 스타일")
        c1, c2 = st.columns(2)
        with c1:
            cur_font_l = st.session_state["subtitle_style_long"].get("font", "본고딕 Bold")
            idx_l = font_options_kr.index(cur_font_l) if cur_font_l in font_options_kr else 0
            lf = st.selectbox("글씨체", font_options_kr, index=idx_l, key="sub_font_long")
            ls = st.slider("글씨 크기", 20, 100, st.session_state["subtitle_style_long"]["size"], key="sub_size_long")
            cur_pos_l = st.session_state["subtitle_style_long"].get("position", "하단 중앙")
            idx_pl = position_options_kr.index(cur_pos_l) if cur_pos_l in position_options_kr else 0
            lp = st.selectbox("위치", position_options_kr, index=idx_pl, key="sub_pos_long")
        with c2:
            lc = st.color_picker("글씨 색상", st.session_state["subtitle_style_long"]["color"], key="sub_color_long")
            loc = st.color_picker("테두리 색상", st.session_state["subtitle_style_long"]["outline_color"], key="sub_oc_long")
            low = st.slider("테두리 두께", 0, 10, st.session_state["subtitle_style_long"]["outline_width"], key="sub_ow_long")
            lbo = st.slider("배경 투명도", 0.0, 1.0, st.session_state["subtitle_style_long"]["bg_opacity"], 0.1, key="sub_bo_long")

        st.session_state["subtitle_style_long"] = {
            "font": lf, "font_eng": font_map_to_eng.get(lf, "NotoSansKR-Bold"),
            "size": ls, "color": lc, "outline_color": loc,
            "outline_width": low, "position": lp,
            "position_eng": position_map_to_eng.get(lp, "bottom-center"),
            "bg_opacity": lbo
        }

        st.write("미리보기:")
        st.markdown(f"""<div style="background:rgba(0,0,0,{lbo});padding:10px 20px;display:inline-block;border-radius:5px;">
<span style="font-size:{ls}px;color:{lc};text-shadow:-{low}px -{low}px 0 {loc},{low}px -{low}px 0 {loc},-{low}px {low}px 0 {loc},{low}px {low}px 0 {loc};">
시니어 콘텐츠 팩토리 자막 미리보기</span></div>""", unsafe_allow_html=True)

    with sub_shorts:
        st.subheader("쇼츠 자막 스타일")
        c1, c2 = st.columns(2)
        with c1:
            cur_font_s = st.session_state["subtitle_style_shorts"].get("font", "본고딕 Bold")
            idx_s = font_options_kr.index(cur_font_s) if cur_font_s in font_options_kr else 0
            sf = st.selectbox("글씨체", font_options_kr, index=idx_s, key="sub_font_shorts")
            ss_size = st.slider("글씨 크기", 20, 120, st.session_state["subtitle_style_shorts"]["size"], key="sub_size_shorts")
            cur_pos_s = st.session_state["subtitle_style_shorts"].get("position", "중앙")
            idx_ps = position_options_kr.index(cur_pos_s) if cur_pos_s in position_options_kr else 3
            sp = st.selectbox("위치", position_options_kr, index=idx_ps, key="sub_pos_shorts")
        with c2:
            sc_c = st.color_picker("글씨 색상", st.session_state["subtitle_style_shorts"]["color"], key="sub_color_shorts")
            soc = st.color_picker("테두리 색상", st.session_state["subtitle_style_shorts"]["outline_color"], key="sub_oc_shorts")
            sow = st.slider("테두리 두께", 0, 10, st.session_state["subtitle_style_shorts"]["outline_width"], key="sub_ow_shorts")
            sbo = st.slider("배경 투명도", 0.0, 1.0, st.session_state["subtitle_style_shorts"]["bg_opacity"], 0.1, key="sub_bo_shorts")

        st.session_state["subtitle_style_shorts"] = {
            "font": sf, "font_eng": font_map_to_eng.get(sf, "NotoSansKR-Bold"),
            "size": ss_size, "color": sc_c, "outline_color": soc,
            "outline_width": sow, "position": sp,
            "position_eng": position_map_to_eng.get(sp, "center"),
            "bg_opacity": sbo
        }

        st.write("미리보기:")
        st.markdown(f"""<div style="background:rgba(0,0,0,{sbo});padding:10px 20px;display:inline-block;border-radius:5px;">
<span style="font-size:{ss_size}px;color:{sc_c};text-shadow:-{sow}px -{sow}px 0 {soc},{sow}px -{sow}px 0 {soc},-{sow}px {sow}px 0 {soc},{sow}px {sow}px 0 {soc};">
쇼츠 자막 미리보기</span></div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader("자막 스타일 내보내기")
    if st.button("JSON으로 내보내기", key="btn_export_sub"):
        export_data = {
            "롱폼": st.session_state["subtitle_style_long"],
            "쇼츠": st.session_state["subtitle_style_shorts"]
        }
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.code(json_str, language="json")
        st.download_button("JSON 다운로드", json_str, "subtitle_styles.json",
                           mime="application/json", key="dl_sub_json")

# ═══════════════════════════════════════════════
# 탭8: 최종 합치기
# ═══════════════════════════════════════════════

with tab8:
    st.header("최종 합치기")

    st.subheader("완료 체크리스트")
    checks = {
        "주제 선택": bool(st.session_state.get("selected_topic")),
        "롱폼 대본 생성": bool(st.session_state.get("full_script")),
        "쇼츠 대본 생성": bool(st.session_state.get("shorts_scripts")),
        "주인공 레퍼런스 이미지": bool(st.session_state.get("reference_image_path")),
        "쇼츠 이미지 생성": bool(st.session_state.get("gen_images_shorts")),
        "TTS 음성 (롱폼)": bool(st.session_state.get("tts_audio_long")),
        "TTS 음성 (쇼츠)": bool(st.session_state.get("tts_audio_shorts")),
        "자막 스타일 설정": True,
    }

    for item, done in checks.items():
        status = "완료" if done else "미완료"
        icon = "O" if done else "X"
        st.write(f"[{icon}] {item} - {status}")

    st.divider()
    st.subheader("FFmpeg 합성 명령어")

    stl = st.session_state["subtitle_style_long"]
    sts = st.session_state["subtitle_style_shorts"]

    st.write("롱폼 영상 합성:")
    st.code(f"""ffmpeg -framerate 1/5 -i generated_images/longform_%03d.png \\
  -i tts_output/longform_tts.mp3 \\
  -vf "subtitles=tts_output/longform.srt:force_style='FontName={stl.get('font_eng','NotoSansKR-Bold')},FontSize={stl['size']},PrimaryColour=&H00{stl['color'][1:]}&,OutlineColour=&H00{stl['outline_color'][1:]}&,Outline={stl['outline_width']},Alignment=2'" \\
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest output/longform_final.mp4""", language="bash")

    st.write("쇼츠 영상 합성:")
    for i in range(1, 4):
        st.code(f"""ffmpeg -framerate 1/4 -i generated_images/shorts_{i}_%03d.png \\
  -i tts_output/shorts_{i}_tts.mp3 \\
  -vf "scale=720:1280,subtitles=tts_output/shorts_{i}.srt:force_style='FontName={sts.get('font_eng','NotoSansKR-Bold')},FontSize={sts['size']},PrimaryColour=&H00{sts['color'][1:]}&,OutlineColour=&H00{sts['outline_color'][1:]}&,Outline={sts['outline_width']},Alignment=5'" \\
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest output/shorts_{i}_final.mp4""", language="bash")

    st.divider()
    st.subheader("전체 데이터 내보내기")
    if st.button("전체 프로젝트 JSON 내보내기", key="btn_export_all"):
        export = {
            "주제": st.session_state.get("selected_topic", ""),
            "카테고리": st.session_state.get("selected_category", ""),
            "롱폼": {
                "제목": st.session_state.get("long_title", ""),
                "태그": st.session_state.get("long_tags", ""),
                "설명": st.session_state.get("long_desc", ""),
                "대본": st.session_state.get("full_script", ""),
            },
            "쇼츠": [],
            "자막스타일": {
                "롱폼": st.session_state.get("subtitle_style_long", {}),
                "쇼츠": st.session_state.get("subtitle_style_shorts", {}),
            },
            "고정댓글": {str(k): v for k, v in st.session_state.get("pinned_comments", {}).items()},
            "롱폼링크": st.session_state.get("longform_link", ""),
        }
        for sd in st.session_state.get("shorts_scripts", []):
            export["쇼츠"].append({
                "편번호": sd.get("num"),
                "제목": sd.get("title"),
                "상단제목1": sd.get("top_line1"),
                "상단제목2": sd.get("top_line2"),
                "설명": sd.get("description"),
                "태그": sd.get("tags"),
                "대본": sd.get("script"),
                "장면수": len(sd.get("scenes", [])),
            })

        json_out = json.dumps(export, ensure_ascii=False, indent=2)
        st.code(json_out, language="json")
        st.download_button("프로젝트 JSON 다운로드", json_out,
                           f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json", key="dl_project")
