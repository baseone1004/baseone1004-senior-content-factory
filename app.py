import streamlit as st
import json
import re
import os
import base64
import time
from datetime import datetime

st.set_page_config(page_title="시니어 콘텐츠 팩토리", layout="wide")

# ── 세션 스테이트 기본값 ──
defaults = {
    "selected_topic": "",
    "topics_list": [],
    "recommended_keywords": [],
    "channel_category": "경제/사회",
    "longform_script": "",
    "longform_metadata": {},
    "shorts_data": [],
    "shorts_raw": "",
    "generated_images_longform": [],
    "generated_images_shorts": {},
    "reference_image": None,
    "api_connected": False,
    "sub_settings_longform": {},
    "sub_settings_shorts": {},
    "tts_longform_audio": None,
    "tts_longform_timestamps": [],
    "tts_longform_srt": "",
    "tts_shorts_audio": {},
    "tts_shorts_timestamps": {},
    "tts_shorts_srt": {},
    "video_effects_longform": {},
    "video_effects_shorts": {},
    "video_results_longform": {},
    "video_results_shorts": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


@st.cache_resource
def load_api():
    from utils.api_handler import APIHandler
    return APIHandler()

try:
    api = load_api()
    st.session_state.api_connected = True
except Exception as e:
    api = None
    st.session_state.api_connected = False
    st.sidebar.error(f"API 로드 실패: {e}")


# ══════════════════════════════════════════════════════
#  핵심 안전 함수들
# ══════════════════════════════════════════════════════

def safe_generate(prompt_text):
    """api.generate() 결과를 안전하게 문자열로 변환.
    skywork_handler.generate()는 (text, error) 튜플을 반환함."""
    if not api:
        return ""
    try:
        raw = api.generate(prompt_text)
    except Exception as e:
        st.error(f"AI 생성 실패: {e}")
        return ""

    # ★ 핵심: 튜플 처리 (skywork_handler가 (text, error) 반환)
    if isinstance(raw, tuple):
        text_part = raw[0] if len(raw) > 0 else None
        error_part = raw[1] if len(raw) > 1 else None
        if error_part:
            st.warning(f"AI 경고: {error_part}")
        if text_part is None:
            return ""
        if isinstance(text_part, str):
            return text_part
        raw = text_part  # 아래에서 dict/list 등 추가 처리

    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ["text", "content", "result", "data", "message", "output", "generated_text", "response"]:
            val = raw.get(key)
            if isinstance(val, str) and len(val) > 3:
                return val
        for key in ["data", "result", "response"]:
            val = raw.get(key)
            if isinstance(val, dict):
                for subkey in ["text", "content", "message", "output"]:
                    subval = val.get(subkey)
                    if isinstance(subval, str) and len(subval) > 3:
                        return subval
        return json.dumps(raw, ensure_ascii=False)
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", "") or item.get("content", "") or json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(raw)


def safe_generate_image(prompt, aspect_ratio="9:16"):
    """api.generate_image()를 안전하게 호출. (url, error) 튜플 처리."""
    if not api:
        return None, "API 미연결"
    try:
        raw = api.generate_image(prompt, aspect_ratio)
    except Exception as e:
        return None, str(e)
    if isinstance(raw, tuple):
        return (raw[0], raw[1]) if len(raw) >= 2 else (raw[0] if raw else None, None)
    if isinstance(raw, str):
        return raw, None
    return None, "알 수 없는 반환 형식"


def sync_topic():
    t = st.session_state.selected_topic
    if t:
        st.session_state["longform_topic"] = t
        st.session_state["shorts_topic"] = t


def safe_naver_search(keyword, count):
    """네이버 검색. naver.search()도 (리스트, 에러) 튜플을 반환함."""
    if not api:
        return []
    raw_result = None
    # 1차: search
    try:
        r = api.naver.search(keyword, display=count)
        if isinstance(r, tuple):
            raw_result = r[0] if r[0] else None
        elif isinstance(r, list):
            raw_result = r
        elif isinstance(r, dict):
            raw_result = r.get("items", [r])
        else:
            raw_result = r
    except Exception:
        pass
    # 2차: search_trending_topics
    if not raw_result:
        try:
            r = api.naver.search_trending_topics([keyword], count)
            if isinstance(r, tuple):
                raw_result = r[0] if r[0] else None
            elif isinstance(r, list):
                raw_result = r
        except Exception:
            pass
    if not raw_result:
        return []
    if not isinstance(raw_result, list):
        if isinstance(raw_result, str):
            return [{"title": l, "description": ""} for l in raw_result.split("\n") if l.strip()]
        return []
    safe = []
    for item in raw_result:
        if isinstance(item, dict):
            safe.append(item)
        elif isinstance(item, str):
            safe.append({"title": item, "description": ""})
        else:
            safe.append({"title": str(item), "description": ""})
    return safe


# ══════════════════════════════════════════════════════
#  유틸리티 함수들
# ══════════════════════════════════════════════════════

def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def timestamps_to_srt(timestamps):
    lines = []
    for i, ts in enumerate(timestamps):
        lines.append(f"{i+1}")
        lines.append(f"{format_srt_time(ts.get('start',0))} --> {format_srt_time(ts.get('end',0))}")
        lines.append(ts.get("text", ""))
        lines.append("")
    return "\n".join(lines)


def estimate_timestamps_from_text(text, total_duration=None):
    sentences = re.split(r'(?<=[.?!])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []
    total_chars = sum(len(s) for s in sentences)
    if total_duration is None:
        total_duration = total_chars / 7.0
    result = []
    cur = 0.0
    for s in sentences:
        dur = max(0.5, (len(s) / max(total_chars, 1)) * total_duration)
        result.append({"text": s, "start": round(cur, 3), "end": round(cur + dur, 3)})
        cur += dur
    return result


def parse_tts_timestamps(raw, script_text):
    if not raw:
        return estimate_timestamps_from_text(script_text)
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            if "start" in first and "text" in first:
                return raw
            if "startTime" in first:
                return [{"text": t.get("text",""), "start": t["startTime"], "end": t.get("endTime", t["startTime"]+1)} for t in raw]
            if "offset" in first:
                return [{"text": t.get("text",""), "start": t["offset"], "end": t["offset"]+t.get("duration",1)} for t in raw]
    if isinstance(raw, dict):
        for key in ["words", "sentences", "segments"]:
            if key in raw:
                return parse_tts_timestamps(raw[key], script_text)
    return estimate_timestamps_from_text(script_text)


CAMERA_EFFECTS = {
    "없음": {"desc": "정지 이미지 그대로", "icon": "⏸️"},
    "줌인 (느린)": {"desc": "중앙으로 천천히 확대", "icon": "🔍"},
    "줌인 (빠른)": {"desc": "중앙으로 빠르게 확대", "icon": "🔍💨"},
    "줌아웃 (느린)": {"desc": "확대 상태에서 천천히 축소", "icon": "🔭"},
    "줌아웃 (빠른)": {"desc": "확대 상태에서 빠르게 축소", "icon": "🔭💨"},
    "좌→우 패닝": {"desc": "왼쪽에서 오른쪽으로 이동", "icon": "➡️"},
    "우→좌 패닝": {"desc": "오른쪽에서 왼쪽으로 이동", "icon": "⬅️"},
    "상→하 패닝": {"desc": "위에서 아래로 이동", "icon": "⬇️"},
    "하→상 패닝": {"desc": "아래에서 위로 이동", "icon": "⬆️"},
    "켄번스 좌상→우하": {"desc": "줌인+좌상→우하 이동", "icon": "↘️🔍"},
    "켄번스 우상→좌하": {"desc": "줌인+우상→좌하 이동", "icon": "↙️🔍"},
    "켄번스 중앙→좌": {"desc": "줌인+중앙→왼쪽 이동", "icon": "⬅️🔍"},
    "켄번스 중앙→우": {"desc": "줌인+중앙→오른쪽 이동", "icon": "➡️🔍"},
    "흔들림 (약한)": {"desc": "미세한 떨림 효과", "icon": "〰️"},
    "펄스 줌": {"desc": "줌인-줌아웃 반복", "icon": "💥"},
}


def effect_to_ffmpeg(effect_name, duration=5.0, w=1920, h=1080):
    fps = 30
    d = int(duration * fps)
    effects_map = {
        "없음": f"zoompan=z=1:d={d}:x=0:y=0:s={w}x{h}:fps={fps}",
        "줌인 (느린)": f"zoompan=z='min(zoom+0.002,1.3)':d={d}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "줌인 (빠른)": f"zoompan=z='min(zoom+0.005,1.5)':d={d}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "줌아웃 (느린)": f"zoompan=z='if(eq(on,1),1.3,max(zoom-0.002,1))':d={d}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "줌아웃 (빠른)": f"zoompan=z='if(eq(on,1),1.5,max(zoom-0.005,1))':d={d}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "좌→우 패닝": f"zoompan=z=1.1:d={d}:x='iw*0.1*on/{d}':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "우→좌 패닝": f"zoompan=z=1.1:d={d}:x='iw*0.1*(1-on/{d})':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "상→하 패닝": f"zoompan=z=1.1:d={d}:x='iw/2-(iw/zoom/2)':y='ih*0.1*on/{d}':s={w}x{h}:fps={fps}",
        "하→상 패닝": f"zoompan=z=1.1:d={d}:x='iw/2-(iw/zoom/2)':y='ih*0.1*(1-on/{d})':s={w}x{h}:fps={fps}",
        "켄번스 좌상→우하": f"zoompan=z='min(zoom+0.002,1.3)':d={d}:x='iw*0.1*on/{d}':y='ih*0.1*on/{d}':s={w}x{h}:fps={fps}",
        "켄번스 우상→좌하": f"zoompan=z='min(zoom+0.002,1.3)':d={d}:x='iw*0.1*(1-on/{d})':y='ih*0.1*on/{d}':s={w}x{h}:fps={fps}",
        "켄번스 중앙→좌": f"zoompan=z='min(zoom+0.002,1.3)':d={d}:x='iw/2-(iw/zoom/2)-iw*0.05*on/{d}':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "켄번스 중앙→우": f"zoompan=z='min(zoom+0.002,1.3)':d={d}:x='iw/2-(iw/zoom/2)+iw*0.05*on/{d}':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "흔들림 (약한)": f"zoompan=z=1.05:d={d}:x='iw/2-(iw/zoom/2)+2*sin(on*0.5)':y='ih/2-(ih/zoom/2)+2*cos(on*0.7)':s={w}x{h}:fps={fps}",
        "펄스 줌": f"zoompan=z='1+0.1*sin(on*0.15)':d={d}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
    }
    return effects_map.get(effect_name, effects_map["없음"])


def build_effect_preview_html(effect_name, img_url=None, ratio="16:9"):
    cw, ch = (180, 320) if ratio == "9:16" else (320, 180)
    bg = f"url('{img_url}') center/cover" if img_url else "linear-gradient(135deg,#1a1a3e,#2a1a4e,#1a2a3e)"
    anim_map = {
        "없음": "",
        "줌인 (느린)": "animation: zoomInSlow 4s ease-in-out infinite alternate;",
        "줌인 (빠른)": "animation: zoomInFast 2s ease-in-out infinite alternate;",
        "줌아웃 (느린)": "animation: zoomOutSlow 4s ease-in-out infinite alternate;",
        "줌아웃 (빠른)": "animation: zoomOutFast 2s ease-in-out infinite alternate;",
        "좌→우 패닝": "animation: panLR 4s linear infinite alternate;",
        "우→좌 패닝": "animation: panRL 4s linear infinite alternate;",
        "상→하 패닝": "animation: panTB 4s linear infinite alternate;",
        "하→상 패닝": "animation: panBT 4s linear infinite alternate;",
        "켄번스 좌상→우하": "animation: kenTLBR 5s ease-in-out infinite alternate;",
        "켄번스 우상→좌하": "animation: kenTRBL 5s ease-in-out infinite alternate;",
        "켄번스 중앙→좌": "animation: kenCL 5s ease-in-out infinite alternate;",
        "켄번스 중앙→우": "animation: kenCR 5s ease-in-out infinite alternate;",
        "흔들림 (약한)": "animation: shake 0.5s ease-in-out infinite;",
        "펄스 줌": "animation: pulse 1.5s ease-in-out infinite;",
    }
    anim = anim_map.get(effect_name, "")
    return f"""<style>
@keyframes zoomInSlow{{from{{transform:scale(1)}}to{{transform:scale(1.3)}}}}
@keyframes zoomInFast{{from{{transform:scale(1)}}to{{transform:scale(1.5)}}}}
@keyframes zoomOutSlow{{from{{transform:scale(1.3)}}to{{transform:scale(1)}}}}
@keyframes zoomOutFast{{from{{transform:scale(1.5)}}to{{transform:scale(1)}}}}
@keyframes panLR{{from{{transform:translateX(-5%) scale(1.1)}}to{{transform:translateX(5%) scale(1.1)}}}}
@keyframes panRL{{from{{transform:translateX(5%) scale(1.1)}}to{{transform:translateX(-5%) scale(1.1)}}}}
@keyframes panTB{{from{{transform:translateY(-5%) scale(1.1)}}to{{transform:translateY(5%) scale(1.1)}}}}
@keyframes panBT{{from{{transform:translateY(5%) scale(1.1)}}to{{transform:translateY(-5%) scale(1.1)}}}}
@keyframes kenTLBR{{from{{transform:translate(-3%,-3%) scale(1)}}to{{transform:translate(3%,3%) scale(1.3)}}}}
@keyframes kenTRBL{{from{{transform:translate(3%,-3%) scale(1)}}to{{transform:translate(-3%,3%) scale(1.3)}}}}
@keyframes kenCL{{from{{transform:translateX(0) scale(1)}}to{{transform:translateX(-5%) scale(1.3)}}}}
@keyframes kenCR{{from{{transform:translateX(0) scale(1)}}to{{transform:translateX(5%) scale(1.3)}}}}
@keyframes shake{{0%,100%{{transform:translate(0,0) scale(1.05)}}25%{{transform:translate(-2px,1px) scale(1.05)}}50%{{transform:translate(1px,-2px) scale(1.05)}}75%{{transform:translate(2px,1px) scale(1.05)}}}}
@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.1)}}}}
</style>
<div style="width:{cw}px;height:{ch}px;overflow:hidden;border-radius:8px;border:1px solid #444;margin:5px auto;position:relative;">
<div style="width:100%;height:100%;background:{bg};{anim}transform-origin:center center;"></div>
<div style="position:absolute;bottom:4px;right:6px;color:#fff8;font-size:9px;font-family:monospace;background:rgba(0,0,0,0.5);padding:1px 4px;border-radius:3px;">{effect_name}</div>
</div>"""


def build_subtitle_preview_html(settings, preview_text, ratio="16:9"):
    font = settings.get("font", "Noto Sans KR")
    size = settings.get("size", 48)
    color = settings.get("color", "#FFFFFF")
    oc = settings.get("outline_color", "#000000")
    ow = settings.get("outline_width", 3)
    sc = settings.get("shadow_color", "#000000")
    sb = settings.get("shadow_blur", 4)
    bgc = settings.get("bg_color", "#000000")
    bgo = settings.get("bg_opacity", 0)
    position = settings.get("position", "하단")
    pos_b = settings.get("pos_bottom", 40)
    pos_l = settings.get("pos_left", 20)
    pos_r = settings.get("pos_right", 20)
    align = settings.get("align", "center")
    bold = settings.get("bold", True)
    italic = settings.get("italic", False)
    ls = settings.get("letter_spacing", 0)
    lh = settings.get("line_height", 1.5)
    cw, ch = (270, 480) if ratio == "9:16" else (540, 304)
    ds = max(10, size // (4 if ratio == "9:16" else 3))
    if position == "하단":
        pos_css = f"bottom:{pos_b}px;"
    elif position == "상단":
        pos_css = f"top:{settings.get('pos_top', 30)}px;"
    else:
        pos_css = "top:50%;transform:translateY(-50%);"
    try:
        br = int(bgc[1:3], 16)
        bgg = int(bgc[3:5], 16)
        bb = int(bgc[5:7], 16)
    except:
        br, bgg, bb = 0, 0, 0
    gf = f'<link href="https://fonts.googleapis.com/css2?family={font.replace(" ", "+")}&display=swap" rel="stylesheet">'
    return f"""{gf}<div style="position:relative;width:{cw}px;height:{ch}px;background:linear-gradient(180deg,#0a0a1a,#1a1a3e,#0a0a1a);border-radius:12px;overflow:hidden;margin:10px auto;border:1px solid #444;">
<div style="position:absolute;top:45%;left:50%;transform:translate(-50%,-50%);color:#ffffff08;font-size:40px;font-weight:bold;">VIDEO</div>
<div style="position:absolute;{pos_css}left:{pos_l}px;right:{pos_r}px;text-align:{align};z-index:10;">
<span style="font-family:'{font}',sans-serif;font-size:{ds}px;font-weight:{'bold' if bold else 'normal'};font-style:{'italic' if italic else 'normal'};color:{color};-webkit-text-stroke:{max(1,ow)}px {oc};paint-order:stroke fill;text-shadow:{sb}px {sb}px {sb*2}px {sc},-{sb}px -{sb}px {sb*2}px {sc};background:rgba({br},{bgg},{bb},{bgo/100});padding:6px 14px;border-radius:6px;letter-spacing:{ls}px;line-height:{lh};display:inline-block;">{preview_text}</span>
</div></div>"""


def subtitle_settings_ui(prefix, ratio="16:9"):
    FONTS = ["Noto Sans KR","Noto Serif KR","Black Han Sans","Jua","Do Hyeon","Gothic A1","Sunflower","Gaegu","Hi Melody","Song Myung","Stylish","Gugi","Gamja Flower","East Sea Dokdo","Cute Font","Yeon Sung","Poor Story","Single Day","Black And White Picture","Dokdo"]
    s = {}
    st.markdown("**글씨체**")
    c1, c2 = st.columns([2, 1])
    with c1:
        s["font"] = st.selectbox("글씨체", FONTS, 0, key=f"{prefix}_font")
    with c2:
        s["size"] = st.number_input("크기(px)", 16, 120, 48, 1, key=f"{prefix}_size")
    st.markdown("**스타일**")
    sc2 = st.columns(4)
    with sc2[0]:
        s["bold"] = st.checkbox("굵게", True, key=f"{prefix}_bold")
    with sc2[1]:
        s["italic"] = st.checkbox("기울임", False, key=f"{prefix}_italic")
    with sc2[2]:
        s["letter_spacing"] = st.number_input("자간", -5, 20, 0, 1, key=f"{prefix}_ls")
    with sc2[3]:
        s["line_height"] = st.number_input("행간", 1.0, 3.0, 1.5, 0.1, key=f"{prefix}_lh")
    st.markdown("**색상**")
    cc = st.columns(4)
    with cc[0]:
        s["color"] = st.color_picker("글자", "#FFFFFF", key=f"{prefix}_color")
    with cc[1]:
        s["outline_color"] = st.color_picker("외곽선", "#000000", key=f"{prefix}_oc")
    with cc[2]:
        s["shadow_color"] = st.color_picker("그림자", "#000000", key=f"{prefix}_sc")
    with cc[3]:
        s["bg_color"] = st.color_picker("배경", "#000000", key=f"{prefix}_bgc")
    st.markdown("**효과**")
    ec = st.columns(3)
    with ec[0]:
        s["outline_width"] = st.slider("외곽선", 0, 8, 2, 1, key=f"{prefix}_ow")
    with ec[1]:
        s["shadow_blur"] = st.slider("그림자", 0, 20, 4, 1, key=f"{prefix}_sb")
    with ec[2]:
        s["bg_opacity"] = st.slider("배경(%)", 0, 100, 0, 5, key=f"{prefix}_bgo")
    st.markdown("**위치**")
    s["position"] = st.radio("위치", ["상단", "중앙", "하단"], 2, horizontal=True, key=f"{prefix}_pos")
    st.markdown("**미세조절 (px)**")
    pc = st.columns(4)
    with pc[0]:
        s["pos_top"] = st.number_input("위", 0, 500, 30, 1, key=f"{prefix}_mt")
    with pc[1]:
        s["pos_bottom"] = st.number_input("아래", 0, 500, 40, 1, key=f"{prefix}_mb")
    with pc[2]:
        s["pos_left"] = st.number_input("좌", 0, 300, 20, 1, key=f"{prefix}_ml")
    with pc[3]:
        s["pos_right"] = st.number_input("우", 0, 300, 20, 1, key=f"{prefix}_mr")
    s["align"] = st.radio("정렬", ["left", "center", "right"], 1, horizontal=True, key=f"{prefix}_align",
                           format_func=lambda x: {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}[x])
    return s


def build_sync_timeline_html(timestamps, dur=None):
    if not timestamps:
        return ""
    total = dur or (timestamps[-1]["end"] if timestamps else 10)
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#E91E63", "#9C27B0", "#00BCD4", "#FF5722", "#795548"]
    rows = ""
    for i, ts in enumerate(timestamps):
        sp = (ts["start"] / max(total, 0.1)) * 100
        wp = max(0.5, ((ts["end"] - ts["start"]) / max(total, 0.1)) * 100)
        c = colors[i % len(colors)]
        rows += f'<div style="display:flex;align-items:center;margin:2px 0;height:28px;"><div style="width:30px;color:#888;font-size:10px;text-align:right;margin-right:6px;">{i+1}</div><div style="flex:1;position:relative;height:22px;background:#1a1a2e;border-radius:4px;overflow:hidden;"><div style="position:absolute;left:{sp}%;width:{wp}%;height:100%;background:{c};border-radius:3px;display:flex;align-items:center;padding:0 4px;overflow:hidden;"><span style="color:#fff;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{ts["text"][:20]}</span></div></div><div style="width:100px;color:#aaa;font-size:9px;margin-left:6px;font-family:monospace;">{ts["start"]:.1f}s~{ts["end"]:.1f}s</div></div>'
    return f'<div style="background:#0a0a1a;border:1px solid #333;border-radius:8px;padding:12px;margin:10px 0;"><div style="color:#ccc;font-size:12px;font-weight:bold;margin-bottom:8px;">싱크 타임라인 ({total:.1f}초 / {len(timestamps)}개)</div>{rows}</div>'


# ══════════════════════════════════════════════════════
#  사이드바
# ══════════════════════════════════════════════════════

with st.sidebar:
    st.title("시니어 콘텐츠 팩토리")
    st.divider()
    if st.session_state.selected_topic:
        st.success(f"선택된 주제: {st.session_state.selected_topic}")
    else:
        st.info("주제를 먼저 선택하세요")
    st.divider()
    st.subheader("레퍼런스 이미지")
    ref_file = st.file_uploader("주인공 이미지", type=["png", "jpg", "jpeg"])
    if ref_file:
        st.session_state.reference_image = ref_file.getvalue()
        st.image(ref_file, caption="레퍼런스", use_container_width=True)
    st.divider()
    if st.button("API 연결 테스트"):
        if api:
            try:
                ok, msg = api.test_connection()
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)
            except Exception as e:
                st.error(str(e))
    st.divider()
    if st.button("전체 초기화", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ══════════════════════════════════════════════════════
#  메인 탭
# ══════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "주제 추천", "롱폼 대본", "쇼츠 대본", "이미지 생성", "영상 변환", "음성 합성", "자막 설정", "최종 합치기"
])


# ═══ 탭1: 주제 추천 ═══
with tab1:
    st.header("떡상 주제 추천")

    # 채널 카테고리 (4개만)
    categories = [
        "경제/사회",
        "시니어 창작 민담/설화",
        "창작 미스터리/괴담",
        "창작 역사",
    ]

    # 카테고리별 자동 검색 키워드 (키워드 입력란 제거 → 자동 매핑)
    CATEGORY_SEARCH_MAP = {
        "경제/사회": ["경제 위기", "물가 상승", "고용 시장", "자영업 폐업", "부동산 시장", "금리"],
        "시니어 창작 민담/설화": ["한국 민담", "전래동화", "설화", "옛날이야기", "구전설화"],
        "창작 미스터리/괴담": ["미스터리 사건", "괴담", "미해결 사건", "도시전설", "공포"],
        "창작 역사": ["한국 역사", "역사 인물", "조선시대", "삼국시대", "근현대사"],
    }

    cat_col, cnt_col = st.columns([3, 1])
    with cat_col:
        selected_cat = st.selectbox("채널 카테고리", categories, index=0, key="channel_cat_select")
    with cnt_col:
        news_count = st.number_input("뉴스 수", 3, 20, 10, key="news_count")

    st.divider()

    if st.button("떡상 주제 추천 받기", type="primary", use_container_width=True):
        if not api:
            st.error("API 미연결")
        else:
            with st.spinner("뉴스 수집 및 분석 중..."):
                # 카테고리에 매핑된 키워드로 자동 검색
                search_keywords = CATEGORY_SEARCH_MAP.get(selected_cat, [selected_cat])
                all_news = []
                for kw in search_keywords:
                    results = safe_naver_search(kw, count=news_count)
                    all_news.extend(results)

                # 중복 제거 및 제한
                seen_titles = set()
                unique_news = []
                for item in all_news:
                    t = item.get("title", "") if isinstance(item, dict) else str(item)
                    short = t[:30]
                    if short not in seen_titles:
                        seen_titles.add(short)
                        unique_news.append(item)
                unique_news = unique_news[:news_count * 2]

                nt = ""
                for item in unique_news:
                    t = re.sub(r'<[^>]+>', '', str(item.get("title", "") if isinstance(item, dict) else item))
                    d = re.sub(r'<[^>]+>', '', str(item.get("description", "") if isinstance(item, dict) else ""))
                    nt += f"- {t}: {d}\n"

                with st.expander("수집된 뉴스 (디버그)"):
                    st.text(nt or "(없음)")

                # 카테고리별 프롬프트 분기
                if selected_cat == "경제/사회":
                    prompt = f"""아래 최신 뉴스를 분석해서 시니어 유튜브 채널용 떡상 주제 10개를 추천해줘.
카테고리: 경제/사회
뉴스:
{nt or '(최신 뉴스 없음)'}

반드시 사실 기반 뉴스에서 파생된 주제만 추천해. 창작 금지.
반드시 정확히 10개를 아래 형식으로 출력해:
1번|제목: 제목내용|확률: 높음/중간/낮음|출처: 출처내용|대안: 대안제목|태그: 태그1,태그2,태그3
2번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ...
(10번까지)"""

                elif selected_cat == "시니어 창작 민담/설화":
                    prompt = f"""당신은 시니어 유튜브 채널 기획자입니다.
카테고리: 시니어 창작 민담/설화

아래 뉴스에서 영감을 받아 한국 전래동화, 민담, 설화를 현대적으로 재해석한 시니어 맞춤 영상 주제 10개를 추천해줘.
참고 뉴스:
{nt or '(없음)'}

옛날이야기를 시니어가 손주에게 들려주는 느낌으로 기획해.
반드시 정확히 10개를 아래 형식으로 출력해:
1번|제목: 제목내용|확률: 높음/중간/낮음|출처: 출처내용|대안: 대안제목|태그: 태그1,태그2,태그3
(10번까지)"""

                elif selected_cat == "창작 미스터리/괴담":
                    prompt = f"""당신은 시니어 유튜브 채널 기획자입니다.
카테고리: 창작 미스터리/괴담

아래 뉴스에서 영감을 받아 미스터리, 괴담, 도시전설 주제의 시니어 맞춤 영상 주제 10개를 추천해줘.
참고 뉴스:
{nt or '(없음)'}

무섭지만 흥미로운 이야기, 미해결 사건 분석, 도시전설 검증 등의 방향으로 기획해.
반드시 정확히 10개를 아래 형식으로 출력해:
1번|제목: 제목내용|확률: 높음/중간/낮음|출처: 출처내용|대안: 대안제목|태그: 태그1,태그2,태그3
(10번까지)"""

                elif selected_cat == "창작 역사":
                    prompt = f"""당신은 시니어 유튜브 채널 기획자입니다.
카테고리: 창작 역사

아래 뉴스에서 영감을 받아 한국 역사를 재미있게 풀어내는 시니어 맞춤 영상 주제 10개를 추천해줘.
참고 뉴스:
{nt or '(없음)'}

역사 인물, 사건, 시대를 흥미진진하게 이야기하는 방향으로 기획해.
반드시 정확히 10개를 아래 형식으로 출력해:
1번|제목: 제목내용|확률: 높음/중간/낮음|출처: 출처내용|대안: 대안제목|태그: 태그1,태그2,태그3
(10번까지)"""

                else:
                    prompt = f"'{selected_cat}' 카테고리로 시니어 유튜브 주제 10개 추천해줘."

                raw_str = safe_generate(prompt)

                with st.expander("AI 응답 (디버그)"):
                    st.code(raw_str if raw_str else "(응답 없음)")

                topics = []
                if raw_str:
                    for line in raw_str.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        m = re.search(r'제목:\s*(.+?)(?:\||$)', line)
                        if m:
                            def safe_group(pat, ln):
                                mm = re.search(pat, ln)
                                return mm.group(1).strip() if mm else ""
                            topics.append({
                                "title": m.group(1).strip().strip("*"),
                                "probability": safe_group(r'확률:\s*(.+?)(?:\||$)', line),
                                "source": safe_group(r'출처:\s*(.+?)(?:\||$)', line),
                                "alternative": safe_group(r'대안:\s*(.+?)(?:\||$)', line),
                                "tags": safe_group(r'태그:\s*(.+?)(?:\||$)', line),
                            })
                        else:
                            m2 = re.match(r'^\d+[\.\)]\s*(.+)', line)
                            if m2:
                                topics.append({"title": m2.group(1).strip(), "probability": "", "source": "", "alternative": "", "tags": ""})
                    st.session_state.topics_list = topics

                if not topics:
                    st.warning("주제 파싱 실패. AI 응답 탭을 확인하세요.")

    if st.session_state.topics_list:
        for i, t in enumerate(st.session_state.topics_list):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{i+1}. {t['title']}**")
                    st.caption(f"확률:{t['probability']} | 출처:{t['source']} | 대안:{t['alternative']} | 태그:{t['tags']}")
                with c2:
                    if st.button("선택", key=f"pick_{i}", use_container_width=True):
                        st.session_state.selected_topic = t["title"]
                        sync_topic()
                        st.rerun()

    st.divider()
    manual = st.text_input("직접 입력", key="manual_topic_input")
    if st.button("이 주제로 설정"):
        if manual.strip():
            st.session_state.selected_topic = manual.strip()
            sync_topic()
            st.rerun()



# ═══ 탭2: 롱폼 대본 ═══
with tab2:
    st.subheader("롱폼 대본 생성")

    if not st.session_state.get("selected_topic"):
        st.info("탭1에서 주제를 먼저 선택하세요.")
    else:
        st.success(f"선택된 주제: {st.session_state.selected_topic}")

        if st.button("롱폼 대본 생성", key="gen_long"):
            topic = st.session_state.selected_topic
            category = st.session_state.get("selected_category", "경제/사회")

            long_prompt = f"""당신은 유튜브 롱폼 영상 전문 대본 작가입니다.

주제: {topic}
카테고리: {category}

아래 규칙을 반드시 지키세요.

출력형식 규칙:
제목과 태그와 설명과 대본을 아래 구분자로 정확히 나누어 출력하세요.

===제목===
제목을 한 줄로 씁니다. 오십 자 이내. 특수기호 금지.

===태그===
쉼표로 구분. 십오 개에서 이십 개. 특수기호 금지. 해시태그 기호 금지.

===설명===
약 이백 자. 특수기호 금지. 해시태그 기호 금지.

===대본===
순수 대사만 씁니다. 역할 표시 금지. 내레이션이라는 단어 금지. 진행자라는 단어 금지. 번호 매기기 금지.
마침표만 사용합니다. 물음표와 느낌표와 특수기호를 사용하지 않습니다.
습니다체를 기본으로 깔되 중간중간 까요체로 질문을 던집니다.
모든 영어와 외래어는 한글 순화어로 교체합니다.
모든 숫자는 한글로 표기합니다.
첫 문장부터 현장감 있게 시작합니다. 인사하지 않습니다. 자기소개하지 않습니다.
금지어: 안녕하세요, 여러분, 오늘은, 소개해 드릴, 알아볼게요, 구독, 좋아요, 알림, 눌러주세요, 도움이 되셨다면, 감사합니다, 다음에 또, 좋은 영상, 찾아오겠습니다.
마지막 문장은 묵직한 여운으로 끝냅니다.
전체 분량은 사십 문장에서 육십 문장 사이로 합니다."""

            with st.spinner("롱폼 대본 생성 중..."):
                raw = safe_generate(long_prompt)

            if raw:
                import re as _re

                def clean_special(text):
                    text = text.replace("#", "").replace("*", "").replace("_", "")
                    text = text.replace("!", "").replace("?", "").replace(";", "")
                    text = text.replace("~", "").replace("`", "").replace('"', "")
                    text = text.replace("'", "").replace("(", "").replace(")", "")
                    text = text.replace("[", "").replace("]", "").replace("{", "").replace("}", "")
                    text = text.replace("<", "").replace(">", "").replace("|", "")
                    text = text.replace("@", "").replace("$", "").replace("%", "")
                    text = text.replace("^", "").replace("&", "").replace("+", "").replace("=", "")
                    return text.strip()

                def extract_section(text, start_marker, end_marker=None):
                    try:
                        s = text.split(start_marker)[1]
                        if end_marker:
                            s = s.split(end_marker)[0]
                        return s.strip()
                    except:
                        return ""

                title = clean_special(extract_section(raw, "===제목===", "===태그==="))
                tags = clean_special(extract_section(raw, "===태그===", "===설명==="))
                desc = clean_special(extract_section(raw, "===설명===", "===대본==="))
                script = clean_special(extract_section(raw, "===대본==="))

                st.session_state.long_title = title
                st.session_state.long_tags = tags
                st.session_state.long_desc = desc
                st.session_state.long_script = script
                st.session_state.long_raw = raw

        if st.session_state.get("long_title"):
            st.markdown("---")
            st.markdown("**제목**")
            st.code(st.session_state.long_title, language=None)

            st.markdown("**태그**")
            st.code(st.session_state.long_tags, language=None)

            st.markdown("**설명**")
            st.code(st.session_state.long_desc, language=None)

            st.markdown("**대본**")
            st.code(st.session_state.long_script, language=None)

            sentences = [s.strip() for s in st.session_state.long_script.split(".") if s.strip()]
            st.session_state.long_sentences = sentences
            st.caption(f"총 {len(sentences)}문장")

# ═══ 탭3: 쇼츠 대본 ═══
with tab3:
    st.subheader("쇼츠 대본 생성 (3편 세트)")

    if not st.session_state.get("selected_topic"):
        st.info("탭1에서 주제를 먼저 선택하세요.")
    else:
        st.success(f"선택된 주제: {st.session_state.selected_topic}")

        if st.button("쇼츠 3편 세트 생성", key="gen_shorts"):
            topic = st.session_state.selected_topic
            category = st.session_state.get("selected_category", "경제/사회")

            shorts_prompt = f"""당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가입니다.

대주제: {topic}
카테고리: {category}

세트 기획 규칙:
하나의 대주제에서 세 개의 소주제를 도출합니다.
세 개의 소주제는 반드시 서로 중복되지 않아야 합니다.
아래 여덟 가지 관점에서 골고루 뽑습니다.
관점 하나. 몰락 원인 분석.
관점 둘. 전성기 실태.
관점 셋. 내부 폭로.
관점 넷. 비교 분석.
관점 다섯. 수익 구조.
관점 여섯. 피해자 시점.
관점 일곱. 현재 상황.
관점 여덟. 미래 전망.
세 편을 채울 때 위 여덟 관점에서 가장 흥미로운 세 가지를 고릅니다.

백만 조회수 대본 핵심 원칙:
시청자가 스와이프하지 못하고 끝까지 보게 만드는 것이 목적입니다.
인사하지 않습니다. 자기소개하지 않습니다. 구독 좋아요 언급하지 않습니다.

일초 법칙. 첫 문장이 곧 생사입니다. 현장 투척형 또는 통념 파괴형 또는 공감 소환형 또는 충격 수치형 또는 질문 관통형으로 시작합니다.
삼초 궁금증 폭탄. 처음 세 문장 안에 열린 고리를 겁니다.
근데의 힘. 사용 접속사는 근데 그래서 결국 알고 보니 문제는. 피해야 하는 접속사는 그리고 또한 뿐만 아니라 한편.
한 문장 한 호흡. 열다섯 자에서 마흔 자 사이. 쉰 자 넘으면 두 개로 쪼갭니다.
번호 매기기 금지. 하나의 이야기 흐름으로 이어갑니다.
습니다 까요 혼합체. 습니다체 기본에 중간중간 까요체로 질문을 던집니다.
감정 곡선 설계. 충격 공감 분노 반전 여운 순서.
중간 고리. 오 초마다 새로운 미끼를 던집니다.
마무리. 묵직한 여운형 또는 다음 편 유도형.
반복 시청 유도. 마지막 문장의 끝이 첫 문장의 시작과 자연스럽게 이어지게 합니다.

대본 작성 규칙:
각 편당 최소 팔 문장 최대 십오 문장.
마침표만 사용합니다. 물음표 느낌표 특수기호 금지.
모든 영어와 외래어는 한글 순화어로 교체합니다.
모든 숫자는 한글로 표기합니다.
구어체를 사용합니다.
대본 안에 역할 표시 금지. 내레이션 진행자 등의 단어 금지.
금지어: 안녕하세요, 여러분, 오늘은, 소개해 드릴, 알아볼게요, 구독, 좋아요, 알림, 눌러주세요, 도움이 되셨다면, 감사합니다, 다음에 또, 좋은 영상, 찾아오겠습니다.

이미지 프롬프트 규칙:
장면 수는 대사 문장 수와 일대일 매칭입니다.
모든 프롬프트의 맨 앞에 반드시 SD 2D anime style,을 붙입니다.
주인공이 등장하는 장면은 맨 뒤에 반드시 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 9:16 vertical aspect ratio를 붙입니다.
주인공이 등장하지 않는 장면은 맨 뒤에 반드시 9:16 vertical aspect ratio를 붙입니다.

장면 유형 판단 규칙:
유형 가. 대상 설명 장면. 주인공 없음. 문장의 주어가 건물 제품 기계 회사 데이터 등일 때.
유형 나. 실제 인물 장면. 주인공 없음. 문장의 주어가 실제 유명인일 때.
유형 다. 주인공 시점 장면. 주인공 등장. 나레이션 시점 리액션 질문 의문 감상 해석 시청자에게 말을 거는 장면.

주인공 복장 규칙:
주인공은 상황에 맞는 복장을 입습니다. 같은 맥락이면 복장 유지. 한 편 안에서 복장 변경은 최대 한 번.

한글 간판 규칙:
장면 내용과 연관된 한글 간판을 자연스럽게 배치합니다. 내용과 무관한 간판은 넣지 않습니다.

감정 표현:
충격은 wide eyes dropped jaw sweat drops.
분노는 cross mark on forehead red aura fire effect.
슬픔은 tears flowing blue aura rain clouds.
두려움은 shaking blue pale face ghost effect.

출력 형식을 반드시 정확히 따르세요:

=001=

제목: (오십 자 이내. 숫자는 아라비아 숫자)

상단제목 첫째 줄: (십오 자 이내)
상단제목 둘째 줄: (십오 자 이내)

설명글: (약 이백 자)

태그: (쉼표로 구분. 십오 개에서 이십 개. 해시태그 기호 금지)

순수 대본:
(문장만 마침표로 나열. 역할 표시 없음. 번호 없음.)

=장면001=
대사: (첫 번째 문장)
프롬프트: SD 2D anime style, (장면 묘사), (접미어 규칙에 따라 마무리)

=장면002=
대사: (두 번째 문장)
프롬프트: SD 2D anime style, (장면 묘사), (접미어 규칙에 따라 마무리)

(대사 문장 수만큼 장면 반복)

=002=
(동일한 형식)

=003=
(동일한 형식)

마지막 장면 프롬프트 출력 후 바로 끝냅니다. 추가 멘트 금지."""

            with st.spinner("쇼츠 3편 세트 생성 중..."):
                raw = safe_generate(shorts_prompt)

            if raw:
                st.session_state.shorts_raw = raw

        if st.session_state.get("shorts_raw"):
            raw = st.session_state.shorts_raw

            import re as _re

            def clean_special_shorts(text):
                text = text.replace("#", "").replace("*", "").replace("_", "")
                text = text.replace("!", "").replace("?", "").replace(";", "")
                text = text.replace("~", "").replace("`", "").replace('"', "")
                text = text.replace("'", "").replace("(", "").replace(")", "")
                text = text.replace("[", "").replace("]", "").replace("{", "").replace("}", "")
                text = text.replace("<", "").replace(">", "").replace("|", "")
                text = text.replace("@", "").replace("$", "").replace("%", "")
                text = text.replace("^", "").replace("&", "").replace("+", "").replace("=", "")
                return text.strip()

            shorts_list = []
            parts = _re.split(r'=00(\d)=', raw)

            i = 1
            while i < len(parts) - 1:
                ep_num = parts[i].strip()
                ep_content = parts[i + 1]
                i += 2

                def get_field(content, field_name, next_fields):
                    for nf in next_fields:
                        pattern = f"{field_name}[:\\s]*(.*?)(?={nf})"
                        m = _re.search(pattern, content, _re.DOTALL)
                        if m:
                            return m.group(1).strip()
                    pattern = f"{field_name}[:\\s]*(.*)"
                    m = _re.search(pattern, content, _re.DOTALL)
                    if m:
                        return m.group(1).strip()
                    return ""

                title = clean_special_shorts(get_field(ep_content, "제목", ["상단제목", "설명글", "태그", "순수 대본"]))
                top1 = clean_special_shorts(get_field(ep_content, "상단제목 첫째 줄", ["상단제목 둘째 줄", "설명글", "태그"]))
                top2 = clean_special_shorts(get_field(ep_content, "상단제목 둘째 줄", ["설명글", "태그", "순수 대본"]))
                desc = clean_special_shorts(get_field(ep_content, "설명글", ["태그", "순수 대본"]))
                tags = clean_special_shorts(get_field(ep_content, "태그", ["순수 대본", "=장면"]))

                script_match = _re.search(r'순수 대본[:\s]*(.*?)(?==장면)', ep_content, _re.DOTALL)
                script = clean_special_shorts(script_match.group(1)) if script_match else ""

                scenes = []
                scene_blocks = _re.findall(r'=장면\d+=\s*대사[:\s]*(.*?)프롬프트[:\s]*(.*?)(?==장면|\Z)', ep_content, _re.DOTALL)
                for sb in scene_blocks:
                    line_text = clean_special_shorts(sb[0])
                    prompt_text = sb[1].strip()
                    scenes.append({"대사": line_text, "프롬프트": prompt_text})

                shorts_list.append({
                    "번호": ep_num,
                    "제목": title,
                    "상단1": top1,
                    "상단2": top2,
                    "설명글": desc,
                    "태그": tags,
                    "대본": script,
                    "장면": scenes
                })

            st.session_state.shorts_list = shorts_list

            for idx, ep in enumerate(shorts_list):
                st.markdown("---")
                st.markdown(f"### 쇼츠 {ep['번호']}편")

                st.markdown("**제목**")
                st.code(ep["제목"], language=None)

                st.markdown("**상단제목**")
                st.code(f"{ep['상단1']}\n{ep['상단2']}", language=None)

                st.markdown("**설명글**")
                st.code(ep["설명글"], language=None)

                st.markdown("**태그**")
                st.code(ep["태그"], language=None)

                st.markdown("**대본**")
                st.code(ep["대본"], language=None)

                if ep["장면"]:
                    with st.expander(f"장면 프롬프트 ({len(ep['장면'])}개)", expanded=False):
                        for si, scene in enumerate(ep["장면"]):
                            st.markdown(f"**장면 {si+1}**")
                            st.code(f"대사: {scene['대사']}\n프롬프트: {scene['프롬프트']}", language=None)

            all_sentences = []
            for ep in shorts_list:
                sents = [s.strip() for s in ep["대본"].split(".") if s.strip()]
                all_sentences.extend(sents)
            st.session_state.shorts_sentences = all_sentences
            st.caption(f"전체 쇼츠 문장 수: {len(all_sentences)}")



# ═══ 탭4: 이미지 생성 (Skywork) ═══
with tab4:
    st.header("이미지 생성 (Skywork AI)")
    img_tab_l, img_tab_s = st.tabs(["롱폼 (16:9)", "쇼츠 (9:16)"])

    with img_tab_l:
        st.subheader("롱폼 이미지")
        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', body) if s.strip()]
            st.info(f"대본 문장 수: {len(sentences)}개")

            num_images = st.number_input("생성할 이미지 수", 1, min(30, len(sentences)), min(10, len(sentences)), key="lf_img_count")
            interval = max(1, len(sentences) // num_images)

            if st.button("롱폼 이미지 프롬프트 생성", type="primary", use_container_width=True):
                selected_sentences = sentences[::interval][:num_images]
                prompt = f"""다음 문장들을 각각 시네마틱 이미지 프롬프트로 변환해줘. 16:9 가로 비율.
각 줄에 프롬프트만 출력. 번호 없이.
영어로 작성. cinematic, detailed, professional 스타일.

문장들:
""" + "\n".join(f"- {s}" for s in selected_sentences)
                with st.spinner("프롬프트 생성 중..."):
                    raw = safe_generate(prompt)
                    if raw:
                        prompts = [line.strip() for line in raw.strip().split("\n") if line.strip() and not line.strip().startswith("[")]
                        st.session_state.generated_images_longform = [{"prompt": p, "url": None, "idx": i} for i, p in enumerate(prompts)]

            if st.session_state.generated_images_longform:
                for i, img_data in enumerate(st.session_state.generated_images_longform):
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.text_area(f"프롬프트 {i+1}", img_data["prompt"], height=80, key=f"lf_prompt_{i}")
                        with col2:
                            if st.button("생성", key=f"lf_gen_{i}"):
                                with st.spinner(f"이미지 {i+1} 생성 중..."):
                                    url, err = safe_generate_image(img_data["prompt"], "16:9")
                                    if url:
                                        st.session_state.generated_images_longform[i]["url"] = url
                                        st.rerun()
                                    else:
                                        st.error(f"실패: {err}")
                        if img_data.get("url"):
                            st.image(img_data["url"], use_container_width=True)

                if st.button("전체 이미지 일괄 생성", use_container_width=True):
                    progress = st.progress(0)
                    for i, img_data in enumerate(st.session_state.generated_images_longform):
                        if not img_data.get("url"):
                            url, err = safe_generate_image(img_data["prompt"], "16:9")
                            if url:
                                st.session_state.generated_images_longform[i]["url"] = url
                            time.sleep(1)
                        progress.progress((i + 1) / len(st.session_state.generated_images_longform))
                    st.rerun()
        else:
            st.info("먼저 롱폼 대본을 생성하세요.")

    with img_tab_s:
        st.subheader("쇼츠 이미지")
        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                ep_num = ep["num"]
                st.markdown(f"#### {ep_num}편: {ep['title']}")

                if ep.get("scenes"):
                    if ep_num not in st.session_state.generated_images_shorts:
                        st.session_state.generated_images_shorts[ep_num] = []

                    if st.button(f"{ep_num}편 전체 이미지 생성", key=f"shorts_gen_all_{ep_num}"):
                        progress = st.progress(0)
                        results = []
                        for j, scene in enumerate(ep["scenes"]):
                            url, err = safe_generate_image(scene["prompt"], "9:16")
                            results.append({"prompt": scene["prompt"], "dialogue": scene["dialogue"], "url": url, "error": err})
                            progress.progress((j + 1) / len(ep["scenes"]))
                            time.sleep(1)
                        st.session_state.generated_images_shorts[ep_num] = results
                        st.rerun()

                    if st.session_state.generated_images_shorts.get(ep_num):
                        cols = st.columns(min(4, len(st.session_state.generated_images_shorts[ep_num])))
                        for j, img in enumerate(st.session_state.generated_images_shorts[ep_num]):
                            with cols[j % len(cols)]:
                                if img.get("url"):
                                    st.image(img["url"], caption=f"장면{j+1}", use_container_width=True)
                                else:
                                    st.warning(f"장면{j+1} 실패")
                                st.caption(img.get("dialogue", "")[:30])
                st.divider()
        else:
            st.info("먼저 쇼츠 대본을 생성하세요.")


# ═══ 탭5: 영상 변환 (Kie AI + 자동 효과) ═══
with tab5:
    st.header("영상 변환")

    AUTO_EFFECTS_CYCLE = [
        "줌인 (느린)", "줌아웃 (느린)", "좌→우 패닝", "우→좌 패닝",
        "상→하 패닝", "하→상 패닝", "켄번스 좌상→우하", "켄번스 우상→좌하",
        "켄번스 중앙→좌", "켄번스 중앙→우", "줌인 (빠른)", "줌아웃 (빠른)",
        "흔들림 (약한)", "펄스 줌",
    ]

    def get_auto_effect(idx):
        return AUTO_EFFECTS_CYCLE[idx % len(AUTO_EFFECTS_CYCLE)]

    vid_tab_l, vid_tab_s = st.tabs(["롱폼 영상", "쇼츠 영상"])

    with vid_tab_l:
        st.subheader("롱폼 이미지 → 영상")
        if st.session_state.generated_images_longform:
            images_with_url = [img for img in st.session_state.generated_images_longform if img.get("url")]
            st.info(f"생성된 이미지: {len(images_with_url)}개")

            st.markdown("**일괄 효과 설정**")
            bc1, bc2 = st.columns([3, 1])
            with bc1:
                bulk_effect = st.selectbox("일괄 적용할 효과", list(CAMERA_EFFECTS.keys()), key="lf_bulk_effect")
            with bc2:
                if st.button("전체 일괄 적용", key="lf_apply_bulk", use_container_width=True):
                    for i in range(len(images_with_url)):
                        st.session_state.video_effects_longform[f"lf_{i}"] = bulk_effect
                    st.rerun()

            if st.button("자동 효과 할당 (줌인/줌아웃 순환)", use_container_width=True):
                for i in range(len(images_with_url)):
                    st.session_state.video_effects_longform[f"lf_{i}"] = get_auto_effect(i)
                st.rerun()

            st.divider()

            for i, img in enumerate(images_with_url):
                eff_key = f"lf_{i}"
                # 효과 미지정이면 자동 할당
                if eff_key not in st.session_state.video_effects_longform:
                    st.session_state.video_effects_longform[eff_key] = get_auto_effect(i)

                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        if img.get("url"):
                            st.image(img["url"], width=200)
                    with c2:
                        current_eff = st.session_state.video_effects_longform.get(eff_key, "줌인 (느린)")
                        eff_list = list(CAMERA_EFFECTS.keys())
                        eff_idx = eff_list.index(current_eff) if current_eff in eff_list else 1
                        eff = st.selectbox("효과", eff_list, index=eff_idx, key=f"lf_eff_{i}")
                        st.session_state.video_effects_longform[eff_key] = eff
                        st.markdown(build_effect_preview_html(eff, img.get("url"), "16:9"), unsafe_allow_html=True)
                    with c3:
                        # Runway 영상 변환 (클릭한 것만)
                        if st.button("Runway 영상변환", key=f"lf_conv_{i}"):
                            with st.spinner("Kie AI 영상 변환 중..."):
                                try:
                                    task_id, err = api.kie.image_to_video(img["url"], prompt=f"{eff} cinematic movement", duration=5)
                                    if task_id:
                                        st.session_state.video_results_longform[eff_key] = {"task_id": task_id, "status": "processing", "type": "runway"}
                                        st.success(f"변환 시작 (태스크: {task_id[:8]}...)")
                                    else:
                                        st.error(f"실패: {err}")
                                except Exception as e:
                                    st.error(str(e))

                        st.caption(f"자동효과: {eff}")

                    # 상태 확인
                    vr = st.session_state.video_results_longform.get(eff_key)
                    if vr:
                        if vr.get("status") == "processing":
                            if st.button("상태 확인", key=f"lf_check_{i}"):
                                state, url, err = api.kie.check_task(vr["task_id"])
                                if state == "success" and url:
                                    st.session_state.video_results_longform[eff_key]["status"] = "done"
                                    st.session_state.video_results_longform[eff_key]["url"] = url
                                    st.rerun()
                                elif state == "failed":
                                    st.error("변환 실패")
                                else:
                                    st.info(f"진행 중... ({state})")
                        elif vr.get("url"):
                            st.video(vr["url"])
                            st.caption("Runway 영상 생성 완료")
        else:
            st.info("먼저 이미지를 생성하세요.")

    with vid_tab_s:
        st.subheader("쇼츠 이미지 → 영상")
        if st.session_state.generated_images_shorts:
            for ep_num, images in st.session_state.generated_images_shorts.items():
                st.markdown(f"#### {ep_num}편")
                imgs_ok = [img for img in images if img.get("url")]
                if not imgs_ok:
                    st.warning("이미지 없음")
                    continue

                # 자동 효과 일괄 할당 버튼
                if st.button(f"{ep_num}편 자동 효과 할당", key=f"s_auto_eff_{ep_num}"):
                    for j in range(len(imgs_ok)):
                        st.session_state.video_effects_shorts[f"s{ep_num}_{j}"] = get_auto_effect(j)
                    st.rerun()

                for j, img in enumerate(imgs_ok):
                    eff_key = f"s{ep_num}_{j}"
                    # 효과 미지정이면 자동 할당
                    if eff_key not in st.session_state.video_effects_shorts:
                        st.session_state.video_effects_shorts[eff_key] = get_auto_effect(j)

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 2, 1])
                        with c1:
                            st.image(img["url"], width=120)
                            st.caption(img.get("dialogue", "")[:25])
                        with c2:
                            current_eff = st.session_state.video_effects_shorts.get(eff_key, "줌인 (느린)")
                            eff_list = list(CAMERA_EFFECTS.keys())
                            eff_idx = eff_list.index(current_eff) if current_eff in eff_list else 1
                            eff = st.selectbox("효과", eff_list, index=eff_idx, key=f"seff_{eff_key}")
                            st.session_state.video_effects_shorts[eff_key] = eff
                            st.markdown(build_effect_preview_html(eff, img.get("url"), "9:16"), unsafe_allow_html=True)
                        with c3:
                            # Runway 영상 변환 (클릭한 것만)
                            if st.button("Runway 변환", key=f"s_conv_{eff_key}"):
                                with st.spinner("영상 변환 중..."):
                                    try:
                                        task_id, err = api.kie.image_to_video(img["url"], prompt=f"{eff} cinematic movement", duration=5)
                                        if task_id:
                                            if ep_num not in st.session_state.video_results_shorts:
                                                st.session_state.video_results_shorts[ep_num] = {}
                                            st.session_state.video_results_shorts[ep_num][str(j)] = {"task_id": task_id, "status": "processing", "type": "runway"}
                                            st.success(f"변환 시작")
                                        else:
                                            st.error(f"실패: {err}")
                                    except Exception as e:
                                        st.error(str(e))

                            st.caption(f"자동: {eff}")

                        # 상태 확인
                        vr = (st.session_state.video_results_shorts.get(ep_num) or {}).get(str(j))
                        if vr:
                            if vr.get("status") == "processing":
                                if st.button("상태확인", key=f"s_chk_{eff_key}"):
                                    state, url, err = api.kie.check_task(vr["task_id"])
                                    if state == "success" and url:
                                        st.session_state.video_results_shorts[ep_num][str(j)]["status"] = "done"
                                        st.session_state.video_results_shorts[ep_num][str(j)]["url"] = url
                                        st.rerun()
                                    elif state == "failed":
                                        st.error("변환 실패")
                                    else:
                                        st.info(f"진행 중... ({state})")
                            elif vr.get("url"):
                                st.video(vr["url"])
                st.divider()
        else:
            st.info("먼저 쇼츠 이미지를 생성하세요.")


# ═══ 탭6: 음성 합성 (Inworld TTS) ═══
with tab6:
    st.header("음성 합성 (Inworld TTS)")

    # ── 공통 음성 설정 ──
    st.markdown("---")
    st.subheader("음성 설정")

    KOREAN_VOICES = {
        "현우 (젊은 남성)": "Hyunwoo",
        "민지 (활발한 여성)": "Minji",
        "서준 (성숙한 남성)": "Seojun",
        "윤아 (차분한 여성)": "Yoona",
    }

    TTS_MODELS = {
        "TTS 1.5 Max (고품질)": "inworld-tts-1.5-max",
        "TTS 1.5 Mini (빠른속도)": "inworld-tts-1.5-mini",
    }

    vc1, vc2, vc3, vc4 = st.columns(4)
    with vc1:
        voice_display = st.selectbox("음성 선택", list(KOREAN_VOICES.keys()), index=0, key="tts_voice_select")
        selected_voice_id = KOREAN_VOICES[voice_display]
    with vc2:
        model_display = st.selectbox("모델", list(TTS_MODELS.keys()), index=0, key="tts_model_select")
        selected_model_id = TTS_MODELS[model_display]
    with vc3:
        speaking_rate = st.slider("말하기 속도", 0.5, 2.0, 1.0, 0.1, key="tts_speed")
    with vc4:
        temperature = st.slider("표현력 (온도)", 0.1, 2.0, 1.0, 0.1, key="tts_temp")

    # 음성 카드 미리보기
    voice_info = {
        "Hyunwoo": {"name": "현우", "desc": "젊은 성인 남성 목소리", "icon": "🧑"},
        "Minji": {"name": "민지", "desc": "활기차고 친근한 젊은 여성 목소리", "icon": "👩"},
        "Seojun": {"name": "서준", "desc": "깊고 성숙한 남성 목소리", "icon": "👨"},
        "Yoona": {"name": "윤아", "desc": "부드럽고 차분한 여성 목소리", "icon": "👩‍🦰"},
    }
    vi = voice_info.get(selected_voice_id, {})
    st.markdown(f"""<div style="background:linear-gradient(135deg,#1a1a3e,#2a1a4e);border:1px solid #444;border-radius:12px;padding:16px;margin:10px 0;display:flex;align-items:center;gap:16px;">
<div style="font-size:48px;">{vi.get('icon','🎙️')}</div>
<div>
<div style="font-size:18px;font-weight:bold;color:#e0e0e0;">{vi.get('name','')} ({selected_voice_id})</div>
<div style="font-size:13px;color:#999;">{vi.get('desc','')}</div>
<div style="font-size:11px;color:#666;margin-top:4px;">모델: {model_display} | 속도: {speaking_rate}x | 온도: {temperature}</div>
</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    tts_tab_l, tts_tab_s = st.tabs(["롱폼 음성", "쇼츠 음성"])

    with tts_tab_l:
        st.subheader("롱폼 TTS")
        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            st.text_area("대본 미리보기", body[:500] + "..." if len(body) > 500 else body, height=150, disabled=True)
            st.caption(f"전체 {len(body)}자 | 2000자 제한으로 앞부분만 합성됩니다")

            if st.button("롱폼 음성 생성", type="primary", use_container_width=True):
                with st.spinner(f"음성 생성 중... ({vi.get('name','')}, {model_display})"):
                    try:
                        audio, timestamps, err = api.inworld.synthesize(
                            text=body[:2000],
                            voice_id=selected_voice_id,
                            model_id=selected_model_id,
                            speaking_rate=speaking_rate,
                            temperature=temperature,
                        )
                        if audio:
                            st.session_state.tts_longform_audio = audio
                            ts = parse_tts_timestamps(timestamps, body)
                            st.session_state.tts_longform_timestamps = ts
                            st.session_state.tts_longform_srt = timestamps_to_srt(ts)
                            st.success(f"음성 생성 완료 ({vi.get('name','')})")
                        else:
                            st.error(f"TTS 실패: {err}")
                    except Exception as e:
                        st.error(f"TTS 오류: {str(e)}")

            if st.session_state.tts_longform_audio:
                st.audio(st.session_state.tts_longform_audio, format="audio/mp3")
                if st.session_state.tts_longform_timestamps:
                    st.markdown(build_sync_timeline_html(st.session_state.tts_longform_timestamps), unsafe_allow_html=True)
                if st.session_state.tts_longform_srt:
                    with st.expander("SRT 자막"):
                        st.code(st.session_state.tts_longform_srt)
                    st.download_button("SRT 다운로드", st.session_state.tts_longform_srt, "longform.srt")
                st.download_button("음성 다운로드", st.session_state.tts_longform_audio, "longform_tts.mp3")
        else:
            st.info("먼저 롱폼 대본을 생성하세요.")

    with tts_tab_s:
        st.subheader("쇼츠 TTS")
        if st.session_state.shorts_data:
            # 전체 일괄 생성
            if st.button("쇼츠 전편 음성 일괄 생성", use_container_width=True):
                progress = st.progress(0)
                total = len(st.session_state.shorts_data)
                for idx, ep in enumerate(st.session_state.shorts_data):
                    ep_num = ep["num"]
                    script = ep.get("script", "")
                    if script and ep_num not in st.session_state.tts_shorts_audio:
                        try:
                            audio, timestamps, err = api.inworld.synthesize(
                                text=script,
                                voice_id=selected_voice_id,
                                model_id=selected_model_id,
                                speaking_rate=speaking_rate,
                                temperature=temperature,
                            )
                            if audio:
                                st.session_state.tts_shorts_audio[ep_num] = audio
                                ts = parse_tts_timestamps(timestamps, script)
                                st.session_state.tts_shorts_timestamps[ep_num] = ts
                                st.session_state.tts_shorts_srt[ep_num] = timestamps_to_srt(ts)
                        except Exception:
                            pass
                    progress.progress((idx + 1) / total)
                    time.sleep(0.5)
                st.rerun()

            st.divider()

            for ep in st.session_state.shorts_data:
                ep_num = ep["num"]
                with st.container(border=True):
                    ec1, ec2 = st.columns([3, 1])
                    with ec1:
                        st.markdown(f"**{ep_num}편: {ep['title']}**")
                        script = ep.get("script", "")
                        if script:
                            st.caption(f"{len(script)}자 | 약 {len(script)//7}초")
                    with ec2:
                        has_audio = ep_num in st.session_state.tts_shorts_audio
                        if has_audio:
                            st.markdown("✅ 생성됨")
                        else:
                            if st.button(f"음성 생성", key=f"tts_s_{ep_num}"):
                                with st.spinner(f"{ep_num}편 음성 생성 중... ({vi.get('name','')})"):
                                    try:
                                        audio, timestamps, err = api.inworld.synthesize(
                                            text=script,
                                            voice_id=selected_voice_id,
                                            model_id=selected_model_id,
                                            speaking_rate=speaking_rate,
                                            temperature=temperature,
                                        )
                                        if audio:
                                            st.session_state.tts_shorts_audio[ep_num] = audio
                                            ts = parse_tts_timestamps(timestamps, script)
                                            st.session_state.tts_shorts_timestamps[ep_num] = ts
                                            st.session_state.tts_shorts_srt[ep_num] = timestamps_to_srt(ts)
                                            st.rerun()
                                        else:
                                            st.error(f"실패: {err}")
                                    except Exception as e:
                                        st.error(str(e))

                    if st.session_state.tts_shorts_audio.get(ep_num):
                        st.audio(st.session_state.tts_shorts_audio[ep_num], format="audio/mp3")
                        if st.session_state.tts_shorts_timestamps.get(ep_num):
                            st.markdown(build_sync_timeline_html(st.session_state.tts_shorts_timestamps[ep_num]), unsafe_allow_html=True)
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            st.download_button(f"{ep_num}편 음성", st.session_state.tts_shorts_audio[ep_num],
                                              f"shorts_{ep_num}_tts.mp3", key=f"dl_audio_{ep_num}")
                        with dc2:
                            if st.session_state.tts_shorts_srt.get(ep_num):
                                st.download_button(f"{ep_num}편 SRT", st.session_state.tts_shorts_srt[ep_num],
                                                  f"shorts_{ep_num}.srt", key=f"dl_srt_{ep_num}")
        else:
            st.info("먼저 쇼츠 대본을 생성하세요.")


# ═══ 탭7: 자막 설정 ═══
with tab7:
    st.header("자막 설정")
    sub_tab_l, sub_tab_s = st.tabs(["롱폼 (16:9)", "쇼츠 (9:16)"])

    with sub_tab_l:
        col_set, col_prev = st.columns([1, 1])
        with col_set:
            st.session_state.sub_settings_longform = subtitle_settings_ui("lf_sub", "16:9")
        with col_prev:
            st.markdown("**미리보기**")
            preview_text = "여기에 자막이 표시됩니다"
            if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
                sentences = [s.strip() for s in st.session_state.longform_metadata["body"].split(".") if s.strip()]
                if sentences:
                    preview_text = sentences[0][:30]
            st.markdown(build_subtitle_preview_html(st.session_state.sub_settings_longform, preview_text, "16:9"), unsafe_allow_html=True)

            if st.button("설정 저장 (롱폼)", use_container_width=True):
                st.success("저장됨")
            st.download_button("설정 JSON 다운로드",
                              json.dumps(st.session_state.sub_settings_longform, ensure_ascii=False, indent=2),
                              "subtitle_longform.json")

    with sub_tab_s:
        col_set2, col_prev2 = st.columns([1, 1])
        with col_set2:
            st.session_state.sub_settings_shorts = subtitle_settings_ui("sh_sub", "9:16")
        with col_prev2:
            st.markdown("**미리보기**")
            preview_text2 = "쇼츠 자막 미리보기"
            if st.session_state.shorts_data:
                script = st.session_state.shorts_data[0].get("script", "")
                if script:
                    preview_text2 = script.split(".")[0][:25] if "." in script else script[:25]
            st.markdown(build_subtitle_preview_html(st.session_state.sub_settings_shorts, preview_text2, "9:16"), unsafe_allow_html=True)

            if st.button("설정 저장 (쇼츠)", use_container_width=True):
                st.success("저장됨")
            st.download_button("설정 JSON 다운로드",
                              json.dumps(st.session_state.sub_settings_shorts, ensure_ascii=False, indent=2),
                              "subtitle_shorts.json")


# ═══ 탭8: 최종 합치기 ═══
with tab8:
    st.header("최종 합치기")
    st.info("Streamlit Cloud에서는 FFmpeg를 직접 실행할 수 없습니다. 아래 명령어를 로컬에서 실행하세요.")

    merge_tab_l, merge_tab_s = st.tabs(["롱폼 합치기", "쇼츠 합치기"])

    with merge_tab_l:
        st.subheader("롱폼 FFmpeg 명령어")
        lf_images = [img for img in st.session_state.generated_images_longform if img.get("url")]
        has_audio = st.session_state.tts_longform_audio is not None
        has_srt = bool(st.session_state.tts_longform_srt)

        if lf_images:
            st.success(f"이미지: {len(lf_images)}개 | 음성: {'있음' if has_audio else '없음'} | 자막: {'있음' if has_srt else '없음'}")

            sub_s = st.session_state.sub_settings_longform
            font_name = sub_s.get("font", "Noto Sans KR")
            font_size = sub_s.get("size", 48)
            fc = sub_s.get("color", "#FFFFFF").replace("#", "&H00") if sub_s.get("color") else "&H00FFFFFF"

            for i, img in enumerate(lf_images):
                eff_name = st.session_state.video_effects_longform.get(f"lf_{i}", "줌인 (느린)")
                zp = effect_to_ffmpeg(eff_name)
                cmd = f'ffmpeg -loop 1 -i scene_{i+1:03d}.jpg -vf "{zp}" -t 5 -pix_fmt yuv420p scene_{i+1:03d}.mp4'
                st.code(cmd, language="bash")

            concat_list = "\n".join(f"file 'scene_{i+1:03d}.mp4'" for i in range(len(lf_images)))
            st.code(f"# concat.txt 내용:\n{concat_list}", language="text")
            st.code("ffmpeg -f concat -safe 0 -i concat.txt -c copy merged.mp4", language="bash")

            if has_audio and has_srt:
                st.code('ffmpeg -i merged.mp4 -i audio.mp3 -vf "subtitles=subtitle.srt" -c:a aac -shortest final.mp4', language="bash")
        else:
            st.warning("이미지, 음성, 자막을 먼저 생성하세요.")

    with merge_tab_s:
        st.subheader("쇼츠 FFmpeg 명령어")
        if st.session_state.generated_images_shorts:
            for ep_num, images in st.session_state.generated_images_shorts.items():
                with st.expander(f"{ep_num}편"):
                    imgs_ok = [img for img in images if img.get("url")]
                    for j, img in enumerate(imgs_ok):
                        eff_name = st.session_state.video_effects_shorts.get(f"s{ep_num}_{j}", "줌인 (느린)")
                        zp = effect_to_ffmpeg(eff_name, w=1080, h=1920)
                        cmd = f'ffmpeg -loop 1 -i ep{ep_num}_scene{j+1:03d}.jpg -vf "{zp}" -t 4 -pix_fmt yuv420p ep{ep_num}_scene{j+1:03d}.mp4'
                        st.code(cmd, language="bash")
        else:
            st.warning("쇼츠 이미지를 먼저 생성하세요.")

    # ── 체크리스트 ──
    st.divider()
    st.subheader("진행 상황")
    checks = {
        "주제 선택": bool(st.session_state.selected_topic),
        "롱폼 대본": bool(st.session_state.longform_metadata),
        "쇼츠 대본": bool(st.session_state.shorts_data),
        "롱폼 이미지": bool([i for i in st.session_state.generated_images_longform if i.get("url")]),
        "쇼츠 이미지": bool(st.session_state.generated_images_shorts),
        "롱폼 음성": st.session_state.tts_longform_audio is not None,
        "쇼츠 음성": bool(st.session_state.tts_shorts_audio),
        "자막 설정": bool(st.session_state.sub_settings_longform) or bool(st.session_state.sub_settings_shorts),
    }
    for label, done in checks.items():
        st.checkbox(label, value=done, disabled=True, key=f"check_{label}")
