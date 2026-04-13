import streamlit as st
import requests
import json
import os
import re
import time
import base64
from datetime import datetime

# ───────────────────────────────────────────
# 페이지 설정
# ───────────────────────────────────────────
st.set_page_config(page_title="시니어 콘텐츠 공장 v4.0", layout="wide")

# ───────────────────────────────────────────
# API 키 로드
# ───────────────────────────────────────────
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

# ───────────────────────────────────────────
# 음성 옵션
# ───────────────────────────────────────────
VOICE_OPTIONS = {
    "한국어 여성 1": {"lang": "ko", "voice_id": "ko-KR-SunHiNeural"},
    "한국어 여성 2": {"lang": "ko", "voice_id": "ko-KR-JiMinNeural"},
    "한국어 남성 1": {"lang": "ko", "voice_id": "ko-KR-InJoonNeural"},
    "한국어 남성 2": {"lang": "ko", "voice_id": "ko-KR-HyunsuNeural"},
    "일본어 여성": {"lang": "ja", "voice_id": "ja-JP-NanamiNeural"},
    "일본어 남성": {"lang": "ja", "voice_id": "ja-JP-KeitaNeural"},
}

# ───────────────────────────────────────────
# 글꼴 매핑
# ───────────────────────────────────────────
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

# ───────────────────────────────────────────
# 자막 스타일 기본값
# ───────────────────────────────────────────
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

# ───────────────────────────────────────────
# 세션 스테이트 초기화
# ───────────────────────────────────────────
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
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ───────────────────────────────────────────
# 유틸 함수
# ───────────────────────────────────────────
def clean_special(text):
    if not text:
        return ""
    text = re.sub(r'[*#_~`>|]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def safe_generate(prompt, system_prompt="", max_tokens=4096):
    """Gemini API를 사용한 텍스트 생성"""
    if not GEMINI_API_KEY:
        return "오류: GEMINI_API_KEY가 설정되지 않았습니다."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
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
    
    try:
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            return f"오류: Gemini API 응답 {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return "오류: Gemini API 응답에 결과가 없습니다."
        content = candidates[0].get("content", {})
        parts_out = content.get("parts", [])
        if not parts_out:
            return "오류: Gemini API 응답 파츠가 비어있습니다."
        return parts_out[0].get("text", "")
    except requests.exceptions.Timeout:
        return "오류: Gemini API 시간 초과"
    except requests.exceptions.ConnectionError:
        return "오류: Gemini API 연결 실패"
    except Exception as e:
        return f"오류: {str(e)}"

def generate_srt(lines, durations=None):
    """SRT 자막 파일 생성"""
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

# ───────────────────────────────────────────
# 사이드바
# ───────────────────────────────────────────
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

# ───────────────────────────────────────────
# 메인 타이틀
# ───────────────────────────────────────────
st.title("시니어 콘텐츠 공장 v4.0")
st.caption("Gemini 주제추천 → Skywork 대본/이미지(직접) → 영상변환 → TTS → 자막 → 합치기")

# ───────────────────────────────────────────
# 탭 구성
# ───────────────────────────────────────────
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
# 탭1: 주제 추천 (Gemini API)
# ═══════════════════════════════════════════
with tab1:
    st.header("주제 추천")
    st.info("카테고리를 선택하고 버튼을 누르면 Gemini가 쇼츠/롱폼에 적합한 주제 5개를 추천합니다.")
    
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
            st.error("Gemini API 키가 설정되지 않았습니다. Streamlit Secrets에 GEMINI_API_KEY를 추가해주세요.")
        else:
            with st.spinner("Gemini에서 주제를 추천받고 있습니다..."):
                content_label = st.session_state.get("content_type", "쇼츠")
                prompt = f"""당신은 유튜브 {content_label} 콘텐츠 기획 전문가입니다.

카테고리: {selected_cat}

이 카테고리에서 유튜브 {content_label}로 만들면 조회수가 높을 만한 주제 5개를 추천해주세요.

규칙:
- 각 주제는 20자 이내로 짧고 임팩트 있게
- 특수기호 사용 금지
- 번호는 1. 2. 3. 4. 5. 형식으로
- 시청자가 클릭하고 싶은 자극적이고 궁금증을 유발하는 제목
- 각 주제 아래에 한 줄로 간단한 설명 추가
- 현재 트렌드와 관련된 주제 우선

예시 형식:
1. 주제 제목
설명: 간단한 한 줄 설명

5개만 출력하세요."""

                result = safe_generate(prompt)
                
                if result.startswith("오류:"):
                    st.error(result)
                else:
                    st.session_state["topic_recommendations"] = result
                    st.success("주제 추천 완료!")
    
    if st.session_state.get("topic_recommendations"):
        st.subheader("추천 주제 목록")
        rec_text = st.session_state["topic_recommendations"]
        st.markdown(f"```\n{clean_special(rec_text)}\n```")
        
        topic_input = st.text_input(
            "위 추천 중 사용할 주제를 입력하거나, 직접 주제를 작성하세요",
            value=st.session_state.get("selected_topic", ""),
            key="topic_input"
        )
        if st.button("이 주제로 결정", key="btn_set_topic"):
            if topic_input.strip():
                st.session_state["selected_topic"] = topic_input.strip()
                st.success(f"주제가 결정되었습니다: {topic_input.strip()}")
            else:
                st.warning("주제를 입력해주세요.")
    
    if st.session_state.get("selected_topic"):
        st.divider()
        st.subheader("선택된 주제")
        st.info(f"현재 주제: **{st.session_state['selected_topic']}**")
        st.caption("이 주제로 Skywork에서 대본과 이미지를 생성한 후, 탭2와 탭3에서 입력해주세요.")

# ═══════════════════════════════════════════
# 탭2: 대본 입력 (Skywork에서 가져온 대본 붙여넣기)
# ═══════════════════════════════════════════
with tab2:
    st.header("대본 입력")
    
    if st.session_state.get("selected_topic"):
        st.info(f"현재 주제: {st.session_state['selected_topic']}")
    else:
        st.warning("탭1에서 먼저 주제를 선택해주세요.")
    
    st.caption("Skywork에서 생성한 대본을 아래에 붙여넣으세요. 문장 단위로 구분됩니다.")
    
    script_input = st.text_area(
        "대본 전체 붙여넣기",
        value=st.session_state.get("script_text", ""),
        height=400,
        placeholder="Skywork에서 생성한 순수 대본을 여기에 붙여넣으세요.\n\n마침표(.)로 끝나는 각 문장이 하나의 장면이 됩니다.",
        key="script_textarea"
    )
    
    if st.button("대본 저장 및 분석", key="btn_save_script", use_container_width=True):
        if script_input.strip():
            st.session_state["script_text"] = script_input.strip()
            # 마침표 기준으로 문장 분리
            raw_lines = re.split(r'(?<=[.?])\s*', script_input.strip())
            lines = [l.strip() for l in raw_lines if l.strip() and len(l.strip()) > 2]
            st.session_state["script_lines"] = lines
            st.success(f"대본이 저장되었습니다. 총 {len(lines)}개 문장(장면)으로 분리됨.")
        else:
            st.warning("대본을 입력해주세요.")
    
    if st.session_state.get("script_lines"):
        st.divider()
        st.subheader(f"분리된 문장 ({len(st.session_state['script_lines'])}개)")
        for i, line in enumerate(st.session_state["script_lines"]):
            st.text(f"장면 {i+1:03d}: {line}")
        
        st.divider()
        st.subheader("문장 수동 편집")
        st.caption("필요 시 개별 문장을 수정할 수 있습니다.")
        
        edited_lines = []
        for i, line in enumerate(st.session_state["script_lines"]):
            edited = st.text_input(
                f"장면 {i+1:03d}",
                value=line,
                key=f"edit_line_{i}"
            )
            edited_lines.append(edited)
        
        if st.button("수정사항 저장", key="btn_save_edits"):
            st.session_state["script_lines"] = [l.strip() for l in edited_lines if l.strip()]
            st.success("수정사항이 저장되었습니다.")
            st.rerun()

# ═══════════════════════════════════════════
# 탭3: 이미지 업로드 (Skywork에서 가져온 이미지)
# ═══════════════════════════════════════════
with tab3:
    st.header("이미지 업로드")
    
    num_lines = len(st.session_state.get("script_lines", []))
    if num_lines == 0:
        st.warning("탭2에서 먼저 대본을 입력하고 저장해주세요. 문장 수에 맞춰 이미지를 업로드합니다.")
    else:
        st.info(f"대본 문장 수: {num_lines}개 → 이미지 {num_lines}장이 필요합니다.")
        st.caption("Skywork에서 생성한 이미지를 장면 번호 순서대로 업로드하세요.")
        
        # 일괄 업로드
        st.subheader("일괄 업로드")
        st.caption(f"이미지 파일 {num_lines}개를 한꺼번에 선택하세요. 파일명 순서대로 장면에 배정됩니다.")
        
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
                    uploaded.append({
                        "name": f.name,
                        "bytes": f.getvalue(),
                        "type": f.type,
                    })
                st.session_state["uploaded_images"] = uploaded
                st.success(f"{len(uploaded)}개 이미지가 저장되었습니다.")
                
                if len(uploaded) < num_lines:
                    st.warning(f"이미지 {len(uploaded)}개 < 문장 {num_lines}개. 부족한 장면은 마지막 이미지가 반복 사용됩니다.")
                elif len(uploaded) > num_lines:
                    st.warning(f"이미지 {len(uploaded)}개 > 문장 {num_lines}개. 초과 이미지는 무시됩니다.")
        
        # 저장된 이미지 미리보기
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
                                line_preview = st.session_state["script_lines"][idx]
                                if len(line_preview) > 30:
                                    line_preview = line_preview[:30] + "..."
                                st.caption(line_preview)

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
        
        st.subheader("영상 변환 설정")
        
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            scene_duration = st.slider("장면당 길이(초)", min_value=3, max_value=10, value=5, key="scene_dur")
        with col_v2:
            motion_type = st.selectbox("모션 유형", ["줌인", "줌아웃", "패닝", "정지"], key="motion_type")
        
        if not KIE_API_KEY:
            st.warning("KIE API 키가 설정되지 않았습니다. 영상 변환 기능을 사용하려면 KIE_API_KEY를 Secrets에 추가하세요.")
            st.divider()
            st.subheader("대안: 수동 영상 변환")
            st.caption("API 없이도 이미지와 대본을 다운로드하여 외부 툴에서 영상을 만들 수 있습니다.")
            
            # 이미지+대본 매칭 정보 다운로드
            match_data = []
            for i, line in enumerate(lines):
                img_idx = min(i, len(images) - 1)
                match_data.append({
                    "scene": i + 1,
                    "script": line,
                    "image_file": images[img_idx]["name"],
                    "duration_sec": scene_duration,
                })
            
            match_json = json.dumps(match_data, ensure_ascii=False, indent=2)
            st.download_button(
                "장면 매칭 정보 다운로드 (JSON)",
                data=match_json,
                file_name="scene_matching.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            if st.button("영상 변환 시작", key="btn_convert_video", use_container_width=True):
                st.session_state["video_urls"] = []
                progress = st.progress(0)
                status = st.empty()
                
                for i, line in enumerate(lines):
                    img_idx = min(i, len(images) - 1)
                    img_data = images[img_idx]["bytes"]
                    img_b64 = base64.b64encode(img_data).decode("utf-8")
                    
                    status.text(f"장면 {i+1}/{len(lines)} 변환 중...")
                    
                    # KIE API 영상 변환 요청
                    try:
                        headers = {
                            "Authorization": f"Bearer {KIE_API_KEY}",
                            "Content-Type": "application/json",
                        }
                        payload = {
                            "image": img_b64,
                            "duration": scene_duration,
                            "motion": motion_type,
                        }
                        resp = requests.post(
                            "https://api.kie.ai/v1/video/generate",
                            headers=headers,
                            json=payload,
                            timeout=120,
                        )
                        if resp.status_code == 200:
                            result = resp.json()
                            video_url = result.get("video_url", "")
                            st.session_state["video_urls"].append(video_url)
                        else:
                            st.session_state["video_urls"].append(f"오류: {resp.status_code}")
                    except Exception as e:
                        st.session_state["video_urls"].append(f"오류: {str(e)}")
                    
                    progress.progress((i + 1) / len(lines))
                
                status.text("영상 변환 완료!")
                st.success(f"{len(st.session_state['video_urls'])}개 장면 변환 완료")
        
        if st.session_state.get("video_urls"):
            st.divider()
            st.subheader("변환된 영상")
            for i, url in enumerate(st.session_state["video_urls"]):
                if url.startswith("오류"):
                    st.error(f"장면 {i+1}: {url}")
                else:
                    st.video(url)

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
        
        selected_voice = st.selectbox(
            "음성 선택",
            list(VOICE_OPTIONS.keys()),
            key="voice_select"
        )
        
        voice_info = VOICE_OPTIONS[selected_voice]
        
        # 미리듣기
        st.subheader("미리듣기")
        preview_line_idx = st.selectbox(
            "미리들을 문장 선택",
            [f"장면 {i+1}: {line[:40]}..." if len(line) > 40 else f"장면 {i+1}: {line}" for i, line in enumerate(lines)],
            key="preview_select"
        )
        preview_idx = int(preview_line_idx.split(":")[0].replace("장면 ", "").strip()) - 1
        
        if st.button("미리듣기", key="btn_preview_tts"):
            if not INWORLD_API_KEY:
                st.warning("Inworld API 키가 없습니다. INWORLD_API_KEY를 Secrets에 추가하세요.")
            else:
                with st.spinner("음성 생성 중..."):
                    try:
                        headers = {
                            "Authorization": f"Bearer {INWORLD_API_KEY}",
                            "Content-Type": "application/json",
                        }
                        payload = {
                            "text": lines[preview_idx],
                            "voice_id": voice_info["voice_id"],
                            "language": voice_info["lang"],
                        }
                        resp = requests.post(
                            "https://api.inworld.ai/v1/tts/synthesize",
                            headers=headers,
                            json=payload,
                            timeout=30,
                        )
                        if resp.status_code == 200:
                            st.audio(resp.content, format="audio/mp3")
                        else:
                            st.error(f"TTS 오류: {resp.status_code} - {resp.text[:200]}")
                    except Exception as e:
                        st.error(f"TTS 오류: {str(e)}")
        
        st.divider()
        
        # 전체 생성
        if st.button("전체 음성 생성", key="btn_full_tts", use_container_width=True):
            if not INWORLD_API_KEY:
                st.warning("Inworld API 키가 없습니다.")
            else:
                st.session_state["tts_audio_bytes"] = []
                progress = st.progress(0)
                status = st.empty()
                
                for i, line in enumerate(lines):
                    status.text(f"장면 {i+1}/{len(lines)} 음성 생성 중...")
                    try:
                        headers = {
                            "Authorization": f"Bearer {INWORLD_API_KEY}",
                            "Content-Type": "application/json",
                        }
                        payload = {
                            "text": line,
                            "voice_id": voice_info["voice_id"],
                            "language": voice_info["lang"],
                        }
                        resp = requests.post(
                            "https://api.inworld.ai/v1/tts/synthesize",
                            headers=headers,
                            json=payload,
                            timeout=30,
                        )
                        if resp.status_code == 200:
                            st.session_state["tts_audio_bytes"].append(resp.content)
                        else:
                            st.session_state["tts_audio_bytes"].append(None)
                            st.warning(f"장면 {i+1} TTS 실패: {resp.status_code}")
                    except Exception as e:
                        st.session_state["tts_audio_bytes"].append(None)
                        st.warning(f"장면 {i+1} TTS 오류: {str(e)}")
                    
                    progress.progress((i + 1) / len(lines))
                
                status.text("전체 음성 생성 완료!")
                success_count = sum(1 for a in st.session_state["tts_audio_bytes"] if a is not None)
                st.success(f"음성 생성 완료: {success_count}/{len(lines)}")
        
        if st.session_state.get("tts_audio_bytes"):
            st.divider()
            st.subheader("생성된 음성")
            for i, audio in enumerate(st.session_state["tts_audio_bytes"]):
                if audio:
                    st.caption(f"장면 {i+1}: {lines[i][:50]}")
                    st.audio(audio, format="audio/mp3")
                    st.download_button(
                        f"장면 {i+1} 다운로드",
                        data=audio,
                        file_name=f"tts_scene_{i+1:03d}.mp3",
                        mime="audio/mp3",
                        key=f"dl_tts_{i}"
                    )

# ═══════════════════════════════════════════
# 탭6: 자막 스타일
# ═══════════════════════════════════════════
with tab6:
    st.header("자막 스타일 설정")
    
    sub_tab_long, sub_tab_shorts = st.tabs(["롱폼 자막", "쇼츠 자막"])
    
    # ─── 롱폼 자막 ───
    with sub_tab_long:
        st.subheader("롱폼 자막 스타일")
        
        col_set, col_prev = st.columns([1, 1])
        
        with col_set:
            sl = st.session_state["subtitle_style_long"]
            
            sl["font"] = st.selectbox("글꼴", FONT_LIST, 
                index=FONT_LIST.index(sl["font"]) if sl["font"] in FONT_LIST else 0,
                key="long_font")
            sl["size"] = st.slider("크기", 16, 60, sl["size"], key="long_size")
            sl["color"] = st.color_picker("글자 색상", sl["color"], key="long_color")
            sl["outline_color"] = st.color_picker("외곽선 색상", sl["outline_color"], key="long_outline_color")
            sl["outline_width"] = st.slider("외곽선 두께", 0, 5, sl["outline_width"], key="long_outline_w")
            sl["position"] = st.selectbox("위치", ["상단", "중앙", "하단"],
                index=["상단", "중앙", "하단"].index(sl["position"]),
                key="long_pos")
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
            preview_html = f"""
            <div style="position:relative; width:320px; height:180px; background:#222; border-radius:8px; overflow:hidden;">
                <div style="position:absolute; {pos_css}; left:50%; transform:translateX(-50%);
                    font-family:'{FONT_MAP.get(sl['font'], 'sans-serif')}', sans-serif;
                    font-size:{sl['size']//2}px; color:{sl['color']};
                    text-shadow: {sl['outline_width']}px {sl['outline_width']}px 0 {sl['outline_color']},
                    -{sl['outline_width']}px -{sl['outline_width']}px 0 {sl['outline_color']};
                    background:{bg_rgba}; padding:4px 12px; border-radius:4px;
                    white-space:nowrap;">
                    롱폼 자막 미리보기
                </div>
            </div>
            """
            st.markdown(preview_html, unsafe_allow_html=True)
    
    # ─── 쇼츠 자막 ───
    with sub_tab_shorts:
        st.subheader("쇼츠 자막 스타일")
        
        col_set2, col_prev2 = st.columns([1, 1])
        
        with col_set2:
            ss = st.session_state["subtitle_style_shorts"]
            
            ss["font"] = st.selectbox("글꼴", FONT_LIST,
                index=FONT_LIST.index(ss["font"]) if ss["font"] in FONT_LIST else 0,
                key="shorts_font")
            ss["size"] = st.slider("크기", 16, 72, ss["size"], key="shorts_size")
            ss["color"] = st.color_picker("글자 색상", ss["color"], key="shorts_color")
            ss["outline_color"] = st.color_picker("외곽선 색상", ss["outline_color"], key="shorts_outline_color")
            ss["outline_width"] = st.slider("외곽선 두께", 0, 6, ss["outline_width"], key="shorts_outline_w")
            ss["position"] = st.selectbox("위치", ["상단", "중앙", "하단"],
                index=["상단", "중앙", "하단"].index(ss["position"]),
                key="shorts_pos")
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
            st.caption("미리보기 (9:16 비율)")
            pos_css2 = pos_map.get(ss["position"], "bottom:15%")
            bg_rgba2 = f"rgba(0,0,0,{ss['bg_opacity']})"
            preview_html2 = f"""
            <div style="position:relative; width:180px; height:320px; background:#111; border-radius:8px; overflow:hidden;">
                <div style="position:absolute; {pos_css2}; left:50%; transform:translateX(-50%);
                    font-family:'{FONT_MAP.get(ss['font'], 'sans-serif')}', sans-serif;
                    font-size:{ss['size']//2}px; color:{ss['color']};
                    text-shadow: {ss['outline_width']}px {ss['outline_width']}px 0 {ss['outline_color']},
                    -{ss['outline_width']}px -{ss['outline_width']}px 0 {ss['outline_color']};
                    background:{bg_rgba2}; padding:4px 12px; border-radius:4px;
                    white-space:nowrap;">
                    쇼츠 자막
                </div>
            </div>
            """
            st.markdown(preview_html2, unsafe_allow_html=True)
    
    # JSON 내보내기
    st.divider()
    if st.button("자막 스타일 JSON 내보내기", key="btn_export_sub", use_container_width=True):
        export_data = {
            "long_form": st.session_state["subtitle_style_long"],
            "shorts": st.session_state["subtitle_style_shorts"],
            "long_form_font_file": FONT_MAP.get(st.session_state["subtitle_style_long"]["font"], ""),
            "shorts_font_file": FONT_MAP.get(st.session_state["subtitle_style_shorts"]["font"], ""),
        }
        export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            "다운로드",
            data=export_json,
            file_name="subtitle_styles.json",
            mime="application/json",
            use_container_width=True,
        )
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
    
    # 진행 상황 요약
    st.subheader("진행 상황 요약")
    
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
    
    # SRT 자막 다운로드
    st.subheader("자막 파일 생성")
    if lines:
        scene_dur = st.session_state.get("scene_dur", 5)
        durations = [scene_dur] * len(lines)
        srt_content = generate_srt(lines, durations)
        
        st.download_button(
            "SRT 자막 파일 다운로드",
            data=srt_content,
            file_name="subtitles.srt",
            mime="text/plain",
            use_container_width=True,
        )
        
        with st.expander("SRT 미리보기"):
            st.code(srt_content)
    
    st.divider()
    
    # 전체 프로젝트 JSON 내보내기
    st.subheader("프로젝트 전체 내보내기")
    st.caption("대본, 자막 스타일, 장면 매칭 정보를 하나의 JSON으로 내보냅니다. (이미지/음성 바이너리는 제외)")
    
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
            "subtitle_style_long_font_file": FONT_MAP.get(
                st.session_state.get("subtitle_style_long", {}).get("font", ""), ""
            ),
            "subtitle_style_shorts_font_file": FONT_MAP.get(
                st.session_state.get("subtitle_style_shorts", {}).get("font", ""), ""
            ),
            "scene_duration_sec": st.session_state.get("scene_dur", 5),
            "video_urls": videos,
            "tts_generated": len([a for a in audios if a]) if audios else 0,
        }
        
        project_json = json.dumps(project, ensure_ascii=False, indent=2)
        
        st.download_button(
            "프로젝트 JSON 다운로드",
            data=project_json,
            file_name=f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
        
        with st.expander("프로젝트 JSON 미리보기"):
            st.code(project_json, language="json")
