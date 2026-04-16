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
    "line_spacing": 1.4,
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
    "line_spacing": 1.4,
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


# ─────────────────────────── 사이드바 ───────────────────────────
with st.sidebar:
    st.title("시니어 콘텐츠 공장 v5.0")
    st.divider()

    st.subheader("API 상태")
    if GEMINI_API_KEY:
        st.success("Gemini API: 연결됨")
    else:
        st.error("Gemini API: 키 없음")
    if INWORLD_API_KEY:
        st.success("Inworld TTS API: 연결됨")
    else:
        st.error("Inworld TTS API: 키 없음")

    st.divider()
    st.subheader("콘텐츠 설정")
    content_type = st.radio("콘텐츠 유형", ["쇼츠", "롱폼"], key="content_type_radio")
    st.session_state["content_type"] = content_type

    st.divider()
    st.subheader("레퍼런스 이미지")
    ref_img = st.file_uploader("주인공 레퍼런스 이미지", type=["png", "jpg", "jpeg"], key="ref_img_upload")
    if ref_img:
        st.session_state["reference_image"] = ref_img.getvalue()
        st.image(ref_img, width=150)

    st.divider()
    st.caption("문의: 시니어 콘텐츠 공장")


# ─────────────────────────── 유틸 함수 ───────────────────────────
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


def generate_srt_split(sub_lines, durations):
    srt = ""
    seq = 1
    current_time = 0.0
    sub_idx = 0
    for i in range(len(durations)):
        dur = durations[i]
        tts_start = current_time
        tts_end = current_time + dur
        count = 0
        j = sub_idx
        while j < len(sub_lines):
            if j == sub_idx:
                count += 1
                j += 1
            elif j < len(sub_lines) and count < 10:
                count += 1
                j += 1
            else:
                break
            if count >= 10 or j >= len(sub_lines):
                break
        if sub_idx + count > len(sub_lines):
            count = len(sub_lines) - sub_idx
        if count <= 0:
            current_time = tts_end
            continue
        if count == 1:
            s_h = int(tts_start // 3600)
            s_m = int((tts_start % 3600) // 60)
            s_s = int(tts_start % 60)
            s_ms = int((tts_start % 1) * 1000)
            e_h = int(tts_end // 3600)
            e_m = int((tts_end % 3600) // 60)
            e_s = int(tts_end % 60)
            e_ms = int((tts_end % 1) * 1000)
            srt += f"{seq}\n"
            srt += f"{s_h:02d}:{s_m:02d}:{s_s:02d},{s_ms:03d} --> "
            srt += f"{e_h:02d}:{e_m:02d}:{e_s:02d},{e_ms:03d}\n"
            srt += f"{sub_lines[sub_idx].strip()}\n\n"
            seq += 1
            sub_idx += 1
        else:
            chunk_dur = dur / count
            for c in range(count):
                c_start = tts_start + c * chunk_dur
                c_end = tts_start + (c + 1) * chunk_dur
                s_h = int(c_start // 3600)
                s_m = int((c_start % 3600) // 60)
                s_s = int(c_start % 60)
                s_ms = int((c_start % 1) * 1000)
                e_h = int(c_end // 3600)
                e_m = int((c_end % 3600) // 60)
                e_s = int(c_end % 60)
                e_ms = int((c_end % 1) * 1000)
                srt += f"{seq}\n"
                srt += f"{s_h:02d}:{s_m:02d}:{s_s:02d},{s_ms:03d} --> "
                srt += f"{e_h:02d}:{e_m:02d}:{e_s:02d},{e_ms:03d}\n"
                srt += f"{sub_lines[sub_idx + c].strip()}\n\n"
                seq += 1
            sub_idx += count
        current_time = tts_end
    while sub_idx < len(sub_lines):
        s_h = int(current_time // 3600)
        s_m = int((current_time % 3600) // 60)
        s_s = int(current_time % 60)
        s_ms = int((current_time % 1) * 1000)
        e_time = current_time + 2.0
        e_h = int(e_time // 3600)
        e_m = int((e_time % 3600) // 60)
        e_s = int(e_time % 60)
        e_ms = int((e_time % 1) * 1000)
        srt += f"{seq}\n"
        srt += f"{s_h:02d}:{s_m:02d}:{s_s:02d},{s_ms:03d} --> "
        srt += f"{e_h:02d}:{e_m:02d}:{e_s:02d},{e_ms:03d}\n"
        srt += f"{sub_lines[sub_idx].strip()}\n\n"
        seq += 1
        sub_idx += 1
        current_time = e_time
    return srt


def merge_final_video(videos, audio_data, srt_text, sub_style):
    try:
        if not videos:
            return None, "영상 클립이 없습니다."
        if not audio_data:
            return None, "TTS 음성이 없습니다."

        tmp_dir = tempfile.mkdtemp()

        clip_paths = []
        for i, v in enumerate(videos):
            cp = os.path.join(tmp_dir, f"clip_{i:03d}.mp4")
            with open(cp, "wb") as f:
                if isinstance(v, dict):
                    f.write(v["bytes"])
                else:
                    f.write(v)
            clip_paths.append(cp)

        audio_paths = []
        audio_index_map = []
        for i, a in enumerate(audio_data):
            if a is None:
                continue
            ap = os.path.join(tmp_dir, f"audio_{i:03d}.mp3")
            with open(ap, "wb") as f:
                f.write(a)
            audio_paths.append(ap)
            audio_index_map.append(i)

        if not audio_paths:
            return None, "유효한 TTS 음성이 없습니다."

        segment_paths = []
        for j, ap in enumerate(audio_paths):
            clip_idx = audio_index_map[j]
            if clip_idx >= len(clip_paths):
                clip_idx = len(clip_paths) - 1

            dur_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                ap
            ]
            dur_result = subprocess.run(dur_cmd, capture_output=True, text=True)
            try:
                audio_dur = float(dur_result.stdout.strip())
            except Exception:
                audio_dur = 3.0

            seg_path = os.path.join(tmp_dir, f"seg_{j:03d}.mp4")
            seg_cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", clip_paths[clip_idx],
                "-i", ap,
                "-t", str(audio_dur),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                seg_path
            ]
            subprocess.run(seg_cmd, capture_output=True, text=True)
            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                segment_paths.append(seg_path)

        if not segment_paths:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None, "세그먼트 생성에 실패했습니다."

        concat_list = os.path.join(tmp_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for sp in segment_paths:
                f.write(f"file '{sp}'\n")

        merged_nosub = os.path.join(tmp_dir, "merged_nosub.mp4")
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            merged_nosub
        ]
        subprocess.run(concat_cmd, capture_output=True, text=True)

        if not os.path.exists(merged_nosub) or os.path.getsize(merged_nosub) == 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None, "영상 병합에 실패했습니다."

        final_path = os.path.join(tmp_dir, "final_output.mp4")

        if srt_text and srt_text.strip():
            srt_path = os.path.join(tmp_dir, "subs.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_text)

            font_candidates = [
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            font_path = ""
            for fp in font_candidates:
                if os.path.exists(fp):
                    font_path = fp
                    break

            font_size = sub_style.get("size", 20) if sub_style else 20
            outline_w = sub_style.get("outline_width", 2) if sub_style else 2
            bg_opacity_float = sub_style.get("bg_opacity", 0.5) if sub_style else 0.5
            bg_hex = format(int(bg_opacity_float * 255), '02X')
            line_sp = sub_style.get("line_spacing", 1.4) if sub_style else 1.4
            spacing_val = int((line_sp - 1.0) * font_size)

            hex_color = sub_style.get("color", "#FFFFFF") if sub_style else "#FFFFFF"
            hex_color = hex_color.lstrip("#")
            if len(hex_color) == 6:
                r_c = hex_color[0:2]
                g_c = hex_color[2:4]
                b_c = hex_color[4:6]
                ass_color = "&H00" + b_c + g_c + r_c
            else:
                ass_color = "&H00FFFFFF"

            srt_escaped = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

            if font_path:
                font_dir = os.path.dirname(font_path)
                font_dir_escaped = font_dir.replace("\\", "\\\\").replace(":", "\\:")
                subtitles_filter = (
                    "subtitles='" + srt_escaped + "'"
                    + ":force_style='"
                    + "FontName=NanumGothic"
                    + ",FontSize=" + str(font_size)
                    + ",PrimaryColour=" + ass_color
                    + ",OutlineColour=&H" + bg_hex + "000000"
                    + ",Outline=" + str(outline_w)
                    + ",BorderStyle=3"
                    + ",Alignment=2"
                    + ",MarginV=30"
                    + ",Spacing=" + str(spacing_val)
                    + "'"
                    + ":fontsdir='" + font_dir_escaped + "'"
                )
            else:
                subtitles_filter = (
                    "subtitles='" + srt_escaped + "'"
                    + ":force_style='"
                    + "FontSize=" + str(font_size)
                    + ",PrimaryColour=" + ass_color
                    + ",OutlineColour=&H" + bg_hex + "000000"
                    + ",Outline=" + str(outline_w)
                    + ",BorderStyle=3"
                    + ",Alignment=2"
                    + ",MarginV=30"
                    + ",Spacing=" + str(spacing_val)
                    + "'"
                )

            sub_cmd = [
                "ffmpeg", "-y",
                "-i", merged_nosub,
                "-vf", subtitles_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                final_path
            ]
            sub_result = subprocess.run(sub_cmd, capture_output=True, text=True)

            if not os.path.exists(final_path) or os.path.getsize(final_path) == 0:
                err_msg = sub_result.stderr[-500:] if sub_result.stderr else "알 수 없는 오류"
                st.warning("자막 번인 실패 - 자막 없이 생성합니다. 오류: " + err_msg)
                shutil.copy2(merged_nosub, final_path)
        else:
            shutil.copy2(merged_nosub, final_path)

        if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
            with open(final_path, "rb") as f:
                video_bytes = f.read()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return video_bytes, None
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None, "최종 파일 생성에 실패했습니다."

    except Exception as e:
        return None, f"오류 발생: {str(e)}"


# ─────────────────────────── 탭 생성 ───────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. 주제 추천",
    "2. 대본 입력",
    "3. 영상 업로드",
    "4. TTS 음성",
    "5. 자막 편집",
    "6. 최종 합치기"
])

# ─────────────────────────── 탭1: 주제 추천 ───────────────────────────
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
                topic_prompt = f"""당신은 유튜브 {content_label} 백만 조회수 전문 기획자이자 유튜브 광고 수익 최적화 전문가입니다.

아래는 "{selected_cat}" 카테고리의 최신 뉴스입니다:
{news_result}

유튜브 {content_label}로 만들면 조회수가 폭발할 주제 10개를 추천하세요.

반드시 아래 유튜브 광고주 친화적 콘텐츠 가이드라인을 모두 준수하는 제목과 주제만 추천하세요.

광고주 친화적 가이드라인 필수 준수사항:
1. 욕설이나 저속한 표현을 제목에 절대 사용하지 않는다.
2. 유혈이나 폭력을 자극적으로 묘사하는 제목을 만들지 않는다.
3. 성적인 내용이나 암시를 제목에 포함하지 않는다.
4. 시청자에게 혐오감이나 충격을 주는 표현을 사용하지 않는다.
5. 유해하거나 위험한 행위를 조장하는 제목을 만들지 않는다.
6. 특정 개인이나 집단을 증오하거나 비하하거나 차별하는 표현을 사용하지 않는다.
7. 불법 약물이나 마약 관련 내용을 다루거나 조장하지 않는다.
8. 총기의 판매나 악용을 묘사하지 않는다.
9. 아동 학대나 성적 학대나 자해나 자살 등 논란의 소지가 있는 민감한 주제를 자극적으로 다루지 않는다.
10. 자연재해나 테러 등 민감한 사건을 부당하게 이용하지 않는다.
11. 해킹이나 속임수 등 부정 행위를 미화하거나 조장하지 않는다.
12. 담배 관련 제품을 홍보하지 않는다.
13. 불필요한 도발이나 선동이나 비하를 하지 않는다.
14. 제목에 낚시성 표현이나 허위 정보를 넣지 않는다.

광고주 친화적이면서 조회수가 높은 제목 작성법:
- 교육적이고 정보 전달 중심의 프레임을 사용한다.
- 분석이나 해설이나 정리 같은 지적 호기심을 자극하는 키워드를 사용한다.
- 숫자나 구체적 데이터를 활용하여 신뢰감을 준다.
- 시청자의 실생활에 도움이 되는 실용적 정보를 담는다.
- 궁금증을 유발하되 과도한 자극이 아닌 지적 호기심에 기반한다.
- 몰락이나 위기를 다루더라도 원인 분석이나 교훈이나 대안 제시 관점으로 접근한다.
- 특정인을 비난하지 않고 구조적 문제를 분석하는 방식으로 접근한다.

반드시 아래 JSON 형식으로만 출력하세요. JSON 외에 다른 텍스트를 절대 포함하지 마세요:
[
  {{"번호": 1, "주제": "유튜브 제목 (20~30자)", "출처뉴스": "참고한 뉴스 제목", "떡상확률": 85, "이유": "한 줄 설명", "추천태그": "태그1, 태그2, 태그3", "난이도": "쉬움", "광고적합": "적합"}},
  ...
]
규칙:
- 주제는 20~30자 사이로 작성한다.
- 광고주 친화적 가이드라인을 완벽히 준수하는 제목만 추천한다.
- 떡상확률은 50~95 사이로 현실적으로 평가한다.
- 난이도는 쉬움 또는 보통 또는 어려움 중 하나를 선택한다.
- 광고적합 항목은 반드시 적합으로만 출력한다.
- 10개 주제는 모두 서로 다른 각도의 주제여야 한다.
- 떡상확률이 높은 순서로 정렬한다.
- 출력은 반드시 [ 로 시작하고 ] 로 끝나야 한다."""
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
        if cleaned_raw.startswith("json"):
            cleaned_raw = cleaned_raw[4:].strip()
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
                    pc = "#FF4444"
                    pe = "🔥"
                    bc = "#FF4444"
                elif prob >= 70:
                    pc = "#FF8800"
                    pe = "⚡"
                    bc = "#FF8800"
                else:
                    pc = "#44AA44"
                    pe = "💡"
                    bc = "#44AA44"
                dc = {"쉬움": "#44CC44", "보통": "#FFAA00", "어려움": "#FF4444"}.get(diff, "#FFAA00")
                card_html = '<div style="border:2px solid ' + bc + ';border-radius:12px;padding:16px;margin:10px 0;background:#1a1a2e;">'
                card_html = card_html + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
                card_html = card_html + '<span style="font-size:20px;font-weight:bold;color:#FFF;">' + pe + ' ' + str(num) + '. ' + str(title) + '</span>'
                card_html = card_html + '<span style="font-size:24px;font-weight:bold;color:' + pc + ';">' + str(prob) + '%</span>'
                card_html = card_html + '</div>'
                card_html = card_html + '<table style="width:100%;border-collapse:collapse;margin:8px 0;">'
                card_html = card_html + '<tr style="border-bottom:1px solid #333;">'
                card_html = card_html + '<td style="padding:6px 8px;color:#888;font-size:13px;width:80px;">출처뉴스</td>'
                card_html = card_html + '<td style="padding:6px 8px;color:#CCC;font-size:13px;">' + str(source) + '</td>'
                card_html = card_html + '</tr>'
                card_html = card_html + '<tr style="border-bottom:1px solid #333;">'
                card_html = card_html + '<td style="padding:6px 8px;color:#888;font-size:13px;">추천이유</td>'
                card_html = card_html + '<td style="padding:6px 8px;color:#CCC;font-size:13px;">' + str(reason) + '</td>'
                card_html = card_html + '</tr>'
                card_html = card_html + '<tr style="border-bottom:1px solid #333;">'
                card_html = card_html + '<td style="padding:6px 8px;color:#888;font-size:13px;">추천태그</td>'
                card_html = card_html + '<td style="padding:6px 8px;color:#CCC;font-size:13px;">' + str(tags) + '</td>'
                card_html = card_html + '</tr>'
                card_html = card_html + '</table>'
                card_html = card_html + '<div style="display:flex;gap:8px;margin-top:8px;">'
                card_html = card_html + '<span style="background:' + dc + '22;padding:4px 12px;border-radius:20px;font-size:12px;color:' + dc + ';">난이도: ' + str(diff) + '</span>'
                card_html = card_html + '<span style="background:#00AA0022;padding:4px 12px;border-radius:20px;font-size:12px;color:#00CC00;">광고적합</span>'
                card_html = card_html + '</div>'
                card_html = card_html + '</div>'
                st.markdown(card_html, unsafe_allow_html=True)

            st.divider()
            topic_options = [str(item.get("번호", "")) + ". " + str(item.get("주제", "")) + " (" + str(item.get("떡상확률", 0)) + "%)" for item in topics_parsed]
            selected_topic_idx = st.selectbox("제작할 주제를 선택하세요", topic_options, key="topic_select_dropdown")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("이 주제로 결정", key="btn_set_topic", use_container_width=True):
                    idx = int(selected_topic_idx.split(".")[0]) - 1
                    if 0 <= idx < len(topics_parsed):
                        chosen = topics_parsed[idx]
                        st.session_state["selected_topic"] = chosen.get("주제", "")
                        st.session_state["selected_topic_data"] = chosen
                        st.success("주제 결정: " + chosen.get("주제", ""))
            with col_btn2:
                custom_topic = st.text_input("또는 직접 주제 입력", key="custom_topic_input")
                if st.button("직접 입력 주제로 결정", key="btn_custom_topic"):
                    if custom_topic.strip():
                        st.session_state["selected_topic"] = custom_topic.strip()
                        st.session_state["selected_topic_data"] = {}
                        st.success("주제 결정: " + custom_topic.strip())
        else:
            st.markdown("```\n" + clean_special(raw) + "\n```")
            topic_input = st.text_input("사용할 주제를 입력하세요", key="topic_input_fallback")
            if st.button("이 주제로 결정", key="btn_set_topic_fallback"):
                if topic_input.strip():
                    st.session_state["selected_topic"] = topic_input.strip()
                    st.success("주제 결정: " + topic_input.strip())

    if st.session_state.get("selected_topic"):
        st.divider()
        sd = st.session_state.get("selected_topic_data", {})
        info_line = ""
        if sd:
            info_line = '<div style="font-size:14px;color:#AAA;">떡상확률: <span style="color:#FF4444;font-weight:bold;">' + str(sd.get("떡상확률", "")) + '%</span> | 난이도: ' + str(sd.get("난이도", "")) + ' | 태그: ' + str(sd.get("추천태그", "")) + '</div>'
        selected_box = '<div style="border:3px solid #4CAF50;border-radius:12px;padding:20px;background:#0a2e0a;text-align:center;">'
        selected_box = selected_box + '<div style="font-size:14px;color:#88CC88;">현재 선택된 주제</div>'
        selected_box = selected_box + '<div style="font-size:24px;font-weight:bold;color:#FFF;margin:10px 0;">' + st.session_state["selected_topic"] + '</div>'
        selected_box = selected_box + info_line
        selected_box = selected_box + '</div>'
        st.markdown(selected_box, unsafe_allow_html=True)

# ─────────────────────────── 탭2: 대본 입력 ───────────────────────────
with tab2:
    st.header("대본 입력")
    if st.session_state.get("selected_topic"):
        st.markdown(
            '<div style="border:2px solid #4CAF50; border-radius:8px; padding:12px; background:#0a2e0a; margin-bottom:16px;">'
            + '<span style="color:#88CC88;">현재 주제:</span>'
            + '<span style="color:#FFF; font-weight:bold; margin-left:8px;">' + st.session_state["selected_topic"] + '</span>'
            + '</div>', unsafe_allow_html=True)
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
            st.markdown(
                '<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">'
                + '<span style="color:#88CC88; font-weight:bold;">생성된 대본: ' + str(len(preview)) + '문장</span></div>',
                unsafe_allow_html=True)
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
        st.markdown(
            '<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">'
            + '<span style="color:#88CC88;">저장된 대본:</span>'
            + '<span style="color:#FFF; font-weight:bold; margin-left:8px;">' + str(len(lines)) + '개 문장</span></div>',
            unsafe_allow_html=True)
        with st.expander("전체 장면 보기"):
            for i, line in enumerate(lines):
                st.markdown(
                    '<div style="padding:4px 0; border-bottom:1px solid #333;">'
                    + '<span style="color:#888; font-size:12px;">' + f"{i+1:03d}" + '</span>'
                    + '<span style="color:#DDD; font-size:14px; margin-left:8px;">' + line + '</span></div>',
                    unsafe_allow_html=True)

# ─────────────────────────── 탭3: 영상 업로드 ───────────────────────────
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
            st.markdown(
                '<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">'
                + '<span style="color:#88CC88;">저장된 영상:</span>'
                + '<span style="color:#FFF; font-weight:bold; margin-left:8px;">' + str(len(videos)) + '개 / ' + f"{total_size:.1f}" + 'MB</span>'
                + '<span style="color:#AAA; margin-left:12px;">(필요: ' + str(num_lines) + '개)</span></div>',
                unsafe_allow_html=True)
            with st.expander("영상 목록"):
                for i, v in enumerate(videos):
                    sz = len(v["bytes"]) / 1024 / 1024
                    lt = st.session_state["script_lines"][i] if i < num_lines else ""
                    st.markdown(
                        '<div style="padding:4px 0; border-bottom:1px solid #333;">'
                        + '<span style="color:#888;">' + f"{i+1:03d}" + '</span>'
                        + '<span style="color:#FFF; margin-left:8px;">' + v["name"] + ' (' + f"{sz:.1f}" + 'MB)</span>'
                        + '<span style="color:#AAA; margin-left:8px; font-size:12px;">' + lt[:40] + '</span></div>',
                        unsafe_allow_html=True)

# ─────────────────────────── 탭4: TTS 음성 ───────────────────────────
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
            st.markdown(
                '<div style="background:#1a2e1a; border:2px solid #4CAF50; border-radius:8px; padding:12px;">'
                + '<span style="color:#88CC88;">총 음성:</span>'
                + '<span style="color:#FFF; font-weight:bold; margin-left:8px;">' + f"{td:.1f}" + '초 (' + f"{td/60:.1f}" + '분)</span></div>',
                unsafe_allow_html=True)
            with st.expander("개별 음성 확인"):
                for i, (a, d) in enumerate(zip(ad, dr)):
                    lt = lines[i] if i < len(lines) else ""
                    st.caption(f"{i+1:03d} ({d:.1f}초): {lt[:50]}")
                    if a:
                        st.audio(a, format="audio/mp3")

# ─────────────────────────── 탭5: 자막 편집 ───────────────────────────
with tab5:
    st.header("자막 편집")
    lines = st.session_state.get("script_lines", [])
    durations = st.session_state.get("tts_durations", [])
    if not lines:
        st.warning("탭2에서 먼저 대본을 저장해주세요.")
    elif not durations:
        st.warning("탭4에서 먼저 TTS 음성을 생성해주세요.")
    else:
        ct = st.session_state.get("content_type", "쇼츠")
        if ct == "쇼츠":
            sub_style = st.session_state.get("subtitle_style_shorts", dict(DEFAULT_SUB_SHORTS))
        else:
            sub_style = st.session_state.get("subtitle_style_long", dict(DEFAULT_SUB_LONG))

        if "line_spacing" not in sub_style:
            sub_style["line_spacing"] = 1.4

        if not st.session_state.get("edited_sub_lines") or len(st.session_state["edited_sub_lines"]) != len(lines):
            st.session_state["edited_sub_lines"] = list(lines)

        st.subheader("자막 스타일 설정")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            sel_font = st.selectbox("글꼴", FONT_LIST, index=FONT_LIST.index(sub_style.get("font", FONT_LIST[0])) if sub_style.get("font", FONT_LIST[0]) in FONT_LIST else 0, key="sub_font")
            sub_style["font"] = sel_font
        with col_s2:
            sub_style["size"] = st.slider("글자 크기", 12, 60, sub_style.get("size", 28), key="sub_size")
        with col_s3:
            sub_style["color"] = st.color_picker("글자 색상", sub_style.get("color", "#FFFFFF"), key="sub_color")
        with col_s4:
            sub_style["outline_width"] = st.slider("외곽선 두께", 0, 6, sub_style.get("outline_width", 2), key="sub_outline")

        col_s5, col_s6, col_s7, col_s8 = st.columns(4)
        with col_s5:
            sub_style["outline_color"] = st.color_picker("외곽선 색상", sub_style.get("outline_color", "#000000"), key="sub_outline_color")
        with col_s6:
            pos_options = ["상단", "중앙", "하단"]
            pos_idx = pos_options.index(sub_style.get("position", "하단")) if sub_style.get("position", "하단") in pos_options else 2
            sub_style["position"] = st.selectbox("위치", pos_options, index=pos_idx, key="sub_position")
        with col_s7:
            sub_style["margin_v"] = st.slider("상하 여백", 0, 100, sub_style.get("margin_v", 30), key="sub_margin_v")
        with col_s8:
            sub_style["bg_opacity"] = st.slider("배경 투명도", 0.0, 1.0, sub_style.get("bg_opacity", 0.5), step=0.1, key="sub_bg_opacity")

        col_s9, col_s10 = st.columns(2)
        with col_s9:
            sub_style["line_spacing"] = st.slider("줄간격", 1.0, 3.0, sub_style.get("line_spacing", 1.4), step=0.1, key="sub_line_spacing")
        with col_s10:
            st.caption("줄간격 1.0 = 촘촘 / 1.5 = 기본 / 2.0 = 넓음 / 3.0 = 매우 넓음")

        if ct == "쇼츠":
            st.session_state["subtitle_style_shorts"] = sub_style
        else:
            st.session_state["subtitle_style_long"] = sub_style

        st.divider()
        st.subheader("자막 미리보기")

        edited_lines = st.session_state["edited_sub_lines"]
        total_subs = len(edited_lines)

        preview_num = st.number_input("미리볼 자막 번호", min_value=1, max_value=total_subs, value=1, step=1, key="preview_num_input")
        preview_idx = preview_num - 1
        preview_text = edited_lines[preview_idx] if preview_idx < len(edited_lines) else ""
        preview_dur = durations[preview_idx] if preview_idx < len(durations) else 3.0

        font_name = FONT_MAP.get(sub_style.get("font", "나눔고딕 볼드"), "NanumGothicBold")
        font_import = "https://fonts.googleapis.com/css2?family=" + font_name.replace(" ", "+") + "&display=swap"

        pos_val = sub_style.get("position", "하단")
        if pos_val == "상단":
            vert_align = "flex-start"
            pad_area = "padding-top:" + str(sub_style.get("margin_v", 30)) + "px;"
        elif pos_val == "중앙":
            vert_align = "center"
            pad_area = ""
        else:
            vert_align = "flex-end"
            pad_area = "padding-bottom:" + str(sub_style.get("margin_v", 30)) + "px;"

        bg_r = int(sub_style.get("outline_color", "#000000")[1:3], 16)
        bg_g = int(sub_style.get("outline_color", "#000000")[3:5], 16)
        bg_b = int(sub_style.get("outline_color", "#000000")[5:7], 16)
        bg_a = sub_style.get("bg_opacity", 0.5)

        outline_w = sub_style.get("outline_width", 2)
        oc = sub_style.get("outline_color", "#000000")
        shadow_str = (
            oc + " " + str(outline_w) + "px " + str(outline_w) + "px 0px, "
            + oc + " -" + str(outline_w) + "px -" + str(outline_w) + "px 0px, "
            + oc + " " + str(outline_w) + "px -" + str(outline_w) + "px 0px, "
            + oc + " -" + str(outline_w) + "px " + str(outline_w) + "px 0px"
        )

        if ct == "쇼츠":
            box_w = "360px"
            box_h = "640px"
        else:
            box_w = "640px"
            box_h = "360px"

        font_size_px = str(sub_style.get("size", 28))
        font_color = sub_style.get("color", "#FFFFFF")
        line_height_val = str(sub_style.get("line_spacing", 1.4))

        preview_html = '<style>@import url("' + font_import + '");</style>'
        preview_html = preview_html + '<div style="width:' + box_w + ';height:' + box_h + ';background:#1a1a2e;border:2px solid #444;border-radius:8px;display:flex;align-items:' + vert_align + ';justify-content:center;' + pad_area + 'margin:0 auto;">'
        preview_html = preview_html + '<div style="background:rgba(' + str(bg_r) + ',' + str(bg_g) + ',' + str(bg_b) + ',' + str(bg_a) + ');padding:10px 24px;border-radius:6px;width:85%;text-align:center;">'
        preview_html = preview_html + '<span style="font-family:' + "'" + font_name + "'" + ',sans-serif;font-size:' + font_size_px + 'px;color:' + font_color + ';text-shadow:' + shadow_str + ';font-weight:bold;word-break:keep-all;overflow-wrap:break-word;white-space:normal;line-height:' + line_height_val + ';">'
        preview_html = preview_html + preview_text
        preview_html = preview_html + '</span></div></div>'

        st.markdown(preview_html, unsafe_allow_html=True)
        st.caption(str(preview_num) + "번 자막 (총 " + str(total_subs) + "개) / " + str(round(preview_dur, 1)) + "초 / 글자수: " + str(len(preview_text)))

        st.divider()
        st.subheader("자막 목록 한눈에 보기")

        list_html = '<div style="max-height:400px;overflow-y:auto;border:1px solid #333;border-radius:8px;padding:8px;">'
        for si in range(total_subs):
            s_text = edited_lines[si] if si < len(edited_lines) else ""
            s_dur = durations[si] if si < len(durations) else 3.0
            char_count = len(s_text)
            if char_count > 30:
                row_color = "#FF6B6B"
            elif char_count > 20:
                row_color = "#FFD93D"
            else:
                row_color = "#6BCB77"
            list_html = list_html + '<div style="padding:4px 8px;border-bottom:1px solid #2a2a2a;display:flex;align-items:center;">'
            list_html = list_html + '<span style="color:#888;font-size:12px;min-width:40px;">' + str(si + 1).zfill(3) + '</span>'
            list_html = list_html + '<span style="color:#AAA;font-size:11px;min-width:50px;">' + str(round(s_dur, 1)) + '초</span>'
            list_html = list_html + '<span style="color:' + row_color + ';font-size:11px;min-width:40px;">' + str(char_count) + '자</span>'
            list_html = list_html + '<span style="color:#DDD;font-size:13px;margin-left:8px;">' + s_text + '</span>'
            list_html = list_html + '</div>'
        list_html = list_html + '</div>'
        st.markdown(list_html, unsafe_allow_html=True)
        st.caption("빨간색: 30자 초과 / 노란색: 20~30자 / 초록색: 20자 이하")

        st.divider()
        st.subheader("긴 자막 자동 분할")
        max_chars = st.slider("한 줄 최대 글자수", 10, 40, 20, key="max_sub_chars")
        if st.button("긴 자막 자동 분할", key="btn_auto_split_subs", use_container_width=True):
            original = st.session_state.get("edited_sub_lines", [])
            new_lines = []
            for line in original:
                line = line.strip()
                if not line:
                    continue
                if len(line) <= max_chars:
                    new_lines.append(line)
                else:
                    words = line.split(" ")
                    current = ""
                    for w in words:
                        if current and len(current + " " + w) > max_chars:
                            new_lines.append(current.strip())
                            current = w
                        else:
                            current = current + " " + w if current else w
                    if current.strip():
                        new_lines.append(current.strip())
            st.session_state["edited_sub_lines"] = new_lines
            st.success("분할 완료! " + str(len(original)) + "개 → " + str(len(new_lines)) + "개")
            st.warning("자막이 분할되었습니다. 아래에서 SRT를 다시 생성하면 음성 싱크에 맞춰 자동 배분됩니다.")
            st.rerun()

        st.divider()
        st.subheader("자막 텍스트 편집")

        all_sub_text = "\n".join(st.session_state["edited_sub_lines"])
        edited_all = st.text_area("자막 전체 편집 (한 줄에 하나씩, 엔터로 구분)", value=all_sub_text, height=400, key="bulk_sub_edit")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("편집 내용 저장", key="btn_save_subs", use_container_width=True):
                new_lines = [l.strip() for l in edited_all.split("\n") if l.strip()]
                if len(new_lines) == 0:
                    st.error("자막이 비어있습니다.")
                else:
                    st.session_state["edited_sub_lines"] = new_lines
                    if len(new_lines) != len(durations):
                        st.warning("자막 수(" + str(len(new_lines)) + ")와 음성 수(" + str(len(durations)) + ")가 다릅니다.")
                    st.success("자막 저장 완료! " + str(len(new_lines)) + "개")
        with col_b2:
            if st.button("SRT 자막 생성", key="btn_gen_srt", use_container_width=True):
                sub_lines = st.session_state.get("edited_sub_lines", lines)
                if len(sub_lines) == len(durations):
                    srt = generate_srt(sub_lines, durations)
                else:
                    srt = generate_srt_split(sub_lines, durations)
                st.session_state["srt_content"] = srt
                st.success("SRT 생성 완료! (자막 " + str(len(sub_lines)) + "개 / 음성 " + str(len(durations)) + "개)")

        if st.session_state.get("srt_content"):
            with st.expander("SRT 내용 확인"):
                st.text(st.session_state["srt_content"][:3000])
            st.download_button("SRT 파일 다운로드", data=st.session_state["srt_content"], file_name="subtitles.srt", mime="text/plain", key="dl_srt")

# ─────────────────────────── 탭6: 최종 합치기 ───────────────────────────
with tab6:
    st.header("최종 영상 합치기")
    videos = st.session_state.get("uploaded_videos", [])
    audio_data = st.session_state.get("tts_audio_data", [])
    srt = st.session_state.get("srt_content", "")
    lines = st.session_state.get("script_lines", [])

    ready = True
    if not videos:
        st.warning("탭3에서 영상을 업로드해주세요.")
        ready = False
    if not audio_data or not any(a for a in audio_data if a):
        st.warning("탭4에서 TTS 음성을 생성해주세요.")
        ready = False
    if not srt:
        st.warning("탭5에서 SRT 자막을 생성해주세요.")
        ready = False

    if ready:
        ct = st.session_state.get("content_type", "쇼츠")
        if ct == "쇼츠":
            sub_style = st.session_state.get("subtitle_style_shorts", dict(DEFAULT_SUB_SHORTS))
        else:
            sub_style = st.session_state.get("subtitle_style_long", dict(DEFAULT_SUB_LONG))

        ok_audio = len([a for a in audio_data if a])
        info_msg = "영상 " + str(len(videos)) + "개 / 음성 " + str(ok_audio) + "개 / 자막 준비됨"
        st.markdown(
            '<div style="background:#1a2e1a;border:2px solid #4CAF50;border-radius:8px;padding:12px;">'
            + '<span style="color:#88CC88;">준비 상태:</span>'
            + '<span style="color:#FFF;font-weight:bold;margin-left:8px;">'
            + info_msg
            + '</span></div>',
            unsafe_allow_html=True
        )

        st.info("Streamlit Cloud에서 영상 합치기는 서버 성능 제한이 있습니다.")

        if st.button("최종 영상 합치기", key="btn_merge_final", use_container_width=True):
            ffmpeg_check = shutil.which("ffmpeg")
            if not ffmpeg_check:
                st.error("ffmpeg가 설치되어 있지 않습니다. packages.txt 파일을 확인해주세요.")
            else:
                with st.spinner("영상을 합치고 있습니다..."):
                    result, err = merge_final_video(videos, audio_data, srt, sub_style)
                    if err:
                        st.error(err)
                    elif result:
                        st.session_state["final_video"] = result
                        st.success("최종 영상 완성!")

        if st.session_state.get("final_video"):
            st.divider()
            st.subheader("완성된 영상")
            st.video(st.session_state["final_video"])
            fsize = len(st.session_state["final_video"]) / 1024 / 1024
            st.caption("파일 크기: " + str(round(fsize, 1)) + "MB")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = "final_" + ts + ".mp4"
            st.download_button(
                "영상 다운로드",
                data=st.session_state["final_video"],
                file_name=fname,
                mime="video/mp4",
                key="dl_final_video",
                use_container_width=True
            )
