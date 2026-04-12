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

    # 채널 카테고리
    categories = ["경제/사회", "부동산", "주식/투자", "IT/기술", "건강/의학", "교육", "정치", "국제", "문화/예술", "법률", "환경", "스포츠", "라이프스타일", "역사", "직접 입력"]
    cat_col, kw_col, cnt_col = st.columns([2, 3, 1])
    with cat_col:
        selected_cat = st.selectbox("채널 카테고리", categories, index=0, key="channel_cat_select")
    with kw_col:
        keyword = st.text_input("키워드", "시니어", key="search_keyword")
    with cnt_col:
        news_count = st.number_input("뉴스 수", 3, 20, 10, key="news_count")

    # 키워드 추천
    kw_c1, kw_c2 = st.columns([1, 1])
    with kw_c1:
        if st.button("키워드 추천 받기", use_container_width=True):
            if not api:
                st.error("API 미연결")
            else:
                with st.spinner("키워드 분석 중..."):
                    cat = selected_cat if selected_cat != "직접 입력" else keyword
                    kw_prompt = f"'{cat}' 카테고리의 유튜브 트렌드 키워드 20개를 추천해줘. 한 줄에 하나씩, 번호 없이 키워드만 출력해."
                    kw_raw = safe_generate(kw_prompt)
                    if kw_raw:
                        kws = [line.strip().strip("-").strip("•").strip() for line in kw_raw.strip().split("\n") if line.strip() and not line.strip().startswith("[")]
                        st.session_state.recommended_keywords = kws[:20]

    if st.session_state.recommended_keywords:
        st.markdown("**추천 키워드** (클릭하면 검색어에 적용)")
        cols = st.columns(5)
        for idx, kw in enumerate(st.session_state.recommended_keywords):
            with cols[idx % 5]:
                if st.button(kw, key=f"kw_{idx}", use_container_width=True):
                    st.session_state.search_keyword = kw
                    st.rerun()

    st.divider()

    if st.button("떡상 주제 추천 받기", type="primary", use_container_width=True):
        if not api:
            st.error("API 미연결")
        else:
            with st.spinner("분석 중..."):
                news = safe_naver_search(keyword, news_count)
                nt = ""
                for item in news[:news_count]:
                    t = re.sub(r'<[^>]+>', '', str(item.get("title", "") if isinstance(item, dict) else item))
                    d = re.sub(r'<[^>]+>', '', str(item.get("description", "") if isinstance(item, dict) else ""))
                    nt += f"- {t}: {d}\n"
                with st.expander("뉴스 (디버그)"):
                    st.text(nt or "(없음)")

                prompt = f"""아래 뉴스를 분석해서 유튜브 떡상 주제 10개를 추천해줘.
카테고리: {selected_cat}
키워드: {keyword}
뉴스:
{nt or '(최신 뉴스 없음)'}

반드시 정확히 10개를 아래 형식으로 출력해:
1번|제목: 제목내용|확률: 높음/중간/낮음|출처: 출처내용|대안: 대안제목|태그: 태그1,태그2,태그3
2번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ...
(10번까지)"""

                raw_str = safe_generate(prompt)

                with st.expander("AI 응답"):
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
                            # 번호. 제목 형식 대응
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
    st.header("롱폼 대본 (약 30분)")
    if st.session_state.selected_topic and not st.session_state.get("longform_topic"):
        st.session_state["longform_topic"] = st.session_state.selected_topic
    topic_long = st.text_input("영상 주제", key="longform_topic")

    if st.button("롱폼 대본 생성", type="primary", use_container_width=True):
        if not topic_long.strip():
            st.warning("주제를 입력하세요")
        elif not api:
            st.error("API가 연결되지 않았습니다")
        else:
            with st.spinner("대본 생성 중 (1~3분 소요)..."):
                try:
                    from prompts.senior_longform import get_prompt
                    prompt = get_prompt(topic_long.strip())
                except Exception:
                    prompt = f"'{topic_long.strip()}' 주제로 30분 분량 유튜브 롱폼 대본을 작성해줘.\n\n제목:\n태그:\n설명글:\n---대본시작---\n(본문)\n---대본끝---"

                raw_str = safe_generate(prompt)

                if raw_str:
                    st.session_state.longform_script = raw_str
                    meta = {}
                    for f, p in [("title", r'제목:\s*(.+)'), ("tags", r'태그:\s*(.+)'), ("description", r'설명글:\s*(.+)')]:
                        m = re.search(p, raw_str)
                        if m:
                            meta[f] = m.group(1).strip()
                    bm = re.search(r'---대본시작---(.+?)---대본끝---', raw_str, re.DOTALL)
                    meta["body"] = bm.group(1).strip() if bm else raw_str
                    st.session_state.longform_metadata = meta
                else:
                    st.error("대본 생성 실패: 응답이 비어있습니다.")

    if st.session_state.longform_metadata:
        meta = st.session_state.longform_metadata
        with st.container(border=True):
            st.subheader(meta.get("title", "제목 없음"))
            if meta.get("tags"):
                st.caption(f"태그: {meta['tags']}")
            if meta.get("description"):
                st.info(meta["description"])
        with st.expander("대본 전문", expanded=True):
            body = meta.get("body", "")
            st.text_area("대본", body, height=500, key="lb_disp")
            st.caption(f"{len(body)}자 | 약 {len(body)//350}분")
        st.download_button("다운로드", st.session_state.longform_script,
                           f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")


# ═══ 탭3: 쇼츠 대본 ═══
with tab3:
    st.header("쇼츠 대본 (3편 / 40초)")
    if st.session_state.selected_topic and not st.session_state.get("shorts_topic"):
        st.session_state["shorts_topic"] = st.session_state.selected_topic
    topic_shorts = st.text_input("쇼츠 주제", key="shorts_topic")

    if st.button("쇼츠 3편 생성", type="primary", use_container_width=True):
        if not topic_shorts.strip():
            st.warning("주제를 입력하세요")
        elif not api:
            st.error("API가 연결되지 않았습니다")
        else:
            with st.spinner("쇼츠 3편 생성 중..."):
                prompt = f"""유튜브 쇼츠 대본 작가야. 대주제: '{topic_shorts.strip()}'
3편 세트를 만들어줘. 각 편은 8~12문장, 40초 이내 분량.
인사/구독/좋아요 금지. 열린고리 기법 사용. 근데/그래서/결국 접속사. 습니다+까요 혼합체.
이미지프롬프트: SD 2D anime style로 시작. 9:16 비율. 장면 수 = 문장 수.

반드시 아래 형식으로만 출력해:
=001=
제목: (50자 이내)
상단제목첫째줄: (15자 이내)
상단제목둘째줄: (15자 이내)
설명글: (200자, 해시태그 3~5개 포함)
태그: (쉼표 구분 15~20개)
순수대본: (문장만 나열. 마침표로 구분)
=장면001=
대사: (첫 번째 문장)
프롬프트: SD 2D anime style, (영어 장면 묘사), 9:16 vertical aspect ratio
=장면002=
대사: (두 번째 문장)
프롬프트: SD 2D anime style, (영어 장면 묘사), 9:16 vertical aspect ratio
(문장 수만큼 반복)
=002=
(동일 형식)
=003=
(동일 형식)"""

                raw_str = safe_generate(prompt)

                if raw_str:
                    st.session_state.shorts_raw = raw_str
                    episodes = []
                    blocks = re.split(r'=0*(\d+)=', raw_str)
                    i = 1
                    while i < len(blocks) - 1:
                        num_str = blocks[i].strip()
                        content = blocks[i + 1].strip()
                        ep = {"num": num_str, "raw": content}
                        for f, p in [("title", r'제목:\s*(.+)'), ("top_line1", r'상단제목첫째줄:\s*(.+)'),
                                     ("top_line2", r'상단제목둘째줄:\s*(.+)'), ("tags", r'태그:\s*(.+)')]:
                            m = re.search(p, content)
                            ep[f] = m.group(1).strip() if m else ""
                        if not ep.get("title"):
                            ep["title"] = f"쇼츠 {num_str}편"
                        m = re.search(r'설명글:\s*(.+?)(?=\n태그:|\n=장면|\n순수대본)', content, re.DOTALL)
                        ep["description"] = m.group(1).strip() if m else ""
                        m = re.search(r'순수대본:\s*(.+?)(?=\n=장면)', content, re.DOTALL)
                        ep["script"] = m.group(1).strip() if m else ""
                        scenes = re.findall(
                            r'=장면\d+=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?=\n=장면|\n=0|$)', content, re.DOTALL)
                        ep["scenes"] = [{"dialogue": d.strip(), "prompt": p.strip()} for d, p in scenes]
                        episodes.append(ep)
                        i += 2
                    st.session_state.shorts_data = episodes
                else:
                    st.error("쇼츠 생성 실패: 응답이 비어있습니다.")

    # ── 쇼츠 표시 (편별 카드) ──
    if st.session_state.shorts_data:
        with st.expander("AI 원본 응답"):
            st.code(st.session_state.shorts_raw)

        for ep in st.session_state.shorts_data:
            st.divider()
            with st.container(border=True):
                # 제목 + 상단제목
                st.markdown(f"### {ep['num']}편: {ep['title']}")
                if ep.get("top_line1") or ep.get("top_line2"):
                    st.markdown(f"""<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:10px 16px;border-radius:8px;text-align:center;font-weight:bold;margin:8px 0;">
{ep.get('top_line1','')}<br>{ep.get('top_line2','')}</div>""", unsafe_allow_html=True)

                # 태그
                if ep.get("tags"):
                    with st.container(border=True):
                        st.markdown('<span style="background:linear-gradient(90deg,#667eea,#764ba2);color:#fff;padding:4px 12px;border-radius:8px;font-size:0.85em;font-weight:bold;">태그</span>', unsafe_allow_html=True)
                        tags_html = ""
                        for tag in ep["tags"].split(","):
                            tag = tag.strip()
                            if tag:
                                tags_html += f'<span style="display:inline-block;background:#238636;color:#fff;padding:3px 10px;border-radius:12px;font-size:0.78em;margin:2px 3px;">{tag}</span>'
                        st.markdown(tags_html, unsafe_allow_html=True)

                # 설명글
                if ep.get("description"):
                    with st.container(border=True):
                        st.markdown('<span style="background:linear-gradient(90deg,#667eea,#764ba2);color:#fff;padding:4px 12px;border-radius:8px;font-size:0.85em;font-weight:bold;">설명글</span>', unsafe_allow_html=True)
                        st.markdown(f'<div style="background:#1e293b;border-radius:8px;padding:12px;color:#cbd5e1;font-size:0.9em;line-height:1.6;margin-top:6px;">{ep["description"]}</div>', unsafe_allow_html=True)

                # 대본
                with st.container(border=True):
                    st.markdown('<span style="background:linear-gradient(90deg,#667eea,#764ba2);color:#fff;padding:4px 12px;border-radius:8px;font-size:0.85em;font-weight:bold;">대본 (40초)</span>', unsafe_allow_html=True)
                    script_text = ep.get("script", "(없음)")
                    st.markdown(f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;font-size:0.95em;line-height:1.8;color:#e6edf3;white-space:pre-wrap;margin-top:6px;">{script_text}</div>', unsafe_allow_html=True)
                    if script_text:
                        st.caption(f"{len(script_text)}자")

                # 장면 프롬프트
                if ep.get("scenes"):
                    with st.expander(f"장면 프롬프트 ({len(ep['scenes'])}개)"):
                        for j, s in enumerate(ep["scenes"]):
                            st.markdown(f"**장면 {j+1}**")
                            st.write(f"대사: {s['dialogue']}")
                            st.code(s["prompt"], language="text")

        st.download_button("쇼츠 3편 다운로드", st.session_state.shorts_raw,
                           f"shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")


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


# ═══ 탭5: 영상 변환 (Kie AI) ═══
with tab5:
    st.header("영상 변환 (Kie AI)")
    vid_tab_l, vid_tab_s = st.tabs(["롱폼 영상", "쇼츠 영상"])

    with vid_tab_l:
        st.subheader("롱폼 이미지 → 영상")
        if st.session_state.generated_images_longform:
            images_with_url = [img for img in st.session_state.generated_images_longform if img.get("url")]
            st.info(f"생성된 이미지: {len(images_with_url)}개")

            # 효과 선택
            st.markdown("**카메라 효과 선택**")
            bulk_effect = st.selectbox("일괄 적용", list(CAMERA_EFFECTS.keys()), key="lf_bulk_effect")
            if st.button("전체 일괄 적용", key="lf_apply_bulk"):
                for i in range(len(images_with_url)):
                    st.session_state.video_effects_longform[f"lf_{i}"] = bulk_effect
                st.rerun()

            for i, img in enumerate(images_with_url):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        if img.get("url"):
                            st.image(img["url"], width=200)
                    with c2:
                        eff = st.selectbox("효과", list(CAMERA_EFFECTS.keys()),
                                          index=list(CAMERA_EFFECTS.keys()).index(st.session_state.video_effects_longform.get(f"lf_{i}", "줌인 (느린)")),
                                          key=f"lf_eff_{i}")
                        st.session_state.video_effects_longform[f"lf_{i}"] = eff
                        st.markdown(build_effect_preview_html(eff, img.get("url"), "16:9"), unsafe_allow_html=True)
                    with c3:
                        if st.button("변환", key=f"lf_conv_{i}"):
                            with st.spinner("변환 중..."):
                                try:
                                    task_id, err = api.kie.image_to_video(img["url"], prompt=eff, duration=5)
                                    if task_id:
                                        st.session_state.video_results_longform[f"lf_{i}"] = {"task_id": task_id, "status": "processing"}
                                        st.success(f"변환 시작 (태스크: {task_id[:8]}...)")
                                    else:
                                        st.error(f"실패: {err}")
                                except Exception as e:
                                    st.error(str(e))

                    # 상태 확인
                    vr = st.session_state.video_results_longform.get(f"lf_{i}")
                    if vr:
                        if vr.get("status") == "processing":
                            if st.button("상태 확인", key=f"lf_check_{i}"):
                                state, url, err = api.kie.check_task(vr["task_id"])
                                if state == "success" and url:
                                    st.session_state.video_results_longform[f"lf_{i}"]["status"] = "done"
                                    st.session_state.video_results_longform[f"lf_{i}"]["url"] = url
                                    st.rerun()
                                elif state == "failed":
                                    st.error("변환 실패")
                                else:
                                    st.info(f"진행 중... ({state})")
                        elif vr.get("url"):
                            st.video(vr["url"])
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
                for j, img in enumerate(imgs_ok):
                    with st.container(border=True):
                        c1, c2 = st.columns([2, 2])
                        with c1:
                            st.image(img["url"], width=150)
                        with c2:
                            eff_key = f"s{ep_num}_{j}"
                            eff = st.selectbox("효과", list(CAMERA_EFFECTS.keys()), key=f"seff_{eff_key}")
                            st.session_state.video_effects_shorts[eff_key] = eff
                            st.markdown(build_effect_preview_html(eff, img.get("url"), "9:16"), unsafe_allow_html=True)
                st.divider()
        else:
            st.info("먼저 쇼츠 이미지를 생성하세요.")


# ═══ 탭6: 음성 합성 (Inworld TTS) ═══
with tab6:
    st.header("음성 합성 (TTS)")
    tts_tab_l, tts_tab_s = st.tabs(["롱폼 음성", "쇼츠 음성"])

    with tts_tab_l:
        st.subheader("롱폼 TTS")
        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            st.text_area("대본 미리보기", body[:500] + "..." if len(body) > 500 else body, height=150, disabled=True)
            if st.button("롱폼 음성 생성", type="primary", use_container_width=True):
                with st.spinner("음성 생성 중..."):
                    try:
                        audio, timestamps, err = api.inworld.synthesize(body[:2000])
                        if audio:
                            st.session_state.tts_longform_audio = audio
                            ts = parse_tts_timestamps(timestamps, body)
                            st.session_state.tts_longform_timestamps = ts
                            st.session_state.tts_longform_srt = timestamps_to_srt(ts)
                            st.success("음성 생성 완료")
                        else:
                            st.error(f"TTS 실패: {err}")
                    except Exception as e:
                        st.error(str(e))

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
            for ep in st.session_state.shorts_data:
                ep_num = ep["num"]
                with st.container(border=True):
                    st.markdown(f"**{ep_num}편: {ep['title']}**")
                    script = ep.get("script", "")
                    if script:
                        st.caption(f"{len(script)}자")
                        if st.button(f"{ep_num}편 음성 생성", key=f"tts_s_{ep_num}"):
                            with st.spinner("생성 중..."):
                                try:
                                    audio, timestamps, err = api.inworld.synthesize(script)
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
