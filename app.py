# ─────────────────────────────────────────────
# 시니어 콘텐츠 팩토리 v3.4
# 파일명: app.py
# 실행: streamlit run app.py
# API: Skywork(LLM+이미지) / KIE(영상) / Inworld(TTS)
# ─────────────────────────────────────────────

import streamlit as st
import requests
import json
import re
import os
import time
import base64
from datetime import datetime

st.set_page_config(page_title="시니어 콘텐츠 팩토리", page_icon="", layout="wide")

# ═══ API 키 ═══
def load_key(name):
    val = os.environ.get(name, "")
    if not val:
        try:
            val = st.secrets.get(name, "")
        except Exception:
            pass
    return val

SKYWORK_API_KEY = load_key("SKYWORK_API_KEY")
KIE_API_KEY = load_key("KIE_API_KEY")
INWORLD_API_KEY = load_key("INWORLD_API_KEY")

SKYWORK_LLM_BASE = "https://api.apifree.ai"
SKYWORK_IMG_ENDPOINT = "https://api-tools.skywork.ai/theme-gateway"
KIE_BASE = "https://api.kie.ai/api/v1"
INWORLD_TTS_ENDPOINT = "https://studio.inworld.ai/v1/tts"

# ═══ TTS 음성 목록 (한국어 + 일본어) ═══
VOICE_OPTIONS = {
    "현우 (한국어, 남성, 청년)": {"id": "Hyunwoo", "lang": "ko"},
    "민지 (한국어, 여성, 활발)": {"id": "Minji", "lang": "ko"},
    "서준 (한국어, 남성, 중후)": {"id": "Seojun", "lang": "ko"},
    "윤아 (한국어, 여성, 차분)": {"id": "Yoona", "lang": "ko"},
    "아스카 (일본어, 여성, 친근)": {"id": "Asuka", "lang": "ja"},
    "사토시 (일본어, 남성, 극적)": {"id": "Satoshi", "lang": "ja"},
}

# ═══ 글씨체 매핑 ═══
FONT_MAP = {
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
FONT_LIST = list(FONT_MAP.keys())

# ═══ 유틸 함수 ═══
def clean_special(text):
    if not text:
        return ""
    return re.sub(r'[^\uAC00-\uD7A3\u3131-\u3163\u1100-\u11FFa-zA-Z0-9\s.,?]', '', text).strip()

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
    c = re.sub(r'[【】\[\]{}▶▷►◆◇■□●○★☆→←↑↓《》〈〉「」『』]', '', c)
    c = re.sub(r'---+', '', c)
    c = re.sub(r'===+', '', c)
    c = re.sub(r'\n\s*\n+', '\n', c)
    return c.strip()

def extract_section(text, section_name):
    m = re.search(rf'==={section_name}===\s*(.*?)(?====|$)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m2 = re.search(rf'{section_name}\s*[:：]\s*(.*?)(?=\n[가-힣A-Z]|\n\n|$)', text, re.DOTALL)
    if m2:
        return m2.group(1).strip()
    return ""

def safe_generate(messages, max_tokens=4096, temperature=0.7):
    if not SKYWORK_API_KEY:
        st.error("Skywork API 키가 설정되지 않았습니다.")
        return ""
    try:
        resp = requests.post(
            f"{SKYWORK_LLM_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {SKYWORK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-4o", "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            timeout=180)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        st.error(f"LLM API 오류: {resp.status_code}")
        return ""
    except Exception as e:
        st.error(f"LLM 요청 실패: {e}")
        return ""

def generate_image_skywork(prompt, filename="output.png", ref_image_path=None):
    if not SKYWORK_API_KEY:
        return None
    payload = {"prompt": prompt, "width": 720, "height": 1280}
    if ref_image_path and os.path.exists(ref_image_path):
        with open(ref_image_path, "rb") as f:
            payload["reference_image"] = base64.b64encode(f.read()).decode()
    try:
        resp = requests.post(SKYWORK_IMG_ENDPOINT, json=payload,
                             headers={"Authorization": f"Bearer {SKYWORK_API_KEY}", "Content-Type": "application/json"},
                             timeout=120)
        if resp.status_code == 200:
            result = resp.json()
            img_raw = result.get("image", result.get("data", ""))
            if img_raw:
                os.makedirs("generated_images", exist_ok=True)
                path = os.path.join("generated_images", filename)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(img_raw))
                return path
        return None
    except Exception:
        return None

def kie_create_task(image_url, prompt="", duration="5"):
    if not KIE_API_KEY:
        return None
    try:
        resp = requests.post(
            f"{KIE_BASE}/jobs/createTask",
            headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
            json={"model": "kling-2.6/image-to-video",
                  "input": {"prompt": prompt if prompt else "subtle cinematic camera movement, slow zoom",
                            "image_urls": [image_url], "sound": False, "duration": duration}},
            timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("task_id", data.get("task_id", ""))
        return None
    except Exception:
        return None

def kie_check_task(task_id):
    if not KIE_API_KEY or not task_id:
        return None, None
    try:
        resp = requests.post(
            f"{KIE_BASE}/jobs/queryTaskInfo",
            headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
            json={"task_id": task_id}, timeout=30)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            status = data.get("status", "")
            output = data.get("output", {})
            video_url = ""
            if isinstance(output, dict):
                video_url = output.get("video_url", output.get("url", ""))
            elif isinstance(output, list) and output:
                video_url = output[0] if isinstance(output[0], str) else output[0].get("url", "")
            return status, video_url
        return None, None
    except Exception:
        return None, None

def inworld_tts(text, voice="Hyunwoo", speed=1.0, temperature=0.5, lang="ko"):
    if not INWORLD_API_KEY:
        return None
    try:
        resp = requests.post(
            INWORLD_TTS_ENDPOINT,
            headers={"Authorization": f"Bearer {INWORLD_API_KEY}", "Content-Type": "application/json"},
            json={"text": text, "voice": voice, "speed": speed, "temperature": temperature, "language": lang},
            timeout=120)
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception:
        return None

def generate_srt(sentences):
    srt, t = [], 0.0
    for i, s in enumerate(sentences):
        if not s.strip():
            continue
        start, dur = t, max(2.0, len(s) * 0.12)
        end = start + dur
        sh, sm, ss = int(start//3600), int((start%3600)//60), start%60
        eh, em, es = int(end//3600), int((end%3600)//60), end%60
        srt.append(f"{i+1}")
        srt.append(f"{sh:02d}:{sm:02d}:{ss:06.3f} --> {eh:02d}:{em:02d}:{es:06.3f}".replace('.',','))
        srt.append(s.strip())
        srt.append("")
        t = end + 0.2
    return "\n".join(srt)

# ═══ 세션 초기화 ═══
defaults = {
    "selected_topic": "", "selected_category": "", "topics_list": [],
    "structure": "", "parts": {}, "full_script": "",
    "long_title": "", "long_tags": "", "long_desc": "",
    "long_sentences": [], "long_prompts": [],
    "shorts_scripts": [], "shorts_scenes": {},
    "longform_link": "", "pinned_comments": {},
    "reference_image_path": "",
    "gen_images_long": {}, "gen_images_shorts": {},
    "kie_tasks": {},
    "tts_audio_long": None, "tts_audio_shorts": {},
    "subtitle_style_long": {
        "font": "NotoSansKR-Bold", "size": 48,
        "color": "#FFFFFF", "outline_color": "#000000",
        "outline_width": 3, "position": "bottom-center", "bg_opacity": 0.0
    },
    "subtitle_style_shorts": {
        "font": "NotoSansKR-Bold", "size": 52,
        "color": "#FFFF00", "outline_color": "#000000",
        "outline_width": 4, "position": "center", "bg_opacity": 0.5
    },
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══ 사이드바 ═══
with st.sidebar:
    st.header("공통 설정")

    st.subheader("API 연결 상태")
    if SKYWORK_API_KEY:
        st.success("Skywork API: 연결됨")
    else:
        st.error("Skywork API: 키 없음")

    if KIE_API_KEY:
        st.success("KIE API: 연결됨")
    else:
        st.warning("KIE API: 키 없음 (영상생성 불가)")

    if INWORLD_API_KEY:
        st.success("Inworld API: 연결됨")
    else:
        st.warning("Inworld API: 키 없음 (TTS 불가)")

    st.divider()

    st.subheader("주인공 레퍼런스 이미지")
    st.caption("쇼츠 이미지 생성 시 주인공 얼굴을 일관되게 유지하기 위한 참조 이미지입니다.")

    ref_img = st.file_uploader("이미지 업로드 (PNG/JPG)", type=["png", "jpg", "jpeg"], key="sidebar_ref")
    if ref_img:
        os.makedirs("reference", exist_ok=True)
        ref_path = os.path.join("reference", "reference.png")
        with open(ref_path, "wb") as f:
            f.write(ref_img.getvalue())
        st.session_state["reference_image_path"] = ref_path
        st.image(ref_path, caption="현재 레퍼런스", use_container_width=True)
    elif st.session_state.get("reference_image_path") and os.path.exists(st.session_state["reference_image_path"]):
        st.image(st.session_state["reference_image_path"], caption="현재 레퍼런스", use_container_width=True)
    else:
        st.info("아직 업로드된 이미지가 없습니다.")

    st.divider()

    if st.session_state.get("selected_topic"):
        st.subheader("현재 주제")
        st.write(st.session_state["selected_topic"])
        st.caption(st.session_state.get("selected_category", ""))


# ═══ 메인 ═══
st.title("시니어 콘텐츠 팩토리")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "1.주제추천", "2.롱폼대본", "3.쇼츠대본",
    "4.이미지생성", "5.영상생성", "6.TTS",
    "7.자막스타일", "8.최종합치기"
])

# ═══ 탭1: 주제 추천 ═══
with tab1:
    st.header("주제 추천")
    category = st.selectbox("카테고리 선택", ["경제/사회","시니어 창작 민담/설화","창작 미스터리/괴담","창작 역사"], key="cat_select")
    extract_prompts = {
        "경제/사회": "시니어 유튜브 채널 주제 기획자로서 최근 한국 경제 사회 이슈 중 시니어 시청자가 관심 가질 만한 주제 10개를 추천하세요.\n규칙:\n- 제목은 반드시 20자 이내 한글\n- 특수기호 물음표 느낌표 금지\n- 숫자는 아라비아 숫자\n- 핵심 키워드를 앞에 배치\n- 한 줄에 하나씩 번호 없이 출력\n- 자극적이고 클릭을 유도하는 제목",
        "시니어 창작 민담/설화": "시니어 유튜브 채널 주제 기획자로서 한국 전통 민담 설화를 현대적으로 재해석한 창작 주제 10개를 추천하세요.\n규칙:\n- 제목은 반드시 20자 이내 한글\n- 특수기호 물음표 느낌표 금지\n- 숫자는 아라비아 숫자\n- 핵심 키워드를 앞에 배치\n- 한 줄에 하나씩 번호 없이 출력\n- 시니어 감성에 맞는 서사적 제목",
        "창작 미스터리/괴담": "시니어 유튜브 채널 주제 기획자로서 한국 배경의 창작 미스터리 괴담 주제 10개를 추천하세요.\n규칙:\n- 제목은 반드시 20자 이내 한글\n- 특수기호 물음표 느낌표 금지\n- 숫자는 아라비아 숫자\n- 핵심 키워드를 앞에 배치\n- 한 줄에 하나씩 번호 없이 출력\n- 몰입감 있는 공포 서스펜스 제목",
        "창작 역사": "시니어 유튜브 채널 주제 기획자로서 한국 역사 속 흥미로운 사건을 재조명하는 주제 10개를 추천하세요.\n규칙:\n- 제목은 반드시 20자 이내 한글\n- 특수기호 물음표 느낌표 금지\n- 숫자는 아라비아 숫자\n- 핵심 키워드를 앞에 배치\n- 한 줄에 하나씩 번호 없이 출력\n- 역사적 사실 기반 자극적 제목"
    }
    if st.button("주제 추천 받기", key="btn_topic"):
        with st.spinner("주제를 추천받는 중..."):
            result = safe_generate([
                {"role":"system","content":"시니어 유튜브 채널 전문 기획자입니다. 요청에 맞는 주제만 출력하세요."},
                {"role":"user","content": extract_prompts.get(category, extract_prompts["경제/사회"])}
            ], max_tokens=1024, temperature=0.9)
            if result:
                lines = [re.sub(r'^[\d\.\)\-\*]\s*','',l).strip() for l in result.strip().split('\n') if l.strip()]
                st.session_state["topics_list"] = [t for t in lines if t and len(t)<=25][:10]
                st.session_state["selected_category"] = category
    if st.session_state["topics_list"]:
        st.subheader(f"추천 주제 ({st.session_state.get('selected_category','')})")
        for i, topic in enumerate(st.session_state["topics_list"]):
            c1, c2 = st.columns([5,1])
            with c1:
                st.write(f"{i+1}. {topic}")
            with c2:
                if st.button("선택", key=f"sel_{i}"):
                    st.session_state["selected_topic"] = topic
                    st.success(f"선택됨: {topic}")
    if st.session_state["selected_topic"]:
        st.info(f"현재 선택된 주제: {st.session_state['selected_topic']}")

# ═══ 탭2: 롱폼 대본 ═══
with tab2:
    st.header("롱폼 대본 생성 (30~40분)")
    if st.session_state["selected_topic"]:
        st.info(f"주제: {st.session_state['selected_topic']} / 카테고리: {st.session_state.get('selected_category','')}")
    else:
        st.warning("먼저 탭1에서 주제를 선택하세요.")

    part_names = ['일','이','삼','사','오','육','칠','팔']

    def build_structure_prompt(topic, cat):
        return f"""30~40분 분량의 시니어 유튜브 롱폼 대본 구조를 설계하세요.
주제: {topic} / 카테고리: {cat}
파트 일: 도입부. 충격적 현장 묘사.
파트 이: 배경 설명. 맥락.
파트 삼: 핵심 원인 분석.
파트 사: 내부 실태와 폭로.
파트 오: 충돌과 갈등. 클라이맥스.
파트 육: 반전과 새로운 시각.
파트 칠: 현재 상황.
파트 팔: 마무리와 여운.
각 파트별 핵심 내용 요약 2~3줄 출력. 감정 곡선 한 줄 요약."""

    def build_part_prompt(topic, cat, structure, part_num, part_name):
        return f"""시니어 유튜브 롱폼 대본 작가입니다.
주제: {topic} / 카테고리: {cat}
전체 구조:
{structure}
파트 {part_name} (8파트 중 {part_num}번째) 작성.
규칙:
- 약 4~5분 분량. 30~45개 문장.
- 한 문장 15~50자. 50자 넘으면 쪼개기.
- 마침표만 사용. 물음표는 질문만.
- 숫자 한글. 영어 순화어.
- 습니다체 기본 + 까요체 질문.
- 파트 제목 번호 소제목 금지.
- 인사 자기소개 구독 좋아요 금지.
- 접속사는 근데 그래서 결국 알고 보니 문제는 만.
순수 대본 문장만 출력."""

    def build_meta_prompt(topic, full_script):
        return f"""롱폼 대본의 제목 태그 설명을 만드세요.
주제: {topic}
대본 첫 부분: {full_script[:500]}
===제목===
한글 20자 이내. 특수기호 물음표 느낌표 금지. 숫자 아라비아. 핵심 키워드 앞 배치.
===태그===
쉼표 구분 15~20개. 한글.
===설명===
약 200자. 해시태그 3~5개.
위 형식 그대로 출력."""

    if st.button("롱폼 대본 전체 생성", key="btn_longform"):
        topic = st.session_state["selected_topic"]
        cat = st.session_state.get("selected_category","")
        if not topic:
            st.error("주제를 먼저 선택하세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.text("구조 설계 중...")
            structure = safe_generate([
                {"role":"system","content":"시니어 유튜브 롱폼 대본 구조 설계 전문가입니다."},
                {"role":"user","content": build_structure_prompt(topic, cat)}
            ], max_tokens=2048)
            st.session_state["structure"] = structure
            progress.progress(10)

            all_parts = []
            for i in range(8):
                pname = part_names[i]
                status.text(f"파트 {pname} 생성 중... ({i+1}/8)")
                part = safe_generate([
                    {"role":"system","content":"시니어 유튜브 롱폼 대본 작가입니다. 파트 제목 번호 없이 순수 대본만 출력."},
                    {"role":"user","content": build_part_prompt(topic, cat, structure, i+1, pname)}
                ], max_tokens=4096)
                cleaned = clean_script_output(part)
                st.session_state["parts"][pname] = cleaned
                all_parts.append(cleaned)
                progress.progress(10 + int((i+1)*10))

            full = clean_script_output("\n".join(all_parts))
            st.session_state["full_script"] = full
            sentences = [s.strip() for s in full.split('.') if s.strip() and len(s.strip()) > 3]
            st.session_state["long_sentences"] = sentences
            progress.progress(95)

            status.text("제목 태그 설명 생성 중...")
            meta = safe_generate([
                {"role":"system","content":"유튜브 메타데이터 전문가입니다."},
                {"role":"user","content": build_meta_prompt(topic, full)}
            ], max_tokens=1024)
            st.session_state["long_title"] = clean_special(extract_section(meta,"제목")) or topic
            st.session_state["long_tags"] = extract_section(meta,"태그")
            st.session_state["long_desc"] = extract_section(meta,"설명")
            progress.progress(100)
            status.text("완료")

    if st.session_state.get("full_script"):
        st.subheader("제목")
        st.code(st.session_state["long_title"], language=None)
        st.subheader("태그")
        st.code(st.session_state["long_tags"], language=None)
        st.subheader("설명")
        st.code(st.session_state["long_desc"], language=None)
        st.subheader("전체 대본 (순수 대본)")
        st.code(st.session_state["full_script"], language=None)
        sc = len(st.session_state.get("long_sentences",[]))
        st.caption(f"글자 수: {len(st.session_state['full_script'])} / 문장 수: {sc} / 예상 시간: 약 {round(sc*0.12,1)}분")
# ═══ 탭3: 쇼츠 대본 ═══
with tab3:
    st.header("쇼츠 대본 생성 (3편 세트)")
    if st.session_state["selected_topic"]:
        st.info(f"주제: {st.session_state['selected_topic']}")
    else:
        st.warning("먼저 탭1에서 주제를 선택하세요.")

    longform_link = st.text_input("롱폼 영상 링크 (고정 댓글에 삽입)",
                                   value=st.session_state.get("longform_link",""),
                                   placeholder="https://youtu.be/...", key="link_input")
    st.session_state["longform_link"] = longform_link

    if st.session_state.get("reference_image_path"):
        st.success("주인공 레퍼런스 이미지: 적용됨 (사이드바에서 변경 가능)")
    else:
        st.warning("주인공 레퍼런스 이미지가 없습니다. 왼쪽 사이드바에서 업로드하세요.")

    def build_shorts_prompt(topic, cat):
        return f"""유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가입니다.
대주제: {topic} / 카테고리: {cat}

쇼츠 3편 세트를 기획하고 각 편마다 대본과 이미지 프롬프트를 작성하세요.

세트 기획: 대주제에서 3개 소주제 도출. 중복 없이 연관성 높게.
8가지 관점에서 골고루: 몰락 원인 / 전성기 실태 / 내부 폭로 / 비교 분석 / 수익 구조 / 피해자 시점 / 현재 상황 / 미래 전망

대본 규칙: 각 편 8~15문장. 첫 문장은 현장 투척. 첫 3문장 열린 고리. 접속사 근데 그래서 결국 알고 보니 문제는. 한 문장 15~40자. 습니다+까요. 번호 소제목 인사 구독 금지. 영어 숫자 한글. 마침표만. 마지막 묵직한 여운.

이미지 프롬프트: 문장수=장면수. SD 2D anime style,로 시작. 9:16 vertical aspect ratio로 끝. 주인공 등장시 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 9:16 vertical aspect ratio

상단제목: 한 줄 15자 이내 두 줄. 숫자 아라비아. 특수기호 금지.

출력 형식:
=001=
제목: (50자 이내)
상단제목 첫째 줄: (15자 이내)
상단제목 둘째 줄: (15자 이내)
설명글: (200자 해시태그 3~5개)
태그: (쉼표 구분 15~20개)
순수 대본:
(문장만 마침표로 나열)
=장면001=
대사: (첫 번째 문장)
프롬프트: SD 2D anime style, (영어), (접미어)
(문장 수만큼 반복)
=002= (동일) =003= (동일)"""

    if st.button("쇼츠 3편 세트 생성", key="btn_shorts"):
        topic = st.session_state["selected_topic"]
        cat = st.session_state.get("selected_category","")
        if not topic:
            st.error("주제를 먼저 선택하세요.")
        else:
            with st.spinner("쇼츠 3편 생성 중... (약 1~2분)"):
                result = safe_generate([
                    {"role":"system","content":"유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가입니다. 형식을 정확히 따르세요."},
                    {"role":"user","content": build_shorts_prompt(topic, cat)}
                ], max_tokens=8192, temperature=0.8)
                if result:
                    blocks = [b.strip() for b in re.split(r'=00[1-3]=', result) if b.strip()]
                    parsed, all_sc = [], {}
                    for idx, block in enumerate(blocks[:3]):
                        sn = idx + 1
                        title_m = re.search(r'제목:\s*(.+)', block)
                        top1_m = re.search(r'상단제목\s*첫째\s*줄:\s*(.+)', block)
                        top2_m = re.search(r'상단제목\s*둘째\s*줄:\s*(.+)', block)
                        desc_m = re.search(r'설명글:\s*(.+?)(?=태그:|$)', block, re.DOTALL)
                        tags_m = re.search(r'태그:\s*(.+?)(?=순수|$)', block, re.DOTALL)
                        script_m = re.search(r'순수\s*대본[:\s]*(.+?)(?==장면|$)', block, re.DOTALL)
                        scenes = []
                        for sm in re.finditer(r'=장면(\d+)=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?==장면|=00|$)', block, re.DOTALL):
                            scenes.append({"scene_id":sm.group(1).strip(),"dialogue":sm.group(2).strip(),"prompt":sm.group(3).strip()})
                        sd = {
                            "num": sn,
                            "title": clean_special(title_m.group(1)) if title_m else f"쇼츠 {sn}",
                            "top_line1": clean_special(top1_m.group(1)) if top1_m else "",
                            "top_line2": clean_special(top2_m.group(1)) if top2_m else "",
                            "description": desc_m.group(1).strip() if desc_m else "",
                            "tags": tags_m.group(1).strip() if tags_m else "",
                            "script": clean_script_output(script_m.group(1)) if script_m else "",
                            "scenes": scenes
                        }
                        parsed.append(sd)
                        all_sc[sn] = scenes
                    st.session_state["shorts_scripts"] = parsed
                    st.session_state["shorts_scenes"] = all_sc
                    if longform_link:
                        for sd in parsed:
                            summary = sd["script"][:80] if sd["script"] else sd["title"]
                            st.session_state["pinned_comments"][sd["num"]] = f"{summary}...\n더 자세한 이야기가 궁금하다면 여기서 확인하세요\n{longform_link}"

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
            if sd["num"] in st.session_state.get("pinned_comments",{}):
                st.write("고정 댓글:")
                st.code(st.session_state["pinned_comments"][sd["num"]], language=None)
            st.divider()

# ═══ 탭4: 이미지 생성 ═══
with tab4:
    st.header("이미지 생성 (Skywork AI)")
    ref_path = st.session_state.get("reference_image_path","")
    if ref_path and os.path.exists(ref_path):
        st.success("주인공 레퍼런스 이미지: 적용됨")
    else:
        st.warning("주인공 레퍼런스 없음. 사이드바에서 업로드하면 주인공 장면에 자동 적용.")

    img_tab_long, img_tab_shorts = st.tabs(["롱폼 이미지", "쇼츠 이미지"])

    with img_tab_long:
        st.subheader("롱폼 문장별 이미지 생성")

        sentences = st.session_state.get("long_sentences", [])
        if not sentences:
            st.warning("먼저 탭2에서 롱폼 대본을 생성하세요.")
        else:
            st.write(f"총 {len(sentences)}개 문장에 대한 이미지를 생성합니다.")
            st.caption("먼저 문장별 이미지 프롬프트를 자동 생성한 뒤, 일괄 이미지를 생성합니다.")

            if st.button("문장별 프롬프트 자동 생성", key="btn_long_prompts"):
                prompts_all = []
                batch_size = 30
                total_batches = (len(sentences) + batch_size - 1) // batch_size
                progress = st.progress(0)

                for b in range(total_batches):
                    batch = sentences[b*batch_size : (b+1)*batch_size]
                    numbered = "\n".join([f"{b*batch_size+j+1}. {s}" for j, s in enumerate(batch)])
                    prompt_req = f"""다음 한국어 대본 문장들에 대해 각각 이미지 프롬프트를 영어로 만들어주세요.

규칙:
- 각 프롬프트는 SD 2D anime style,로 시작
- 각 프롬프트는 16:9 horizontal aspect ratio로 끝남
- 문장 내용에 맞는 장면을 시각적으로 묘사
- 한국적 배경과 분위기 반영
- 한 줄에 하나씩 번호와 함께 출력
- 번호. 프롬프트 형식으로만 출력

문장들:
{numbered}"""
                    result = safe_generate([
                        {"role":"system","content":"이미지 프롬프트 전문가입니다. 번호와 프롬프트만 출력하세요."},
                        {"role":"user","content": prompt_req}
                    ], max_tokens=4096, temperature=0.7)
                    if result:
                        for line in result.strip().split('\n'):
                            line = line.strip()
                            m = re.match(r'\d+[\.\)]\s*(.+)', line)
                            if m:
                                prompts_all.append(m.group(1).strip())
                    progress.progress((b+1)/total_batches)

                if len(prompts_all) < len(sentences):
                    for _ in range(len(sentences) - len(prompts_all)):
                        prompts_all.append("SD 2D anime style, Korean cityscape, moody atmosphere, 16:9 horizontal aspect ratio")

                st.session_state["long_prompts"] = prompts_all[:len(sentences)]
                st.success(f"프롬프트 {len(st.session_state['long_prompts'])}개 생성 완료")

            if st.session_state.get("long_prompts"):
                with st.expander(f"프롬프트 목록 ({len(st.session_state['long_prompts'])}개)"):
                    for i, p in enumerate(st.session_state["long_prompts"]):
                        st.text(f"{i+1}. {p[:100]}...")

                if st.button("롱폼 이미지 일괄 생성", key="btn_long_img_all"):
                    prompts = st.session_state["long_prompts"]
                    total = len(prompts)
                    progress = st.progress(0)
                    for i, p in enumerate(prompts):
                        fname = f"long_{i+1:04d}.png"
                        path = generate_image_skywork(p, fname)
                        if path:
                            st.session_state["gen_images_long"][f"long_{i+1}"] = path
                            if (i+1) % 10 == 0:
                                st.write(f"{i+1}/{total} 생성 완료")
                        progress.progress((i+1)/total)
                        time.sleep(0.5)
                    st.success(f"롱폼 이미지 {len(st.session_state['gen_images_long'])}개 생성 완료")

    with img_tab_shorts:
        st.subheader("쇼츠 장면 이미지 일괄 생성")
        if not st.session_state.get("shorts_scenes"):
            st.warning("먼저 탭3에서 쇼츠 대본을 생성하세요.")
        else:
            for sn, scenes in st.session_state["shorts_scenes"].items():
                st.write(f"쇼츠 {sn}편: {len(scenes)}개 장면")
            if st.button("쇼츠 이미지 일괄 생성", key="btn_shorts_img"):
                total = sum(len(s) for s in st.session_state["shorts_scenes"].values())
                progress = st.progress(0)
                count = 0
                for sn, scenes in st.session_state["shorts_scenes"].items():
                    st.write(f"쇼츠 {sn}편 생성 중...")
                    for sc in scenes:
                        prompt = sc.get("prompt","")
                        sid = sc.get("scene_id","0")
                        fname = f"shorts_{sn}_{sid}.png"
                        has_ref = "reference" in prompt.lower() or "main character" in prompt.lower()
                        path = generate_image_skywork(prompt, fname,
                                                      ref_image_path=ref_path if has_ref and ref_path else None)
                        if path:
                            sc["image_path"] = path
                            st.session_state["gen_images_shorts"][f"s{sn}_{sid}"] = path
                            st.image(path, caption=f"쇼츠{sn} 장면{sid}: {sc.get('dialogue','')[:20]}", width=180)
                        count += 1
                        progress.progress(count/total)
                        time.sleep(1)
                st.success("쇼츠 이미지 일괄 생성 완료")

# ═══ 탭5: 영상 생성 (Kling AI / KIE) ═══
with tab5:
    st.header("영상 생성 (Kling AI)")
    if not KIE_API_KEY:
        st.warning("KIE API 키가 설정되지 않았습니다.")

    vid_create, vid_check = st.tabs(["영상 생성 요청", "상태 확인"])

    with vid_create:
        st.subheader("이미지를 영상으로 변환 (Kling 2.6)")
        all_images = {}
        for k, v in st.session_state.get("gen_images_long",{}).items():
            all_images[f"롱폼_{k}"] = v
        for k, v in st.session_state.get("gen_images_shorts",{}).items():
            all_images[f"쇼츠_{k}"] = v

        if not all_images:
            st.info("먼저 탭4에서 이미지를 생성하세요.")
        else:
            selected = st.multiselect("변환할 이미지 선택", list(all_images.keys()), key="vid_select")
            motion = st.text_input("카메라 모션 프롬프트", value="subtle cinematic camera movement, slow zoom in", key="motion_input")
            dur = st.selectbox("영상 길이", ["5","10"], key="vid_dur")

            if st.button("영상 생성 시작", key="btn_vid"):
                for img_key in selected:
                    img_path = all_images[img_key]
                    with open(img_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode()
                    img_url = f"data:image/png;base64,{img_b64}"
                    task_id = kie_create_task(img_url, motion, dur)
                    if task_id:
                        st.session_state["kie_tasks"][img_key] = {"task_id": task_id, "status": "요청됨", "output": None}
                        st.success(f"{img_key}: 작업 ID {task_id[:20]}...")
                    else:
                        st.error(f"{img_key}: 요청 실패")

    with vid_check:
        st.subheader("영상 생성 상태 확인")
        if not st.session_state.get("kie_tasks"):
            st.info("생성 요청한 작업이 없습니다.")
        else:
            if st.button("전체 상태 확인", key="btn_vid_check"):
                for key, task in st.session_state["kie_tasks"].items():
                    s, o = kie_check_task(task["task_id"])
                    if s:
                        task["status"] = s
                    if o:
                        task["output"] = o
            for key, task in st.session_state["kie_tasks"].items():
                c1, c2, c3 = st.columns([3,2,2])
                with c1:
                    st.write(key)
                with c2:
                    st.write(f"상태: {task['status']}")
                with c3:
                    if task.get("output"):
                        st.markdown(f"[다운로드]({task['output']})")
# ═══ 탭6: TTS (Inworld) ═══
with tab6:
    st.header("TTS 음성 생성 (Inworld)")
    if not INWORLD_API_KEY:
        st.warning("Inworld API 키가 설정되지 않았습니다.")

    tts_long, tts_shorts = st.tabs(["롱폼 TTS", "쇼츠 TTS"])

    with tts_long:
        st.subheader("롱폼 대본 음성 생성")
        voice_sel = st.selectbox("목소리 선택", list(VOICE_OPTIONS.keys()), key="tts_voice_long")
        speed = st.slider("속도", 0.5, 2.0, 1.0, 0.1, key="tts_speed_long")
        temp = st.slider("자연스러움", 0.0, 1.0, 0.5, 0.1, key="tts_temp_long")

        if st.button("롱폼 TTS 생성", key="btn_tts_long"):
            script = st.session_state.get("full_script","")
            if not script:
                st.error("먼저 롱폼 대본을 생성하세요.")
            else:
                with st.spinner("음성 생성 중..."):
                    vi = VOICE_OPTIONS[voice_sel]
                    audio = inworld_tts(script, vi["id"], speed, temp, vi["lang"])
                    if audio:
                        os.makedirs("tts_output", exist_ok=True)
                        apath = os.path.join("tts_output","longform_tts.mp3")
                        with open(apath,"wb") as f:
                            f.write(audio)
                        st.session_state["tts_audio_long"] = apath
                        st.audio(audio, format="audio/mp3")
                        st.success("TTS 생성 완료")
                        sents = [s.strip() for s in script.split('.') if s.strip()]
                        srt = generate_srt(sents)
                        st.download_button("SRT 자막 다운로드", srt, "longform.srt", key="dl_srt_l")
                        st.download_button("MP3 다운로드", audio, "longform_tts.mp3", key="dl_mp3_l")
                    else:
                        st.error("TTS 생성 실패")

    with tts_shorts:
        st.subheader("쇼츠 대본 음성 생성")
        voice_sel_s = st.selectbox("목소리 선택", list(VOICE_OPTIONS.keys()), key="tts_voice_shorts")
        speed_s = st.slider("속도", 0.5, 2.0, 1.1, 0.1, key="tts_speed_shorts")
        temp_s = st.slider("자연스러움", 0.0, 1.0, 0.5, 0.1, key="tts_temp_shorts")

        if not st.session_state.get("shorts_scripts"):
            st.info("먼저 쇼츠 대본을 생성하세요.")
        else:
            if st.button("쇼츠 전체 TTS 생성", key="btn_tts_shorts"):
                vi_s = VOICE_OPTIONS[voice_sel_s]
                for sd in st.session_state["shorts_scripts"]:
                    script = sd.get("script","")
                    if not script:
                        continue
                    st.write(f"쇼츠 {sd['num']}편 TTS 생성 중...")
                    audio = inworld_tts(script, vi_s["id"], speed_s, temp_s, vi_s["lang"])
                    if audio:
                        os.makedirs("tts_output", exist_ok=True)
                        path = os.path.join("tts_output",f"shorts_{sd['num']}_tts.mp3")
                        with open(path,"wb") as f:
                            f.write(audio)
                        st.session_state["tts_audio_shorts"][sd["num"]] = path
                        st.audio(audio, format="audio/mp3")
                        st.success(f"쇼츠 {sd['num']}편 완료")
                    else:
                        st.error(f"쇼츠 {sd['num']}편 실패")

# ═══ 탭7: 자막 스타일 (글씨체 목록만 한국어로 변경, 나머지 원래대로) ═══
with tab7:
    st.header("Subtitle Style Settings")

    sub_long, sub_shorts = st.tabs(["Longform", "Shorts"])

    with sub_long:
        st.subheader("Longform Subtitle Style")
        col1, col2 = st.columns(2)
        with col1:
            cur_font_eng = st.session_state["subtitle_style_long"].get("font","NotoSansKR-Bold")
            reverse_map = {v:k for k,v in FONT_MAP.items()}
            cur_font_kr = reverse_map.get(cur_font_eng, FONT_LIST[0])
            idx_l = FONT_LIST.index(cur_font_kr) if cur_font_kr in FONT_LIST else 0
            lf = st.selectbox("Font", FONT_LIST, index=idx_l, key="sub_font_long")
            ls = st.slider("Size", 20, 100, st.session_state["subtitle_style_long"]["size"], key="sub_size_long")
        with col2:
            lc = st.color_picker("Color", st.session_state["subtitle_style_long"]["color"], key="sub_color_long")
            loc = st.color_picker("Outline Color", st.session_state["subtitle_style_long"]["outline_color"], key="sub_oc_long")
            low = st.slider("Outline Width", 0, 10, st.session_state["subtitle_style_long"]["outline_width"], key="sub_ow_long")

        pos_opts = ["bottom-center","bottom-left","bottom-right","center","top-center","top-left","top-right"]
        cur_pos = st.session_state["subtitle_style_long"].get("position","bottom-center")
        lp = st.selectbox("Position", pos_opts, index=pos_opts.index(cur_pos) if cur_pos in pos_opts else 0, key="sub_pos_long")
        lbo = st.slider("BG Opacity", 0.0, 1.0, st.session_state["subtitle_style_long"]["bg_opacity"], 0.1, key="sub_bo_long")

        st.session_state["subtitle_style_long"] = {
            "font": FONT_MAP.get(lf,"NotoSansKR-Bold"), "size": ls, "color": lc,
            "outline_color": loc, "outline_width": low, "position": lp, "bg_opacity": lbo
        }

        st.write("Preview:")
        st.markdown(f'<div style="background:rgba(0,0,0,{lbo});padding:10px 20px;display:inline-block;border-radius:5px;">'
                    f'<span style="font-size:{ls}px;color:{lc};text-shadow:-{low}px -{low}px 0 {loc},{low}px -{low}px 0 {loc},'
                    f'-{low}px {low}px 0 {loc},{low}px {low}px 0 {loc};">'
                    f'시니어 콘텐츠 팩토리 자막 미리보기</span></div>', unsafe_allow_html=True)

    with sub_shorts:
        st.subheader("Shorts Subtitle Style")
        col1, col2 = st.columns(2)
        with col1:
            cur_font_eng_s = st.session_state["subtitle_style_shorts"].get("font","NotoSansKR-Bold")
            cur_font_kr_s = reverse_map.get(cur_font_eng_s, FONT_LIST[0])
            idx_s = FONT_LIST.index(cur_font_kr_s) if cur_font_kr_s in FONT_LIST else 0
            sf = st.selectbox("Font", FONT_LIST, index=idx_s, key="sub_font_shorts")
            ss_size = st.slider("Size", 20, 120, st.session_state["subtitle_style_shorts"]["size"], key="sub_size_shorts")
        with col2:
            sc_c = st.color_picker("Color", st.session_state["subtitle_style_shorts"]["color"], key="sub_color_shorts")
            soc = st.color_picker("Outline Color", st.session_state["subtitle_style_shorts"]["outline_color"], key="sub_oc_shorts")
            sow = st.slider("Outline Width", 0, 10, st.session_state["subtitle_style_shorts"]["outline_width"], key="sub_ow_shorts")

        sp = st.selectbox("Position", pos_opts, index=pos_opts.index(st.session_state["subtitle_style_shorts"].get("position","center")) if st.session_state["subtitle_style_shorts"].get("position","center") in pos_opts else 3, key="sub_pos_shorts")
        sbo = st.slider("BG Opacity", 0.0, 1.0, st.session_state["subtitle_style_shorts"]["bg_opacity"], 0.1, key="sub_bo_shorts")

        st.session_state["subtitle_style_shorts"] = {
            "font": FONT_MAP.get(sf,"NotoSansKR-Bold"), "size": ss_size, "color": sc_c,
            "outline_color": soc, "outline_width": sow, "position": sp, "bg_opacity": sbo
        }

        st.write("Preview:")
        st.markdown(f'<div style="background:rgba(0,0,0,{sbo});padding:10px 20px;display:inline-block;border-radius:5px;">'
                    f'<span style="font-size:{ss_size}px;color:{sc_c};text-shadow:-{sow}px -{sow}px 0 {soc},{sow}px -{sow}px 0 {soc},'
                    f'-{sow}px {sow}px 0 {soc},{sow}px {sow}px 0 {soc};">'
                    f'쇼츠 자막 미리보기</span></div>', unsafe_allow_html=True)

    st.divider()
    if st.button("Export JSON", key="btn_export_sub"):
        export = {"longform": st.session_state["subtitle_style_long"], "shorts": st.session_state["subtitle_style_shorts"]}
        j = json.dumps(export, ensure_ascii=False, indent=2)
        st.code(j, language="json")
        st.download_button("Download JSON", j, "subtitle_styles.json", mime="application/json", key="dl_sub_json")

# ═══ 탭8: 최종 합치기 ═══
with tab8:
    st.header("최종 합치기")

    st.subheader("완료 체크리스트")
    checks = {
        "주제 선택": bool(st.session_state.get("selected_topic")),
        "롱폼 대본": bool(st.session_state.get("full_script")),
        "쇼츠 대본": bool(st.session_state.get("shorts_scripts")),
        "레퍼런스 이미지": bool(st.session_state.get("reference_image_path")),
        "롱폼 이미지": bool(st.session_state.get("gen_images_long")),
        "쇼츠 이미지": bool(st.session_state.get("gen_images_shorts")),
        "TTS 롱폼": bool(st.session_state.get("tts_audio_long")),
        "TTS 쇼츠": bool(st.session_state.get("tts_audio_shorts")),
        "자막 스타일": True,
    }
    for item, done in checks.items():
        st.write(f"[{'O' if done else 'X'}] {item} - {'완료' if done else '미완료'}")

    st.divider()
    st.subheader("FFmpeg 합성 명령어")
    stl = st.session_state["subtitle_style_long"]
    sts = st.session_state["subtitle_style_shorts"]

    st.write("롱폼 영상 합성:")
    st.code(f"""ffmpeg -framerate 1/5 -i generated_images/long_%04d.png \\
  -i tts_output/longform_tts.mp3 \\
  -vf "subtitles=tts_output/longform.srt:force_style='FontName={stl['font']},FontSize={stl['size']},PrimaryColour=&H00{stl['color'][1:]}&,OutlineColour=&H00{stl['outline_color'][1:]}&,Outline={stl['outline_width']},Alignment=2'" \\
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest output/longform_final.mp4""", language="bash")

    st.write("쇼츠 영상 합성:")
    for i in range(1,4):
        st.code(f"""ffmpeg -framerate 1/4 -i generated_images/shorts_{i}_%03d.png \\
  -i tts_output/shorts_{i}_tts.mp3 \\
  -vf "scale=720:1280,subtitles=tts_output/shorts_{i}.srt:force_style='FontName={sts['font']},FontSize={sts['size']},PrimaryColour=&H00{sts['color'][1:]}&,OutlineColour=&H00{sts['outline_color'][1:]}&,Outline={sts['outline_width']},Alignment=5'" \\
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest output/shorts_{i}_final.mp4""", language="bash")

    st.divider()
    if st.button("전체 프로젝트 JSON 내보내기", key="btn_export_all"):
        export = {
            "주제": st.session_state.get("selected_topic",""),
            "카테고리": st.session_state.get("selected_category",""),
            "롱폼": {"제목":st.session_state.get("long_title",""),"태그":st.session_state.get("long_tags",""),
                    "설명":st.session_state.get("long_desc",""),"대본":st.session_state.get("full_script",""),
                    "문장수":len(st.session_state.get("long_sentences",[])),
                    "이미지수":len(st.session_state.get("gen_images_long",{}))},
            "쇼츠": [{"편":sd.get("num"),"제목":sd.get("title"),"대본":sd.get("script"),"장면수":len(sd.get("scenes",[]))}
                    for sd in st.session_state.get("shorts_scripts",[])],
            "자막":{"롱폼":st.session_state.get("subtitle_style_long",{}),"쇼츠":st.session_state.get("subtitle_style_shorts",{})},
            "고정댓글":{str(k):v for k,v in st.session_state.get("pinned_comments",{}).items()},
            "롱폼링크": st.session_state.get("longform_link","")
        }
        j = json.dumps(export, ensure_ascii=False, indent=2)
        st.code(j, language="json")
        st.download_button("프로젝트 JSON 다운로드", j,
                           f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json", key="dl_project")
