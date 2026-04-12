import streamlit as st
import json
import re
import os
import base64
import time
from datetime import datetime

st.set_page_config(page_title="시니어 콘텐츠 팩토리 올인원", layout="wide")

defaults = {
    "selected_topic": "",
    "topics_list": [],
    "longform_script": "",
    "longform_metadata": {},
    "shorts_data": [],
    "shorts_raw": "",
    "generated_images_longform": [],
    "generated_images_shorts": [],
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


def sync_topic():
    t = st.session_state.selected_topic
    if t:
        st.session_state["longform_topic"] = t
        st.session_state["shorts_topic"] = t


def safe_naver_search(keyword, count):
    raw_result = None
    try:
        raw_result = api.naver.search(keyword, display=count)
    except (TypeError, AttributeError):
        pass
    except Exception:
        pass
    if raw_result is None:
        try:
            raw_result = api.naver.search_trending_topics([keyword], count)
        except TypeError:
            try:
                raw_result = api.naver.search_trending_topics(keyword, count)
            except Exception:
                pass
        except Exception:
            pass
    if raw_result is None:
        try:
            raw_result = api.naver.search_news(keyword, count)
        except Exception:
            pass
    if raw_result is None:
        return []
    if isinstance(raw_result, dict):
        for key in ["items", "news", "results"]:
            if key in raw_result:
                news_items = raw_result[key]
                break
        else:
            news_items = [raw_result]
    elif isinstance(raw_result, list):
        news_items = raw_result
    elif isinstance(raw_result, str):
        news_items = [{"title": l, "description": ""} for l in raw_result.split("\n") if l.strip()]
    else:
        return []
    safe = []
    for item in news_items:
        if isinstance(item, dict):
            safe.append(item)
        elif isinstance(item, str):
            safe.append({"title": item, "description": ""})
        else:
            safe.append({"title": str(item), "description": ""})
    return safe


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


# ── 카메라 효과 목록 ──
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
    "켄번스 좌상→우하": {"desc": "줌인하면서 좌상단에서 우하단으로", "icon": "↘️🔍"},
    "켄번스 우상→좌하": {"desc": "줌인하면서 우상단에서 좌하단으로", "icon": "↙️🔍"},
    "켄번스 중앙→좌": {"desc": "줌인하면서 중앙에서 왼쪽으로", "icon": "⬅️🔍"},
    "켄번스 중앙→우": {"desc": "줌인하면서 중앙에서 오른쪽으로", "icon": "➡️🔍"},
    "흔들림 (약한)": {"desc": "미세한 떨림 효과", "icon": "〰️"},
    "펄스 줌": {"desc": "줌인-줌아웃 반복 (강조용)", "icon": "💥"},
}


def effect_to_ffmpeg(effect_name, duration=5.0, w=1920, h=1080):
    """카메라 효과를 FFmpeg zoompan 필터로 변환"""
    fps = 30
    total_frames = int(duration * fps)
    d = total_frames

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


# ── 효과 미리보기 CSS 애니메이션 HTML ──
def build_effect_preview_html(effect_name, img_url=None, ratio="16:9"):
    if ratio == "9:16":
        cw, ch = 180, 320
    else:
        cw, ch = 320, 180

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

    return f"""
    <style>
        @keyframes zoomInSlow {{ from {{ transform: scale(1); }} to {{ transform: scale(1.3); }} }}
        @keyframes zoomInFast {{ from {{ transform: scale(1); }} to {{ transform: scale(1.5); }} }}
        @keyframes zoomOutSlow {{ from {{ transform: scale(1.3); }} to {{ transform: scale(1); }} }}
        @keyframes zoomOutFast {{ from {{ transform: scale(1.5); }} to {{ transform: scale(1); }} }}
        @keyframes panLR {{ from {{ transform: translateX(-5%) scale(1.1); }} to {{ transform: translateX(5%) scale(1.1); }} }}
        @keyframes panRL {{ from {{ transform: translateX(5%) scale(1.1); }} to {{ transform: translateX(-5%) scale(1.1); }} }}
        @keyframes panTB {{ from {{ transform: translateY(-5%) scale(1.1); }} to {{ transform: translateY(5%) scale(1.1); }} }}
        @keyframes panBT {{ from {{ transform: translateY(5%) scale(1.1); }} to {{ transform: translateY(-5%) scale(1.1); }} }}
        @keyframes kenTLBR {{ from {{ transform: translate(-3%,-3%) scale(1); }} to {{ transform: translate(3%,3%) scale(1.3); }} }}
        @keyframes kenTRBL {{ from {{ transform: translate(3%,-3%) scale(1); }} to {{ transform: translate(-3%,3%) scale(1.3); }} }}
        @keyframes kenCL {{ from {{ transform: translateX(0) scale(1); }} to {{ transform: translateX(-5%) scale(1.3); }} }}
        @keyframes kenCR {{ from {{ transform: translateX(0) scale(1); }} to {{ transform: translateX(5%) scale(1.3); }} }}
        @keyframes shake {{ 0%,100% {{ transform: translate(0,0) scale(1.05); }} 25% {{ transform: translate(-2px,1px) scale(1.05); }} 50% {{ transform: translate(1px,-2px) scale(1.05); }} 75% {{ transform: translate(2px,1px) scale(1.05); }} }}
        @keyframes pulse {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.1); }} }}
    </style>
    <div style="width:{cw}px;height:{ch}px;overflow:hidden;border-radius:8px;border:1px solid #444;margin:5px auto;position:relative;">
        <div style="width:100%;height:100%;background:{bg};{anim}transform-origin:center center;"></div>
        <div style="position:absolute;bottom:4px;right:6px;color:#fff8;font-size:9px;font-family:monospace;
            background:rgba(0,0,0,0.5);padding:1px 4px;border-radius:3px;">{effect_name}</div>
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
    pos_css = f"bottom:{pos_b}px;" if position == "하단" else (f"top:{settings.get('pos_top',30)}px;" if position == "상단" else "top:50%;transform:translateY(-50%);")
    br, bg, bb = int(bgc[1:3],16), int(bgc[3:5],16), int(bgc[5:7],16)
    gf = f'<link href="https://fonts.googleapis.com/css2?family={font.replace(" ","+")}&display=swap" rel="stylesheet">'
    return f"""{gf}<div style="position:relative;width:{cw}px;height:{ch}px;background:linear-gradient(180deg,#0a0a1a,#1a1a3e,#0a0a1a);border-radius:12px;overflow:hidden;margin:10px auto;border:1px solid #444;">
    <div style="position:absolute;top:45%;left:50%;transform:translate(-50%,-50%);color:#ffffff08;font-size:40px;font-weight:bold;">VIDEO</div>
    <div style="position:absolute;{pos_css}left:{pos_l}px;right:{pos_r}px;text-align:{align};z-index:10;">
    <span style="font-family:'{font}',sans-serif;font-size:{ds}px;font-weight:{'bold' if bold else 'normal'};font-style:{'italic' if italic else 'normal'};color:{color};-webkit-text-stroke:{max(1,ow)}px {oc};paint-order:stroke fill;text-shadow:{sb}px {sb}px {sb*2}px {sc},-{sb}px -{sb}px {sb*2}px {sc};background:rgba({br},{bg},{bb},{bgo/100});padding:6px 14px;border-radius:6px;letter-spacing:{ls}px;line-height:{lh};display:inline-block;">{preview_text}</span>
    </div></div>"""


def subtitle_settings_ui(prefix, ratio="16:9"):
    FONTS = ["Noto Sans KR","Noto Serif KR","Black Han Sans","Jua","Do Hyeon","Gothic A1","Sunflower","Gaegu","Hi Melody","Song Myung","Stylish","Gugi","Gamja Flower","East Sea Dokdo","Cute Font","Yeon Sung","Poor Story","Single Day","Black And White Picture","Dokdo"]
    s = {}
    st.markdown("**글씨체**")
    c1, c2 = st.columns([2,1])
    with c1: s["font"] = st.selectbox("글씨체", FONTS, 0, key=f"{prefix}_font")
    with c2: s["size"] = st.number_input("크기(px)", 16, 120, 48, 1, key=f"{prefix}_size")
    st.markdown("**스타일**")
    sc = st.columns(4)
    with sc[0]: s["bold"] = st.checkbox("굵게", True, key=f"{prefix}_bold")
    with sc[1]: s["italic"] = st.checkbox("기울임", False, key=f"{prefix}_italic")
    with sc[2]: s["letter_spacing"] = st.number_input("자간", -5, 20, 0, 1, key=f"{prefix}_ls")
    with sc[3]: s["line_height"] = st.number_input("행간", 1.0, 3.0, 1.5, 0.1, key=f"{prefix}_lh")
    st.markdown("**색상**")
    cc = st.columns(4)
    with cc[0]: s["color"] = st.color_picker("글자", "#FFFFFF", key=f"{prefix}_color")
    with cc[1]: s["outline_color"] = st.color_picker("외곽선", "#000000", key=f"{prefix}_oc")
    with cc[2]: s["shadow_color"] = st.color_picker("그림자", "#000000", key=f"{prefix}_sc")
    with cc[3]: s["bg_color"] = st.color_picker("배경", "#000000", key=f"{prefix}_bgc")
    st.markdown("**효과**")
    ec = st.columns(3)
    with ec[0]: s["outline_width"] = st.slider("외곽선", 0, 8, 2, 1, key=f"{prefix}_ow")
    with ec[1]: s["shadow_blur"] = st.slider("그림자", 0, 20, 4, 1, key=f"{prefix}_sb")
    with ec[2]: s["bg_opacity"] = st.slider("배경(%)", 0, 100, 0, 5, key=f"{prefix}_bgo")
    st.markdown("**위치**")
    s["position"] = st.radio("위치", ["상단","중앙","하단"], 2, horizontal=True, key=f"{prefix}_pos")
    st.markdown("**미세조절 (px)**")
    pc = st.columns(4)
    with pc[0]: s["pos_top"] = st.number_input("위", 0, 500, 30, 1, key=f"{prefix}_mt")
    with pc[1]: s["pos_bottom"] = st.number_input("아래", 0, 500, 40, 1, key=f"{prefix}_mb")
    with pc[2]: s["pos_left"] = st.number_input("좌", 0, 300, 20, 1, key=f"{prefix}_ml")
    with pc[3]: s["pos_right"] = st.number_input("우", 0, 300, 20, 1, key=f"{prefix}_mr")
    s["align"] = st.radio("정렬", ["left","center","right"], 1, horizontal=True, key=f"{prefix}_align",
                           format_func=lambda x: {"left":"왼쪽","center":"가운데","right":"오른쪽"}[x])
    return s


def build_sync_timeline_html(timestamps, dur=None):
    if not timestamps: return ""
    total = dur or (timestamps[-1]["end"] if timestamps else 10)
    colors = ["#4CAF50","#2196F3","#FF9800","#E91E63","#9C27B0","#00BCD4","#FF5722","#795548"]
    rows = ""
    for i, ts in enumerate(timestamps):
        sp = (ts["start"]/max(total,0.1))*100
        wp = max(0.5, ((ts["end"]-ts["start"])/max(total,0.1))*100)
        c = colors[i%len(colors)]
        rows += f'<div style="display:flex;align-items:center;margin:2px 0;height:28px;"><div style="width:30px;color:#888;font-size:10px;text-align:right;margin-right:6px;">{i+1}</div><div style="flex:1;position:relative;height:22px;background:#1a1a2e;border-radius:4px;overflow:hidden;"><div style="position:absolute;left:{sp}%;width:{wp}%;height:100%;background:{c};border-radius:3px;display:flex;align-items:center;padding:0 4px;overflow:hidden;"><span style="color:#fff;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{ts["text"][:20]}</span></div></div><div style="width:100px;color:#aaa;font-size:9px;margin-left:6px;font-family:monospace;">{ts["start"]:.1f}s~{ts["end"]:.1f}s</div></div>'
    return f'<div style="background:#0a0a1a;border:1px solid #333;border-radius:8px;padding:12px;margin:10px 0;"><div style="color:#ccc;font-size:12px;font-weight:bold;margin-bottom:8px;">싱크 타임라인 ({total:.1f}초 / {len(timestamps)}개)</div>{rows}</div>'


# ── 사이드바 ──
with st.sidebar:
    st.title("시니어 콘텐츠 팩토리")
    st.divider()
    if st.session_state.selected_topic:
        st.success(f"선택된 주제: {st.session_state.selected_topic}")
    else:
        st.info("주제를 먼저 선택하세요")
    st.divider()
    st.subheader("레퍼런스 이미지")
    ref_file = st.file_uploader("주인공 이미지", type=["png","jpg","jpeg"])
    if ref_file:
        st.session_state.reference_image = ref_file.getvalue()
        st.image(ref_file, caption="레퍼런스", use_container_width=True)
    st.divider()
    if st.button("API 연결 테스트"):
        if api:
            try:
                r = api.test_connection()
                if isinstance(r, dict):
                    for svc, s in r.items():
                        if isinstance(s, dict) and s.get("status") == "connected": st.success(f"{svc}: 연결됨")
                        else: st.warning(f"{svc}: {s}")
                else: st.success("연결됨")
            except Exception as e: st.error(str(e))
    st.divider()
    if st.button("전체 초기화", type="secondary"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()


tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "주제 추천","롱폼 대본","쇼츠 대본","이미지 생성","영상 변환","음성 합성","자막 설정","최종 합치기"
])


# ═══ 탭1: 주제 추천 ═══
with tab1:
    st.header("떡상 주제 추천")
    ckw, ccnt = st.columns([3,1])
    with ckw: keyword = st.text_input("키워드", "시니어", key="search_keyword")
    with ccnt: news_count = st.number_input("뉴스 수", 3, 20, 10, key="news_count")
    if st.button("떡상 주제 추천 받기", type="primary", use_container_width=True):
        if not api: st.error("API 미연결")
        else:
            with st.spinner("분석 중..."):
                news = safe_naver_search(keyword, news_count)
                nt = ""
                for item in news[:news_count]:
                    t = re.sub(r'<[^>]+>','',str(item.get("title","") if isinstance(item,dict) else item))
                    d = re.sub(r'<[^>]+>','',str(item.get("description","") if isinstance(item,dict) else ""))
                    nt += f"- {t}: {d}\n"
                with st.expander("뉴스 (디버그)"): st.text(nt or "(없음)")
                prompt = f"뉴스 분석 유튜브 주제 10개.\n{nt or '(없음)'}\n키워드:{keyword}\n형식:1번|제목:...|확률:...|출처:...|대안:...|태그:..."
                try: raw = api.generate(prompt)
                except Exception as e: raw = ""; st.error(str(e))
                with st.expander("AI 응답"): st.code(raw or "(없음)")
                topics = []
                if raw:
                    for line in raw.strip().split("\n"):
                        m = re.search(r'제목:\s*(.+?)(?:\||$)', line.strip())
                        if m:
                            def safe_group(pat, ln):
                                mm = re.search(pat, ln)
                                return mm.group(1).strip() if mm else ""
                            topics.append({"title": m.group(1).strip().strip("*"),
                                "probability": safe_group(r'확률:\s*(.+?)(?:\||$)', line),
                                "source": safe_group(r'출처:\s*(.+?)(?:\||$)', line),
                                "alternative": safe_group(r'대안:\s*(.+?)(?:\||$)', line),
                                "tags": safe_group(r'태그:\s*(.+?)(?:\||$)', line)})
                    st.session_state.topics_list = topics
    if st.session_state.topics_list:
        for i, t in enumerate(st.session_state.topics_list):
            with st.container(border=True):
                c1, c2 = st.columns([4,1])
                with c1:
                    st.markdown(f"**{i+1}. {t['title']}**")
                    st.caption(f"확률:{t['probability']} | 출처:{t['source']} | 대안:{t['alternative']} | 태그:{t['tags']}")
                with c2:
                    if st.button("선택", key=f"pick_{i}", use_container_width=True):
                        st.session_state.selected_topic = t["title"]; sync_topic(); st.rerun()
    st.divider()
    manual = st.text_input("직접 입력", key="manual_topic_input")
    if st.button("이 주제로 설정"):
        if manual.strip(): st.session_state.selected_topic = manual.strip(); sync_topic(); st.rerun()


# ═══ 탭2: 롱폼 대본 ═══
with tab2:
    st.header("롱폼 대본 (약 30분)")
    if st.session_state.selected_topic and not st.session_state.get("longform_topic"):
        st.session_state["longform_topic"] = st.session_state.selected_topic
    topic_long = st.text_input("영상 주제", key="longform_topic")
    if st.button("롱폼 대본 생성", type="primary", use_container_width=True):
        if not topic_long.strip(): st.warning("주제 필요")
        elif not api: st.error("API 필요")
        else:
            with st.spinner("생성 중 (1~3분)..."):
                try:
                    from prompts.senior_longform import get_prompt
                    prompt = get_prompt(topic_long.strip())
                except: prompt = f"'{topic_long.strip()}' 30분 롱폼 대본.\n제목:\n태그:\n설명글:\n---대본시작---\n(본문)\n---대본끝---"
                try:
                    raw = api.generate(prompt); st.session_state.longform_script = raw
                    meta = {}
                    for f, p in [("title",r'제목:\s*(.+)'),("tags",r'태그:\s*(.+)'),("description",r'설명글:\s*(.+)')]:
                        m = re.search(p, raw)
                        if m: meta[f] = m.group(1).strip()
                    bm = re.search(r'---대본시작---(.+?)---대본끝---', raw, re.DOTALL)
                    meta["body"] = bm.group(1).strip() if bm else raw
                    st.session_state.longform_metadata = meta
                except Exception as e: st.error(str(e))
    if st.session_state.longform_metadata:
        meta = st.session_state.longform_metadata
        with st.container(border=True):
            st.subheader(meta.get("title","제목 없음"))
            if meta.get("tags"): st.caption(f"태그: {meta['tags']}")
            if meta.get("description"): st.info(meta["description"])
        with st.expander("대본 전문", expanded=True):
            body = meta.get("body","")
            st.text_area("대본", body, height=500, key="lb_disp")
            st.caption(f"{len(body)}자 | 약 {len(body)//350}분")
        st.download_button("다운로드", st.session_state.longform_script, f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")


# ═══ 탭3: 쇼츠 대본 ═══
with tab3:
    st.header("쇼츠 대본 (3편 / 40초)")
    if st.session_state.selected_topic and not st.session_state.get("shorts_topic"):
        st.session_state["shorts_topic"] = st.session_state.selected_topic
    topic_shorts = st.text_input("쇼츠 주제", key="shorts_topic")
    if st.button("쇼츠 3편 생성", type="primary", use_container_width=True):
        if not topic_shorts.strip(): st.warning("주제")
        elif not api: st.error("API")
        else:
            with st.spinner("3편 생성 중..."):
                prompt = f"""유튜브 쇼츠 대본 작가. 대주제:'{topic_shorts.strip()}'
3편 세트. 8~12문장(40초). 인사/구독금지. 열린고리. 근데/그래서/결국. 습니다+까요.
이미지프롬프트: SD 2D anime style. 9:16. 장면=문장수.
형식만:
=001=
제목:(50자)
상단제목첫째줄:(15자)
상단제목둘째줄:(15자)
설명글:(200자,해시태그)
태그:(15~20개)
순수대본:(문장나열)
=장면001=
대사:...
프롬프트:SD 2D anime style,...
=002= =003= 동일"""
                try:
                    raw = api.generate(prompt); st.session_state.shorts_raw = raw
                    episodes = []; blocks = re.split(r'=00(\d)=', raw)
                    i = 1
                    while i < len(blocks)-1:
                        n, c = blocks[i].strip(), blocks[i+1].strip()
                        ep = {"num":n,"raw":c}
                        for f, p in [("title",r'제목:\s*(.+)'),("top_line1",r'상단제목첫째줄:\s*(.+)'),("top_line2",r'상단제목둘째줄:\s*(.+)'),("tags",r'태그:\s*(.+)')]:
                            m = re.search(p,c); ep[f] = m.group(1).strip() if m else ""
                        if not ep.get("title"): ep["title"] = f"쇼츠 {n}편"
                        m = re.search(r'설명글:\s*(.+?)(?=\n태그:|\n=장면)', c, re.DOTALL)
                        ep["description"] = m.group(1).strip() if m else ""
                        m = re.search(r'순수대본:\s*(.+?)(?=\n=장면)', c, re.DOTALL)
                        ep["script"] = m.group(1).strip() if m else ""
                        scenes = re.findall(r'=장면\d+=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?=\n=장면|\n=00|$)', c, re.DOTALL)
                        ep["scenes"] = [{"dialogue":d.strip(),"prompt":p.strip()} for d,p in scenes]
                        episodes.append(ep); i += 2
                    st.session_state.shorts_data = episodes
                except Exception as e: st.error(str(e))
    if st.session_state.shorts_data:
        with st.expander("AI 원본"): st.code(st.session_state.shorts_raw)
        for ep in st.session_state.shorts_data:
            st.divider()
            with st.container(border=True):
                tc, ttc = st.columns([3,2])
                with tc: st.subheader(f"편 {ep['num']}. {ep['title']}")
                with ttc:
                    if ep.get("top_line1"): st.markdown(f"**상단:** {ep['top_line1']} / {ep.get('top_line2','')}")
                if ep.get("tags"):
                    with st.container(border=True): st.markdown("**태그**"); st.write(ep["tags"])
                if ep.get("description"):
                    with st.container(border=True): st.markdown("**설명글**"); st.write(ep["description"])
                with st.container(border=True):
                    st.markdown("**대본 (40초)**"); st.write(ep.get("script","(없음)"))
                    if ep.get("script"): st.caption(f"{len(ep['script'])}자")
                if ep.get("scenes"):
                    with st.expander(f"장면 프롬프트 ({len(ep['scenes'])}개)"):
                        for j, s in enumerate(ep["scenes"]):
                            st.markdown(f"**장면{j+1}**"); st.write(f"대사: {s['dialogue']}"); st.code(s["prompt"])
        st.download_button("3편 다운로드", st.session_state.shorts_raw, f"shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")


# ═══ 탭4: 이미지 생성 ═══
with tab4:
    st.header("이미지 생성")
    it_l, it_s = st.tabs(["롱폼(16:9)","쇼츠(9:16)"])
    with it_l:
        st.subheader("롱폼 이미지")
        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            if st.button("프롬프트 생성", key="gl_p"):
                with st.spinner("생성 중..."):
                    try:
                        r = api.generate(f"대본 문단별 이미지프롬프트. SD 2D anime style. 16:9.\n[장면N]\n내용요약:\n프롬프트:\n\n대본:\n{body[:3000]}")
                        st.session_state["lp_raw"] = r
                    except Exception as e: st.error(str(e))
            if st.session_state.get("lp_raw"):
                st.text_area("프롬프트", st.session_state["lp_raw"], height=300, key="lp_d")
                prompts = re.findall(r'프롬프트:\s*(SD 2D anime style,.+?)(?=\n\[장면|\n$|$)', st.session_state["lp_raw"], re.DOTALL)
                if prompts and st.button("이미지 생성", key="gl_i"):
                    prog = st.progress(0); gen = []
                    for idx, p in enumerate(prompts):
                        try: gen.append({"prompt":p.strip(),"url":api.generate_image(p.strip(),aspect_ratio="16:9"),"index":idx+1})
                        except Exception as e: gen.append({"prompt":p.strip(),"url":None,"error":str(e),"index":idx+1})
                        prog.progress((idx+1)/len(prompts))
                    st.session_state.generated_images_longform = gen
            if st.session_state.generated_images_longform:
                cols = st.columns(3)
                for idx, img in enumerate(st.session_state.generated_images_longform):
                    with cols[idx%3]:
                        st.caption(f"장면{img['index']}")
                        if img.get("url"): st.image(img["url"], use_container_width=True)
                        else: st.error(img.get("error",""))
        else: st.warning("롱폼 대본 먼저")

    with it_s:
        st.subheader("쇼츠 이미지")
        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                with st.container(border=True):
                    st.markdown(f"**편{ep['num']}. {ep['title']}**")
                    if ep.get("scenes"):
                        for j, s in enumerate(ep["scenes"]):
                            st.caption(f"장면{j+1}: {s['dialogue'][:30]}...")
                            st.code(s["prompt"])
                        if st.button(f"편{ep['num']} 생성", key=f"gsi_{ep['num']}"):
                            prog = st.progress(0); imgs = []
                            for j, s in enumerate(ep["scenes"]):
                                try: imgs.append({"url":api.generate_image(s["prompt"],aspect_ratio="9:16"),"scene":j+1,"dialogue":s["dialogue"]})
                                except Exception as e: imgs.append({"url":None,"scene":j+1,"error":str(e),"dialogue":s["dialogue"]})
                                prog.progress((j+1)/len(ep["scenes"]))
                            st.session_state[f"si_ep{ep['num']}"] = imgs
                        if st.session_state.get(f"si_ep{ep['num']}"):
                            cols = st.columns(4)
                            for j, img in enumerate(st.session_state[f"si_ep{ep['num']}"]):
                                with cols[j%4]:
                                    st.caption(f"장면{img['scene']}")
                                    if img.get("url"): st.image(img["url"], use_container_width=True)
                                    else: st.error(img.get("error",""))
        else: st.warning("쇼츠 대본 먼저")


# ═══ 탭5: 영상 변환 (이미지 자동 연동 + 카메라 효과) ═══
with tab5:
    st.header("영상 변환")
    st.caption("이미지 생성 탭에서 만든 이미지가 자동으로 연결됩니다. 장면별 카메라 효과를 설정하고 영상으로 변환하세요.")

    vid_tl, vid_ts, vid_manual = st.tabs(["롱폼 영상","쇼츠 영상","수동 변환"])

    # ── 롱폼 영상 ──
    with vid_tl:
        st.subheader("롱폼 이미지 → 영상 변환")

        if st.session_state.generated_images_longform:
            imgs = [img for img in st.session_state.generated_images_longform if img.get("url")]
            st.info(f"총 {len(imgs)}개 이미지 준비됨")

            # 일괄 효과 설정
            st.markdown("**일괄 카메라 효과 설정**")
            bulk_effect = st.selectbox(
                "전체 장면에 적용할 효과",
                list(CAMERA_EFFECTS.keys()),
                index=0, key="bulk_long_effect"
            )
            if st.button("전체 적용", key="apply_bulk_long"):
                for img in imgs:
                    st.session_state.video_effects_longform[img["index"]] = bulk_effect
                st.rerun()

            # 장면별 효과 설정
            st.divider()
            st.markdown("**장면별 효과 설정 + 미리보기**")

            for img in imgs:
                with st.container(border=True):
                    c_img, c_effect, c_preview = st.columns([2, 2, 2])

                    with c_img:
                        st.caption(f"장면 {img['index']}")
                        st.image(img["url"], use_container_width=True)

                    with c_effect:
                        current = st.session_state.video_effects_longform.get(img["index"], "줌인 (느린)")
                        effect_list = list(CAMERA_EFFECTS.keys())
                        default_idx = effect_list.index(current) if current in effect_list else 0
                        selected = st.selectbox(
                            f"효과", effect_list, default_idx,
                            key=f"eff_long_{img['index']}"
                        )
                        st.session_state.video_effects_longform[img["index"]] = selected
                        st.caption(f"{CAMERA_EFFECTS[selected]['icon']} {CAMERA_EFFECTS[selected]['desc']}")

                        # 장면 길이
                        dur = st.number_input(
                            "장면 길이(초)", 2.0, 30.0, 5.0, 0.5,
                            key=f"dur_long_{img['index']}"
                        )

                    with c_preview:
                        st.caption("효과 미리보기")
                        html = build_effect_preview_html(selected, img.get("url"), "16:9")
                        st.components.v1.html(html, height=220)

            # Kie AI 영상 변환 또는 FFmpeg 명령어
            st.divider()
            st.markdown("**영상 변환 실행**")

            convert_mode = st.radio(
                "변환 방식", ["Kie AI (클라우드 변환)", "FFmpeg 명령어 생성 (로컬)"],
                horizontal=True, key="long_convert_mode"
            )

            if convert_mode == "Kie AI (클라우드 변환)":
                if st.button("Kie AI로 영상 변환 시작", type="primary", key="kie_long_convert"):
                    if api:
                        for img in imgs:
                            st.write(f"장면{img['index']} 변환 중...")
                            try:
                                task_id = api.kie.create_task(img["url"])
                                result = api.kie.wait_for_completion(task_id)
                                if result:
                                    st.session_state.video_results_longform[img["index"]] = result
                                    st.success(f"장면{img['index']} 완료")
                                else:
                                    st.error(f"장면{img['index']} 실패")
                            except Exception as e:
                                st.error(f"장면{img['index']}: {e}")
                        st.success("롱폼 영상 변환 완료!")

                # 변환된 영상 표시
                if st.session_state.video_results_longform:
                    st.divider()
                    st.subheader("변환된 영상")
                    for idx, url in sorted(st.session_state.video_results_longform.items()):
                        with st.container(border=True):
                            st.caption(f"장면 {idx}")
                            st.video(url)

            else:
                if st.button("FFmpeg 명령어 생성", key="ffmpeg_long"):
                    st.markdown("**각 장면별 FFmpeg 명령어:**")
                    for img in imgs:
                        effect = st.session_state.video_effects_longform.get(img["index"], "없음")
                        dur_val = 5.0
                        zoompan = effect_to_ffmpeg(effect, dur_val, 1920, 1080)
                        cmd = f'ffmpeg -loop 1 -i scene_{img["index"]:03d}.png -vf "{zoompan}" -t {dur_val} -pix_fmt yuv420p scene_{img["index"]:03d}.mp4'
                        st.code(cmd, language="bash")

                    # 전체 concat 명령어
                    st.markdown("**전체 이어붙이기:**")
                    concat_list = "\n".join([f"file 'scene_{img['index']:03d}.mp4'" for img in imgs])
                    st.code(f"# concat_list.txt 파일 내용:\n{concat_list}\n\n# 합치기 명령어:\nffmpeg -f concat -safe 0 -i concat_list.txt -c copy longform_video.mp4", language="bash")
        else:
            st.warning("먼저 [이미지 생성] 탭에서 롱폼 이미지를 생성하세요.")

    # ── 쇼츠 영상 ──
    with vid_ts:
        st.subheader("쇼츠 이미지 → 영상 변환")

        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                ep_key = f"si_ep{ep['num']}"
                ep_imgs = st.session_state.get(ep_key, [])
                ep_imgs_valid = [img for img in ep_imgs if img.get("url")]

                if not ep_imgs_valid:
                    st.info(f"편{ep['num']}: 이미지 없음. [이미지 생성] 탭에서 먼저 생성하세요.")
                    continue

                with st.container(border=True):
                    st.markdown(f"**편 {ep['num']}. {ep['title']}** ({len(ep_imgs_valid)}개 이미지)")

                    # 일괄 효과
                    bulk_s = st.selectbox(
                        f"편{ep['num']} 일괄 효과",
                        list(CAMERA_EFFECTS.keys()), 0,
                        key=f"bulk_s_eff_{ep['num']}"
                    )
                    if st.button(f"편{ep['num']} 전체 적용", key=f"apply_bulk_s_{ep['num']}"):
                        for img in ep_imgs_valid:
                            ek = f"s{ep['num']}_{img['scene']}"
                            st.session_state.video_effects_shorts[ek] = bulk_s
                        st.rerun()

                    # 장면별
                    for img in ep_imgs_valid:
                        ek = f"s{ep['num']}_{img['scene']}"
                        ci, ce, cp = st.columns([2, 2, 2])
                        with ci:
                            st.caption(f"장면{img['scene']}: {img.get('dialogue','')[:25]}...")
                            st.image(img["url"], use_container_width=True)
                        with ce:
                            cur = st.session_state.video_effects_shorts.get(ek, "줌인 (느린)")
                            elist = list(CAMERA_EFFECTS.keys())
                            didx = elist.index(cur) if cur in elist else 0
                            sel = st.selectbox("효과", elist, didx, key=f"eff_s_{ek}")
                            st.session_state.video_effects_shorts[ek] = sel
                            st.caption(f"{CAMERA_EFFECTS[sel]['icon']} {CAMERA_EFFECTS[sel]['desc']}")
                        with cp:
                            st.caption("미리보기")
                            st.components.v1.html(build_effect_preview_html(sel, img.get("url"), "9:16"), height=360)

                    # 변환 버튼
                    s_mode = st.radio(
                        f"편{ep['num']} 변환", ["Kie AI","FFmpeg 명령어"],
                        horizontal=True, key=f"s_mode_{ep['num']}"
                    )

                    if s_mode == "Kie AI":
                        if st.button(f"편{ep['num']} Kie AI 변환", key=f"kie_s_{ep['num']}"):
                            if api:
                                for img in ep_imgs_valid:
                                    try:
                                        tid = api.kie.create_task(img["url"])
                                        r = api.kie.wait_for_completion(tid)
                                        if r:
                                            vk = f"s{ep['num']}_{img['scene']}"
                                            st.session_state.video_results_shorts[vk] = r
                                            st.success(f"편{ep['num']} 장면{img['scene']} 완료")
                                    except Exception as e:
                                        st.error(str(e))

                        # 결과 표시
                        ep_results = {k:v for k,v in st.session_state.video_results_shorts.items() if k.startswith(f"s{ep['num']}_")}
                        if ep_results:
                            for vk, vurl in sorted(ep_results.items()):
                                st.video(vurl)
                    else:
                        if st.button(f"편{ep['num']} FFmpeg 생성", key=f"ffcmd_s_{ep['num']}"):
                            for img in ep_imgs_valid:
                                ek = f"s{ep['num']}_{img['scene']}"
                                eff = st.session_state.video_effects_shorts.get(ek, "없음")
                                zp = effect_to_ffmpeg(eff, 4.0, 1080, 1920)
                                st.code(f'ffmpeg -loop 1 -i ep{ep["num"]}_scene{img["scene"]:02d}.png -vf "{zp}" -t 4 -pix_fmt yuv420p ep{ep["num"]}_scene{img["scene"]:02d}.mp4', language="bash")
        else:
            st.warning("쇼츠 대본/이미지 먼저 생성하세요.")

    # ── 수동 변환 ──
    with vid_manual:
        st.subheader("수동 이미지 URL 영상 변환")
        manual_url = st.text_input("이미지 URL", key="manual_vid_url")
        if st.button("변환", key="manual_convert") and manual_url.strip() and api:
            with st.spinner("변환 중..."):
                try:
                    tid = api.kie.create_task(manual_url.strip())
                    r = api.kie.wait_for_completion(tid)
                    if r: st.success("완료!"); st.video(r)
                    else: st.error("실패")
                except Exception as e: st.error(str(e))


# ═══ 탭6: 음성 합성 + 싱크 ═══
with tab6:
    st.header("음성 합성 + 자막 자동 싱크")
    tts_tl, tts_ts = st.tabs(["롱폼 음성","쇼츠 음성"])

    with tts_tl:
        st.subheader("롱폼 음성")
        lb = st.session_state.longform_metadata.get("body","") if st.session_state.longform_metadata else ""
        tts_lt = st.text_area("텍스트", lb, height=200, key="tts_lt")
        if st.button("롱폼 음성+싱크", type="primary", key="tts_lb"):
            if tts_lt.strip() and api:
                with st.spinner("합성 중..."):
                    try:
                        result = api.inworld.synthesize(tts_lt.strip())
                        audio, ts, err = (result + (None,None,None))[:3] if isinstance(result, tuple) else (result, None, None)
                        if err: st.error(str(err))
                        elif audio:
                            ab = base64.b64decode(audio) if isinstance(audio, str) else audio
                            st.session_state.tts_longform_audio = ab; st.audio(ab, format="audio/mp3")
                            pts = parse_tts_timestamps(ts, tts_lt.strip())
                            st.session_state.tts_longform_timestamps = pts
                            st.session_state.tts_longform_srt = timestamps_to_srt(pts)
                            st.success(f"{len(pts)}개 자막 싱크 완료")
                    except Exception as e: st.error(str(e))
        if st.session_state.tts_longform_timestamps:
            ts = st.session_state.tts_longform_timestamps
            st.components.v1.html(build_sync_timeline_html(ts), height=50+len(ts)*34, scrolling=True)
            if st.session_state.tts_longform_srt:
                with st.expander("SRT"): st.code(st.session_state.tts_longform_srt)
                c1, c2 = st.columns(2)
                with c1: st.download_button("SRT", st.session_state.tts_longform_srt, "longform.srt")
                with c2:
                    if st.session_state.tts_longform_audio:
                        st.download_button("MP3", st.session_state.tts_longform_audio, "longform.mp3", "audio/mp3")

    with tts_ts:
        st.subheader("쇼츠 편별 음성")
        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                with st.container(border=True):
                    st.markdown(f"**편{ep['num']}. {ep['title']}**")
                    script = ep.get("script","")
                    if st.button(f"편{ep['num']} 음성+싱크", key=f"tts_s_{ep['num']}"):
                        if script.strip() and api:
                            with st.spinner(f"편{ep['num']} 합성..."):
                                try:
                                    result = api.inworld.synthesize(script.strip())
                                    audio, ts, err = (result+(None,None,None))[:3] if isinstance(result,tuple) else (result,None,None)
                                    if audio and not err:
                                        ab = base64.b64decode(audio) if isinstance(audio,str) else audio
                                        st.session_state.tts_shorts_audio[ep['num']] = ab
                                        pts = parse_tts_timestamps(ts, script.strip())
                                        st.session_state.tts_shorts_timestamps[ep['num']] = pts
                                        st.session_state.tts_shorts_srt[ep['num']] = timestamps_to_srt(pts)
                                        st.success(f"편{ep['num']} {len(pts)}개 싱크")
                                except Exception as e: st.error(str(e))
                    if st.session_state.tts_shorts_audio.get(ep['num']):
                        st.audio(st.session_state.tts_shorts_audio[ep['num']], format="audio/mp3")
                        ts = st.session_state.tts_shorts_timestamps.get(ep['num'],[])
                        if ts: st.components.v1.html(build_sync_timeline_html(ts), height=50+len(ts)*34, scrolling=True)
                        srt = st.session_state.tts_shorts_srt.get(ep['num'],"")
                        if srt:
                            c1, c2 = st.columns(2)
                            with c1: st.download_button(f"편{ep['num']} SRT", srt, f"shorts_ep{ep['num']}.srt", key=f"dl_srt_{ep['num']}")
                            with c2: st.download_button(f"편{ep['num']} MP3", st.session_state.tts_shorts_audio[ep['num']], f"shorts_ep{ep['num']}.mp3", "audio/mp3", key=f"dl_mp3_{ep['num']}")

            if st.button("3편 전체 일괄 합성", type="primary", key="tts_all_s"):
                for ep in st.session_state.shorts_data:
                    script = ep.get("script","")
                    if script.strip() and api:
                        try:
                            result = api.inworld.synthesize(script.strip())
                            audio, ts, err = (result+(None,None,None))[:3] if isinstance(result,tuple) else (result,None,None)
                            if audio and not err:
                                ab = base64.b64decode(audio) if isinstance(audio,str) else audio
                                st.session_state.tts_shorts_audio[ep['num']] = ab
                                pts = parse_tts_timestamps(ts, script.strip())
                                st.session_state.tts_shorts_timestamps[ep['num']] = pts
                                st.session_state.tts_shorts_srt[ep['num']] = timestamps_to_srt(pts)
                        except: pass
                st.rerun()
        else: st.warning("쇼츠 대본 먼저")


# ═══ 탭7: 자막 설정 ═══
with tab7:
    st.header("자막 설정")
    sub_tl, sub_ts = st.tabs(["롱폼 자막(16:9)","쇼츠 자막(9:16)"])
    with sub_tl:
        ctrl, prev = st.columns([1,1])
        with ctrl:
            long_settings = subtitle_settings_ui("long","16:9")
            st.session_state.sub_settings_longform = long_settings
        with prev:
            st.markdown("**미리보기**")
            lpt = st.text_input("텍스트","자막 미리보기 샘플", key="lpt")
            st.components.v1.html(build_subtitle_preview_html(long_settings, lpt, "16:9"), height=360)
            if st.session_state.tts_longform_timestamps:
                st.divider()
                ts = st.session_state.tts_longform_timestamps
                sel = st.slider("자막 번호", 1, len(ts), 1, key="l_sub_sel")
                st.caption(f"#{sel} | {ts[sel-1]['start']:.1f}s~{ts[sel-1]['end']:.1f}s")
                st.components.v1.html(build_subtitle_preview_html(long_settings, ts[sel-1]["text"], "16:9"), height=360)

    with sub_ts:
        ctrl2, prev2 = st.columns([1,1])
        with ctrl2:
            shorts_settings = subtitle_settings_ui("shorts","9:16")
            st.session_state.sub_settings_shorts = shorts_settings
        with prev2:
            st.markdown("**미리보기**")
            spt = st.text_input("텍스트","쇼츠 자막 미리보기", key="spt")
            st.components.v1.html(build_subtitle_preview_html(shorts_settings, spt, "9:16"), height=540)

    st.divider()
    st.subheader("글씨체 갤러리")
    FONTS = ["Noto Sans KR","Noto Serif KR","Black Han Sans","Jua","Do Hyeon","Gothic A1","Sunflower","Gaegu","Hi Melody","Song Myung","Stylish","Gugi","Gamja Flower","East Sea Dokdo","Cute Font","Yeon Sung","Poor Story","Single Day","Black And White Picture","Dokdo"]
    gt = st.text_input("갤러리 텍스트","떡상 콘텐츠 팩토리", key="gt")
    links = "".join([f'<link href="https://fonts.googleapis.com/css2?family={f.replace(" ","+")}&display=swap" rel="stylesheet">' for f in FONTS])
    cards = "".join([f'<div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:12px;margin:4px;display:inline-block;min-width:200px;"><div style="color:#888;font-size:10px;font-family:monospace;">{f}</div><div style="font-family:\'{f}\',sans-serif;font-size:18px;color:#fff;-webkit-text-stroke:1px #000;text-shadow:2px 2px 4px #000;">{gt}</div></div>' for f in FONTS])
    st.components.v1.html(f"{links}<div style='display:flex;flex-wrap:wrap;gap:6px;padding:10px;'>{cards}</div>", height=500, scrolling=True)


# ═══ 탭8: 최종 합치기 ═══
with tab8:
    st.header("최종 합치기")
    checks = {
        "주제": st.session_state.selected_topic or "없음",
        "롱폼 대본": "O" if st.session_state.longform_metadata else "없음",
        "쇼츠 대본": f"{len(st.session_state.shorts_data)}편" if st.session_state.shorts_data else "없음",
        "롱폼 이미지": f"{len(st.session_state.generated_images_longform)}장" if st.session_state.generated_images_longform else "없음",
        "롱폼 음성": "O" if st.session_state.tts_longform_audio else "없음",
        "롱폼 SRT": "O" if st.session_state.tts_longform_srt else "없음",
        "쇼츠 음성": f"{len(st.session_state.tts_shorts_audio)}편" if st.session_state.tts_shorts_audio else "없음",
        "쇼츠 SRT": f"{len(st.session_state.tts_shorts_srt)}편" if st.session_state.tts_shorts_srt else "없음",
        "롱폼 영상효과": f"{len(st.session_state.video_effects_longform)}개" if st.session_state.video_effects_longform else "없음",
        "롱폼 자막설정": "O" if st.session_state.sub_settings_longform else "없음",
        "쇼츠 자막설정": "O" if st.session_state.sub_settings_shorts else "없음",
    }
    for k, v in checks.items():
        (st.success if v != "없음" else st.warning)(f"{k}: {v}")

    st.divider()
    export = {
        "sub_longform": st.session_state.sub_settings_longform,
        "sub_shorts": st.session_state.sub_settings_shorts,
        "srt_longform": st.session_state.tts_longform_srt,
        "srt_shorts": dict(st.session_state.tts_shorts_srt),
        "effects_longform": st.session_state.video_effects_longform,
        "effects_shorts": st.session_state.video_effects_shorts,
    }
    st.download_button("전체 설정 JSON", json.dumps(export, ensure_ascii=False, indent=2, default=str),
                       f"all_settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")
