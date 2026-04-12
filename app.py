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
        if "items" in raw_result:
            news_items = raw_result["items"]
        elif "news" in raw_result:
            news_items = raw_result["news"]
        elif "results" in raw_result:
            news_items = raw_result["results"]
        else:
            news_items = [raw_result]
    elif isinstance(raw_result, list):
        news_items = raw_result
    elif isinstance(raw_result, str):
        lines = [l.strip() for l in raw_result.split("\n") if l.strip()]
        news_items = [{"title": l, "description": ""} for l in lines]
    else:
        return []
    safe_items = []
    for item in news_items:
        if isinstance(item, dict):
            safe_items.append(item)
        elif isinstance(item, str):
            safe_items.append({"title": item, "description": ""})
        elif isinstance(item, (list, tuple)):
            safe_items.append({"title": str(item[0]) if item else "", "description": str(item[1]) if len(item) > 1 else ""})
        else:
            safe_items.append({"title": str(item), "description": ""})
    return safe_items


# ── 타임스탬프 → SRT 변환 함수 ──
def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def timestamps_to_srt(timestamps):
    """타임스탬프 리스트를 SRT 형식으로 변환
    timestamps: [{"text": "문장", "start": 0.0, "end": 2.5}, ...]
    """
    srt_lines = []
    for i, ts in enumerate(timestamps):
        idx = i + 1
        start = format_srt_time(ts.get("start", 0))
        end = format_srt_time(ts.get("end", 0))
        text = ts.get("text", "")
        srt_lines.append(f"{idx}")
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(text)
        srt_lines.append("")
    return "\n".join(srt_lines)


def estimate_timestamps_from_text(text, total_duration=None):
    """TTS 타임스탬프가 없을 경우 텍스트 기반으로 추정"""
    sentences = re.split(r'(?<=[.?!])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []

    total_chars = sum(len(s) for s in sentences)
    if total_duration is None:
        total_duration = total_chars / 7.0

    timestamps = []
    current_time = 0.0
    for s in sentences:
        char_ratio = len(s) / max(total_chars, 1)
        duration = char_ratio * total_duration
        duration = max(duration, 0.5)
        timestamps.append({
            "text": s,
            "start": round(current_time, 3),
            "end": round(current_time + duration, 3),
        })
        current_time += duration

    return timestamps


def parse_tts_timestamps(raw_timestamps, script_text):
    """TTS API에서 반환하는 다양한 형태의 타임스탬프를 정규화"""
    if not raw_timestamps:
        return estimate_timestamps_from_text(script_text)

    if isinstance(raw_timestamps, list) and len(raw_timestamps) > 0:
        first = raw_timestamps[0]
        if isinstance(first, dict) and "start" in first and "text" in first:
            return raw_timestamps
        if isinstance(first, dict) and "startTime" in first:
            return [{"text": t.get("text", ""), "start": t["startTime"], "end": t.get("endTime", t["startTime"] + 1)} for t in raw_timestamps]
        if isinstance(first, dict) and "offset" in first:
            result = []
            for t in raw_timestamps:
                start = t.get("offset", 0)
                dur = t.get("duration", 1)
                result.append({"text": t.get("text", ""), "start": start, "end": start + dur})
            return result
        if isinstance(first, (list, tuple)) and len(first) >= 3:
            return [{"text": str(t[0]), "start": float(t[1]), "end": float(t[2])} for t in raw_timestamps]

    if isinstance(raw_timestamps, dict):
        if "words" in raw_timestamps:
            return parse_tts_timestamps(raw_timestamps["words"], script_text)
        if "sentences" in raw_timestamps:
            return parse_tts_timestamps(raw_timestamps["sentences"], script_text)

    return estimate_timestamps_from_text(script_text)


# ── 자막 미리보기 HTML ──
def build_subtitle_preview_html(settings, preview_text, ratio="16:9"):
    font = settings.get("font", "Noto Sans KR")
    size = settings.get("size", 48)
    color = settings.get("color", "#FFFFFF")
    outline_color = settings.get("outline_color", "#000000")
    outline_w = settings.get("outline_width", 3)
    shadow_color = settings.get("shadow_color", "#000000")
    shadow_blur = settings.get("shadow_blur", 4)
    bg_color = settings.get("bg_color", "#000000")
    bg_opacity = settings.get("bg_opacity", 0)
    pos_bottom = settings.get("pos_bottom", 40)
    pos_left = settings.get("pos_left", 20)
    pos_right = settings.get("pos_right", 20)
    align = settings.get("align", "center")
    bold = settings.get("bold", True)
    italic = settings.get("italic", False)
    letter_spacing = settings.get("letter_spacing", 0)
    line_height = settings.get("line_height", 1.5)
    position = settings.get("position", "하단")

    if ratio == "9:16":
        cw, ch = 270, 480
        display_size = max(10, size // 4)
    else:
        cw, ch = 540, 304
        display_size = max(10, size // 3)

    if position == "상단":
        pos_css = f"top: {settings.get('pos_top', 30)}px;"
    elif position == "중앙":
        pos_css = "top: 50%; transform: translateY(-50%);"
    else:
        pos_css = f"bottom: {pos_bottom}px;"

    bg_r = int(bg_color[1:3], 16)
    bg_g = int(bg_color[3:5], 16)
    bg_b = int(bg_color[5:7], 16)
    bg_rgba = f"rgba({bg_r},{bg_g},{bg_b},{bg_opacity / 100})"
    fw = "bold" if bold else "normal"
    fs = "italic" if italic else "normal"
    gf_link = f'<link href="https://fonts.googleapis.com/css2?family={font.replace(" ", "+")}&display=swap" rel="stylesheet">'

    return f"""
    {gf_link}
    <div style="position:relative;width:{cw}px;height:{ch}px;
        background:linear-gradient(180deg,#0a0a1a 0%,#1a1a3e 30%,#0a0a1a 60%,#1a0a2e 100%);
        border-radius:12px;overflow:hidden;margin:10px auto;border:1px solid #444;
        box-shadow:0 4px 20px rgba(0,0,0,0.5);">
        <div style="position:absolute;top:0;left:0;right:0;bottom:0;
            background:radial-gradient(ellipse at 30% 40%,rgba(100,100,200,0.08) 0%,transparent 60%),
            radial-gradient(ellipse at 70% 60%,rgba(200,100,100,0.06) 0%,transparent 60%);
            pointer-events:none;"></div>
        <div style="position:absolute;top:12px;left:12px;display:flex;gap:4px;">
            <div style="width:8px;height:8px;border-radius:50%;background:#ff5f57;"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:#febc2e;"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:#28c840;"></div>
        </div>
        <div style="position:absolute;top:10px;right:12px;color:#ffffff30;font-size:9px;font-family:monospace;">{ratio} PREVIEW</div>
        <div style="position:absolute;top:45%;left:50%;transform:translate(-50%,-50%);color:#ffffff08;font-size:40px;font-weight:bold;pointer-events:none;">VIDEO</div>
        <div style="position:absolute;{pos_css}left:{pos_left}px;right:{pos_right}px;text-align:{align};z-index:10;">
            <span style="font-family:'{font}',sans-serif;font-size:{display_size}px;font-weight:{fw};
                font-style:{fs};color:{color};-webkit-text-stroke:{max(1,outline_w)}px {outline_color};
                paint-order:stroke fill;
                text-shadow:{shadow_blur}px {shadow_blur}px {shadow_blur*2}px {shadow_color},
                    -{shadow_blur}px -{shadow_blur}px {shadow_blur*2}px {shadow_color};
                background:{bg_rgba};padding:6px 14px;border-radius:6px;
                letter-spacing:{letter_spacing}px;line-height:{line_height};
                display:inline-block;max-width:100%;word-break:keep-all;">{preview_text}</span>
        </div>
    </div>"""


def subtitle_settings_ui(prefix, ratio="16:9"):
    FONT_LIST = [
        "Noto Sans KR", "Noto Serif KR", "Black Han Sans", "Jua", "Do Hyeon",
        "Gothic A1", "Sunflower", "Gaegu", "Hi Melody", "Song Myung",
        "Stylish", "Gugi", "Gamja Flower", "East Sea Dokdo", "Cute Font",
        "Yeon Sung", "Poor Story", "Single Day", "Black And White Picture", "Dokdo",
    ]
    settings = {}
    st.markdown("**글씨체 선택**")
    fc1, fc2 = st.columns([2, 1])
    with fc1:
        settings["font"] = st.selectbox("글씨체", FONT_LIST, index=0, key=f"{prefix}_font")
    with fc2:
        settings["size"] = st.number_input("크기(px)", 16, 120, 48, 1, key=f"{prefix}_size")

    st.markdown("**글자 스타일**")
    sc = st.columns(4)
    with sc[0]:
        settings["bold"] = st.checkbox("굵게", True, key=f"{prefix}_bold")
    with sc[1]:
        settings["italic"] = st.checkbox("기울임", False, key=f"{prefix}_italic")
    with sc[2]:
        settings["letter_spacing"] = st.number_input("자간", -5, 20, 0, 1, key=f"{prefix}_ls")
    with sc[3]:
        settings["line_height"] = st.number_input("행간", 1.0, 3.0, 1.5, 0.1, key=f"{prefix}_lh")

    st.markdown("**색상 설정**")
    cc = st.columns(4)
    with cc[0]:
        settings["color"] = st.color_picker("글자색", "#FFFFFF", key=f"{prefix}_color")
    with cc[1]:
        settings["outline_color"] = st.color_picker("외곽선", "#000000", key=f"{prefix}_oc")
    with cc[2]:
        settings["shadow_color"] = st.color_picker("그림자", "#000000", key=f"{prefix}_sc")
    with cc[3]:
        settings["bg_color"] = st.color_picker("배경색", "#000000", key=f"{prefix}_bgc")

    st.markdown("**외곽선 / 그림자 / 배경**")
    ec = st.columns(3)
    with ec[0]:
        settings["outline_width"] = st.slider("외곽선 두께", 0, 8, 2, 1, key=f"{prefix}_ow")
    with ec[1]:
        settings["shadow_blur"] = st.slider("그림자 번짐", 0, 20, 4, 1, key=f"{prefix}_sb")
    with ec[2]:
        settings["bg_opacity"] = st.slider("배경 투명도(%)", 0, 100, 0, 5, key=f"{prefix}_bgo")

    st.markdown("**위치 설정**")
    settings["position"] = st.radio("기본 위치", ["상단", "중앙", "하단"], 2, horizontal=True, key=f"{prefix}_pos")

    st.markdown("**상하좌우 미세조절 (px)**")
    pc = st.columns(4)
    with pc[0]:
        settings["pos_top"] = st.number_input("위 여백", 0, 500, 30, 1, key=f"{prefix}_mt")
    with pc[1]:
        settings["pos_bottom"] = st.number_input("아래 여백", 0, 500, 40, 1, key=f"{prefix}_mb")
    with pc[2]:
        settings["pos_left"] = st.number_input("왼쪽 여백", 0, 300, 20, 1, key=f"{prefix}_ml")
    with pc[3]:
        settings["pos_right"] = st.number_input("오른쪽 여백", 0, 300, 20, 1, key=f"{prefix}_mr")

    st.markdown("**정렬**")
    settings["align"] = st.radio("텍스트 정렬", ["left", "center", "right"], 1, horizontal=True, key=f"{prefix}_align",
                                  format_func=lambda x: {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}[x])
    return settings


# ── 싱크 타임라인 미리보기 HTML ──
def build_sync_timeline_html(timestamps, audio_duration=None):
    if not timestamps:
        return "<p style='color:#888;'>타임스탬프 데이터가 없습니다.</p>"

    total = audio_duration or (timestamps[-1]["end"] if timestamps else 10)
    rows = ""
    for i, ts in enumerate(timestamps):
        start_pct = (ts["start"] / max(total, 0.1)) * 100
        width_pct = ((ts["end"] - ts["start"]) / max(total, 0.1)) * 100
        width_pct = max(width_pct, 0.5)
        colors = ["#4CAF50", "#2196F3", "#FF9800", "#E91E63", "#9C27B0", "#00BCD4", "#FF5722", "#795548"]
        c = colors[i % len(colors)]
        rows += f"""
        <div style="display:flex;align-items:center;margin:2px 0;height:28px;">
            <div style="width:30px;color:#888;font-size:10px;text-align:right;margin-right:6px;">{i+1}</div>
            <div style="flex:1;position:relative;height:22px;background:#1a1a2e;border-radius:4px;overflow:hidden;">
                <div style="position:absolute;left:{start_pct}%;width:{width_pct}%;height:100%;
                    background:{c};border-radius:3px;display:flex;align-items:center;padding:0 4px;
                    overflow:hidden;white-space:nowrap;">
                    <span style="color:#fff;font-size:9px;text-overflow:ellipsis;overflow:hidden;">{ts['text'][:20]}</span>
                </div>
            </div>
            <div style="width:100px;color:#aaa;font-size:9px;margin-left:6px;font-family:monospace;">
                {ts['start']:.1f}s~{ts['end']:.1f}s
            </div>
        </div>"""

    # 타임라인 눈금
    ruler = ""
    step = max(1, int(total // 10))
    for sec in range(0, int(total) + 1, step):
        pct = (sec / max(total, 0.1)) * 100
        ruler += f'<div style="position:absolute;left:{pct}%;color:#555;font-size:8px;font-family:monospace;">{sec}s</div>'

    return f"""
    <div style="background:#0a0a1a;border:1px solid #333;border-radius:8px;padding:12px;margin:10px 0;">
        <div style="color:#ccc;font-size:12px;font-weight:bold;margin-bottom:8px;">
            음성-자막 싱크 타임라인 (총 {total:.1f}초 / {len(timestamps)}개 자막)
        </div>
        <div style="position:relative;height:16px;margin:4px 36px 8px 36px;">
            {ruler}
        </div>
        {rows}
    </div>"""


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
    ref_file = st.file_uploader("주인공 참고 이미지 업로드", type=["png", "jpg", "jpeg"])
    if ref_file:
        st.session_state.reference_image = ref_file.getvalue()
        st.image(ref_file, caption="레퍼런스 이미지", use_container_width=True)
    st.divider()
    if st.button("API 연결 테스트"):
        if api:
            try:
                result = api.test_connection()
                if isinstance(result, dict):
                    for svc, status in result.items():
                        if isinstance(status, dict) and status.get("status") == "connected":
                            st.success(f"{svc}: 연결됨")
                        elif isinstance(status, dict):
                            st.warning(f"{svc}: {status.get('message', '실패')}")
                        elif isinstance(status, bool) and status:
                            st.success(f"{svc}: 연결됨")
                        else:
                            st.warning(f"{svc}: {status}")
                else:
                    st.success("API 연결 확인됨")
            except Exception as e:
                st.error(f"테스트 실패: {e}")
    st.divider()
    if st.button("전체 초기화", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "주제 추천", "롱폼 대본", "쇼츠 대본",
    "이미지 생성", "영상 변환", "음성 합성",
    "자막 설정", "최종 합치기"
])


# ════════════════════════════════════════════
# 탭1: 주제 추천
# ════════════════════════════════════════════
with tab1:
    st.header("떡상 주제 추천")
    col_kw, col_cnt = st.columns([3, 1])
    with col_kw:
        keyword = st.text_input("검색 키워드", value="시니어", key="search_keyword")
    with col_cnt:
        news_count = st.number_input("뉴스 수", 3, 20, 10, key="news_count")

    if st.button("떡상 주제 추천 받기", type="primary", use_container_width=True):
        if not api:
            st.error("API 미연결")
        else:
            with st.spinner("네이버 뉴스 분석 중..."):
                news = safe_naver_search(keyword, news_count)
                news_text = ""
                for item in news[:news_count]:
                    t = item.get("title", "") if isinstance(item, dict) else str(item)
                    d = item.get("description", "") if isinstance(item, dict) else ""
                    t = re.sub(r'<[^>]+>', '', str(t))
                    d = re.sub(r'<[^>]+>', '', str(d))
                    news_text += f"- {t}: {d}\n"
                with st.expander("수집된 뉴스 (디버그)"):
                    st.text(f"{len(news)}건\n{news_text or '(없음)'}")
                prompt = f"""아래 뉴스를 분석해서 유튜브 주제 10개 추천.
뉴스:
{news_text or '(없음)'}
키워드: {keyword}
형식만 출력. 다른 말 금지.
1번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ...
~10번까지"""
                try:
                    raw = api.generate(prompt)
                except Exception as e:
                    raw = ""
                    st.error(f"AI 실패: {e}")
                with st.expander("AI 응답 (디버그)"):
                    st.code(raw or "(없음)")
                topics = []
                if raw:
                    for line in raw.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        m = re.search(r'제목:\s*(.+?)(?:\||$)', line)
                        if m:
                            topics.append({
                                "title": m.group(1).strip().strip("*"),
                                "probability": (re.search(r'확률:\s*(.+?)(?:\||$)', line) or type('', (), {'group': lambda s, x: ''})()).group(1).strip() if re.search(r'확률:\s*(.+?)(?:\||$)', line) else "",
                                "source": (re.search(r'출처:\s*(.+?)(?:\||$)', line) or type('', (), {'group': lambda s, x: ''})()).group(1).strip() if re.search(r'출처:\s*(.+?)(?:\||$)', line) else "",
                                "alternative": (re.search(r'대안:\s*(.+?)(?:\||$)', line) or type('', (), {'group': lambda s, x: ''})()).group(1).strip() if re.search(r'대안:\s*(.+?)(?:\||$)', line) else "",
                                "tags": (re.search(r'태그:\s*(.+?)(?:\||$)', line) or type('', (), {'group': lambda s, x: ''})()).group(1).strip() if re.search(r'태그:\s*(.+?)(?:\||$)', line) else "",
                            })
                    st.session_state.topics_list = topics
                if not topics:
                    st.warning("파싱 실패. 디버그 확인.")

    if st.session_state.topics_list:
        st.subheader("추천 주제")
        for i, t in enumerate(st.session_state.topics_list):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{i+1}. {t['title']}**")
                    st.caption(f"확률: {t['probability']} | 출처: {t['source']} | 대안: {t['alternative']} | 태그: {t['tags']}")
                with c2:
                    if st.button("선택", key=f"pick_{i}", use_container_width=True):
                        st.session_state.selected_topic = t["title"]
                        sync_topic()
                        st.rerun()
    st.divider()
    manual = st.text_input("직접 주제 입력", key="manual_topic_input")
    if st.button("이 주제로 설정"):
        if manual.strip():
            st.session_state.selected_topic = manual.strip()
            sync_topic()
            st.rerun()


# ════════════════════════════════════════════
# 탭2: 롱폼 대본
# ════════════════════════════════════════════
with tab2:
    st.header("롱폼 대본 생성 (약 30분)")
    if st.session_state.selected_topic and not st.session_state.get("longform_topic"):
        st.session_state["longform_topic"] = st.session_state.selected_topic
    topic_long = st.text_input("영상 주제", key="longform_topic")
    if st.button("롱폼 대본 생성", type="primary", use_container_width=True):
        if not topic_long.strip():
            st.warning("주제 입력 필요")
        elif not api:
            st.error("API 필요")
        else:
            with st.spinner("대본 생성 중 (1~3분)..."):
                try:
                    from prompts.senior_longform import get_prompt
                    prompt = get_prompt(topic_long.strip())
                except Exception:
                    prompt = f"'{topic_long.strip()}' 30분 롱폼 대본. 분당 350자 이상.\n제목:\n태그:\n설명글:\n---대본시작---\n(본문)\n---대본끝---"
                try:
                    raw = api.generate(prompt)
                    st.session_state.longform_script = raw
                    meta = {}
                    for field, pattern in [("title", r'제목:\s*(.+)'), ("tags", r'태그:\s*(.+)'), ("description", r'설명글:\s*(.+)')]:
                        m = re.search(pattern, raw)
                        if m:
                            meta[field] = m.group(1).strip()
                    body_m = re.search(r'---대본시작---(.+?)---대본끝---', raw, re.DOTALL)
                    meta["body"] = body_m.group(1).strip() if body_m else raw
                    st.session_state.longform_metadata = meta
                except Exception as e:
                    st.error(f"실패: {e}")
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
            st.text_area("대본", body, height=500, key="long_body_disp")
            st.caption(f"{len(body)}자 | 약 {len(body)//350}분")
        st.download_button("대본 다운로드", st.session_state.longform_script,
                           f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "text/plain")


# ════════════════════════════════════════════
# 탭3: 쇼츠 대본 (3편)
# ════════════════════════════════════════════
with tab3:
    st.header("쇼츠 대본 (3편 / 40초 이내)")
    if st.session_state.selected_topic and not st.session_state.get("shorts_topic"):
        st.session_state["shorts_topic"] = st.session_state.selected_topic
    topic_shorts = st.text_input("쇼츠 주제", key="shorts_topic")
    if st.button("쇼츠 3편 생성", type="primary", use_container_width=True):
        if not topic_shorts.strip():
            st.warning("주제 입력")
        elif not api:
            st.error("API 필요")
        else:
            with st.spinner("3편 생성 중..."):
                prompt = f"""유튜브 쇼츠 대본 작가. 대주제: '{topic_shorts.strip()}'
3편 세트. 8~12문장(40초). 인사/구독/좋아요 금지. 첫문장 현장투척. 열린고리.
접속사: 근데/그래서/결국/알고보니. 습니다+까요 혼합. 영어/숫자 한글화. 마침표만.
이미지프롬프트: SD 2D anime style, 시작. 9:16. 장면=문장수.
형식만 출력:
=001=
제목: (50자이내)
상단제목첫째줄: (15자이내)
상단제목둘째줄: (15자이내)
설명글: (200자,해시태그3~5개)
태그: (15~20개)
순수대본: (문장나열)
=장면001=
대사: ...
프롬프트: SD 2D anime style, ...
=002= =003= 동일"""
                try:
                    raw = api.generate(prompt)
                    st.session_state.shorts_raw = raw
                    episodes = []
                    blocks = re.split(r'=00(\d)=', raw)
                    i = 1
                    while i < len(blocks) - 1:
                        n, c = blocks[i].strip(), blocks[i+1].strip()
                        ep = {"num": n, "raw": c}
                        for field, pat in [("title", r'제목:\s*(.+)'), ("top_line1", r'상단제목첫째줄:\s*(.+)'),
                                           ("top_line2", r'상단제목둘째줄:\s*(.+)'), ("tags", r'태그:\s*(.+)')]:
                            m = re.search(pat, c)
                            ep[field] = m.group(1).strip() if m else ""
                        if not ep["title"]:
                            ep["title"] = f"쇼츠 {n}편"
                        m = re.search(r'설명글:\s*(.+?)(?=\n태그:|\n=장면)', c, re.DOTALL)
                        ep["description"] = m.group(1).strip() if m else ""
                        m = re.search(r'순수대본:\s*(.+?)(?=\n=장면)', c, re.DOTALL)
                        ep["script"] = m.group(1).strip() if m else ""
                        scenes = re.findall(r'=장면\d+=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?=\n=장면|\n=00|$)', c, re.DOTALL)
                        ep["scenes"] = [{"dialogue": d.strip(), "prompt": p.strip()} for d, p in scenes]
                        episodes.append(ep)
                        i += 2
                    st.session_state.shorts_data = episodes
                except Exception as e:
                    st.error(f"실패: {e}")

    if st.session_state.shorts_data:
        with st.expander("AI 원본 (디버그)"):
            st.code(st.session_state.shorts_raw)
        for ep in st.session_state.shorts_data:
            st.divider()
            with st.container(border=True):
                tc, ttc = st.columns([3, 2])
                with tc:
                    st.subheader(f"편 {ep['num']}. {ep['title']}")
                with ttc:
                    if ep.get("top_line1"):
                        st.markdown(f"**상단제목:** {ep['top_line1']} / {ep.get('top_line2','')}")
                if ep.get("tags"):
                    with st.container(border=True):
                        st.markdown("**태그**")
                        st.write(ep["tags"])
                if ep.get("description"):
                    with st.container(border=True):
                        st.markdown("**설명글**")
                        st.write(ep["description"])
                with st.container(border=True):
                    st.markdown("**대본 (40초)**")
                    st.write(ep.get("script", "(없음)"))
                    if ep.get("script"):
                        st.caption(f"{len(ep['script'])}자 | ~{min(40, max(10, len(ep['script'])//7))}초")
                if ep.get("scenes"):
                    with st.expander(f"장면 프롬프트 ({len(ep['scenes'])}개)"):
                        for j, s in enumerate(ep["scenes"]):
                            st.markdown(f"**장면 {j+1}**")
                            st.write(f"대사: {s['dialogue']}")
                            st.code(s["prompt"], language="text")
        st.download_button("3편 다운로드", st.session_state.shorts_raw,
                           f"shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "text/plain")


# ════════════════════════════════════════════
# 탭4: 이미지 생성
# ════════════════════════════════════════════
with tab4:
    st.header("이미지 생성")
    it_l, it_s = st.tabs(["롱폼 (16:9)", "쇼츠 (9:16)"])
    with it_l:
        st.subheader("롱폼 이미지")
        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            paras = [p.strip() for p in body.split("\n\n") if p.strip()] or [p.strip() for p in body.split("\n") if p.strip()]
            st.info(f"{len(paras)}개 문단")
            if st.button("프롬프트 생성", key="gl_p"):
                with st.spinner("생성 중..."):
                    try:
                        r = api.generate(f"대본 문단별 이미지 프롬프트. SD 2D anime style 시작. 16:9.\n[장면N]\n내용요약: ...\n프롬프트: ...\n\n대본:\n{body[:3000]}")
                        st.session_state["lp_raw"] = r
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("lp_raw"):
                st.text_area("프롬프트", st.session_state["lp_raw"], height=400, key="lp_disp")
                prompts = re.findall(r'프롬프트:\s*(SD 2D anime style,.+?)(?=\n\[장면|\n$|$)', st.session_state["lp_raw"], re.DOTALL)
                if prompts and st.button("이미지 생성", key="gl_i"):
                    prog = st.progress(0)
                    gen = []
                    for idx, p in enumerate(prompts):
                        try:
                            gen.append({"prompt": p.strip(), "url": api.generate_image(p.strip(), aspect_ratio="16:9"), "index": idx+1})
                        except Exception as e:
                            gen.append({"prompt": p.strip(), "url": None, "error": str(e), "index": idx+1})
                        prog.progress((idx+1)/len(prompts))
                    st.session_state.generated_images_longform = gen
            if st.session_state.generated_images_longform:
                cols = st.columns(3)
                for idx, img in enumerate(st.session_state.generated_images_longform):
                    with cols[idx % 3]:
                        st.caption(f"장면 {img['index']}")
                        if img.get("url"):
                            st.image(img["url"], use_container_width=True)
                        else:
                            st.error(img.get("error", ""))
        else:
            st.warning("롱폼 대본 먼저 생성하세요.")

    with it_s:
        st.subheader("쇼츠 이미지")
        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                with st.container(border=True):
                    st.markdown(f"**편 {ep['num']}. {ep['title']}**")
                    if ep.get("scenes"):
                        for j, s in enumerate(ep["scenes"]):
                            st.caption(f"장면{j+1}: {s['dialogue'][:30]}...")
                            st.code(s["prompt"], language="text")
                        if st.button(f"편{ep['num']} 생성", key=f"gsi_{ep['num']}"):
                            prog = st.progress(0)
                            imgs = []
                            for j, s in enumerate(ep["scenes"]):
                                try:
                                    imgs.append({"url": api.generate_image(s["prompt"], aspect_ratio="9:16"), "scene": j+1, "dialogue": s["dialogue"]})
                                except Exception as e:
                                    imgs.append({"url": None, "scene": j+1, "error": str(e), "dialogue": s["dialogue"]})
                                prog.progress((j+1)/len(ep["scenes"]))
                            st.session_state[f"si_ep{ep['num']}"] = imgs
                        if st.session_state.get(f"si_ep{ep['num']}"):
                            cols = st.columns(4)
                            for j, img in enumerate(st.session_state[f"si_ep{ep['num']}"]):
                                with cols[j % 4]:
                                    st.caption(f"장면{img['scene']}")
                                    if img.get("url"):
                                        st.image(img["url"], use_container_width=True)
                                    else:
                                        st.error(img.get("error", ""))
        else:
            st.warning("쇼츠 대본 먼저 생성하세요.")


# ════════════════════════════════════════════
# 탭5: 영상 변환
# ════════════════════════════════════════════
with tab5:
    st.header("영상 변환 (Kie AI)")
    if api:
        img_url = st.text_input("이미지 URL", key="vid_url")
        if st.button("변환") and img_url.strip():
            with st.spinner("변환 중..."):
                try:
                    tid = api.kie.create_task(img_url.strip())
                    r = api.kie.wait_for_completion(tid)
                    if r:
                        st.success("완료!")
                        st.video(r)
                    else:
                        st.error("실패")
                except Exception as e:
                    st.error(str(e))


# ════════════════════════════════════════════
# 탭6: 음성 합성 + 자동 싱크
# ════════════════════════════════════════════
with tab6:
    st.header("음성 합성 + 자막 자동 싱크")
    st.caption("TTS 음성을 생성하면 문장별 타임스탬프가 자동 추출되고, SRT 자막 파일이 자동으로 만들어집니다.")

    tts_tab_long, tts_tab_shorts = st.tabs(["롱폼 음성", "쇼츠 음성"])

    # ── 롱폼 TTS ──
    with tts_tab_long:
        st.subheader("롱폼 음성 합성 + 자막 싱크")
        long_body = st.session_state.longform_metadata.get("body", "") if st.session_state.longform_metadata else ""
        tts_long_text = st.text_area("합성할 텍스트 (롱폼)", value=long_body, height=200, key="tts_long_txt")

        if st.button("롱폼 음성 합성 + 싱크 생성", type="primary", key="tts_long_btn"):
            if not tts_long_text.strip():
                st.warning("텍스트 필요")
            elif api:
                with st.spinner("음성 합성 + 타임스탬프 추출 중..."):
                    try:
                        result = api.inworld.synthesize(tts_long_text.strip())
                        audio, timestamps, error = None, None, None
                        if isinstance(result, tuple):
                            if len(result) == 3:
                                audio, timestamps, error = result
                            elif len(result) == 2:
                                audio, timestamps = result
                        else:
                            audio = result

                        if error:
                            st.error(f"합성 오류: {error}")
                        elif audio:
                            st.success("음성 합성 완료!")
                            audio_bytes = base64.b64decode(audio) if isinstance(audio, str) else audio
                            st.session_state.tts_longform_audio = audio_bytes
                            st.audio(audio_bytes, format="audio/mp3")

                            # 타임스탬프 처리
                            parsed_ts = parse_tts_timestamps(timestamps, tts_long_text.strip())
                            st.session_state.tts_longform_timestamps = parsed_ts

                            # SRT 생성
                            srt = timestamps_to_srt(parsed_ts)
                            st.session_state.tts_longform_srt = srt

                            st.success(f"자막 싱크 완료! {len(parsed_ts)}개 자막 생성됨")
                    except Exception as e:
                        st.error(f"실패: {e}")

        # 결과 표시
        if st.session_state.tts_longform_audio:
            st.divider()
            st.subheader("싱크 결과")

            # 타임라인 시각화
            if st.session_state.tts_longform_timestamps:
                ts = st.session_state.tts_longform_timestamps
                total_dur = ts[-1]["end"] if ts else 0
                timeline_html = build_sync_timeline_html(ts, total_dur)
                st.components.v1.html(timeline_html, height=50 + len(ts) * 34, scrolling=True)

                # 자막 테이블
                with st.expander(f"자막 상세 ({len(ts)}개)", expanded=True):
                    for i, t in enumerate(ts):
                        c1, c2, c3 = st.columns([1, 2, 5])
                        with c1:
                            st.caption(f"#{i+1}")
                        with c2:
                            st.caption(f"{t['start']:.1f}s ~ {t['end']:.1f}s")
                        with c3:
                            st.write(t["text"])

            # SRT 다운로드
            if st.session_state.tts_longform_srt:
                st.text_area("SRT 미리보기", st.session_state.tts_longform_srt, height=200, key="srt_long_prev")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button("SRT 자막 다운로드", st.session_state.tts_longform_srt,
                                       f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt", "text/plain")
                with col_dl2:
                    st.download_button("MP3 다운로드", st.session_state.tts_longform_audio,
                                       f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3", "audio/mp3")

    # ── 쇼츠 TTS (편별) ──
    with tts_tab_shorts:
        st.subheader("쇼츠 편별 음성 합성 + 자막 싱크")

        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                with st.container(border=True):
                    st.markdown(f"**편 {ep['num']}. {ep['title']}**")
                    script = ep.get("script", "")
                    st.text_area(f"편{ep['num']} 대본", script, height=100, key=f"tts_s_txt_{ep['num']}", disabled=True)

                    if st.button(f"편 {ep['num']} 음성+싱크 생성", key=f"tts_s_btn_{ep['num']}"):
                        if not script.strip():
                            st.warning("대본 없음")
                        elif api:
                            with st.spinner(f"편{ep['num']} 합성 중..."):
                                try:
                                    result = api.inworld.synthesize(script.strip())
                                    audio, timestamps, error = None, None, None
                                    if isinstance(result, tuple):
                                        if len(result) == 3:
                                            audio, timestamps, error = result
                                        elif len(result) == 2:
                                            audio, timestamps = result
                                    else:
                                        audio = result

                                    if error:
                                        st.error(f"오류: {error}")
                                    elif audio:
                                        audio_bytes = base64.b64decode(audio) if isinstance(audio, str) else audio
                                        st.session_state.tts_shorts_audio[ep['num']] = audio_bytes

                                        parsed_ts = parse_tts_timestamps(timestamps, script.strip())
                                        st.session_state.tts_shorts_timestamps[ep['num']] = parsed_ts

                                        srt = timestamps_to_srt(parsed_ts)
                                        st.session_state.tts_shorts_srt[ep['num']] = srt

                                        st.success(f"편{ep['num']} 완료! {len(parsed_ts)}개 자막")
                                except Exception as e:
                                    st.error(str(e))

                    # 편별 결과
                    if st.session_state.tts_shorts_audio.get(ep['num']):
                        st.audio(st.session_state.tts_shorts_audio[ep['num']], format="audio/mp3")

                        ts = st.session_state.tts_shorts_timestamps.get(ep['num'], [])
                        if ts:
                            total_dur = ts[-1]["end"] if ts else 0
                            tl_html = build_sync_timeline_html(ts, total_dur)
                            st.components.v1.html(tl_html, height=50 + len(ts) * 34, scrolling=True)

                        srt = st.session_state.tts_shorts_srt.get(ep['num'], "")
                        if srt:
                            with st.expander("SRT 미리보기"):
                                st.code(srt)
                            c1, c2 = st.columns(2)
                            with c1:
                                st.download_button(f"편{ep['num']} SRT", srt,
                                                   f"shorts_ep{ep['num']}.srt", "text/plain", key=f"dl_srt_{ep['num']}")
                            with c2:
                                st.download_button(f"편{ep['num']} MP3", st.session_state.tts_shorts_audio[ep['num']],
                                                   f"shorts_ep{ep['num']}.mp3", "audio/mp3", key=f"dl_mp3_{ep['num']}")

            # 전체 일괄
            st.divider()
            if st.button("쇼츠 3편 전체 음성+싱크 일괄 생성", type="primary", key="tts_all_shorts"):
                for ep in st.session_state.shorts_data:
                    script = ep.get("script", "")
                    if script.strip() and api:
                        st.write(f"편{ep['num']} 합성 중...")
                        try:
                            result = api.inworld.synthesize(script.strip())
                            audio, timestamps, error = None, None, None
                            if isinstance(result, tuple):
                                if len(result) == 3:
                                    audio, timestamps, error = result
                                elif len(result) == 2:
                                    audio, timestamps = result
                            else:
                                audio = result
                            if audio and not error:
                                audio_bytes = base64.b64decode(audio) if isinstance(audio, str) else audio
                                st.session_state.tts_shorts_audio[ep['num']] = audio_bytes
                                parsed_ts = parse_tts_timestamps(timestamps, script.strip())
                                st.session_state.tts_shorts_timestamps[ep['num']] = parsed_ts
                                st.session_state.tts_shorts_srt[ep['num']] = timestamps_to_srt(parsed_ts)
                                st.success(f"편{ep['num']} 완료")
                        except Exception as e:
                            st.error(f"편{ep['num']} 실패: {e}")
                st.rerun()
        else:
            st.warning("쇼츠 대본 먼저 생성하세요.")


# ════════════════════════════════════════════
# 탭7: 자막 설정
# ════════════════════════════════════════════
with tab7:
    st.header("자막 설정")
    st.caption("롱폼/쇼츠 자막 스타일을 각각 설정하고 실시간 미리보기로 확인하세요. 음성 합성 탭에서 생성된 SRT에 이 스타일이 적용됩니다.")

    sub_tl, sub_ts = st.tabs(["롱폼 자막 (16:9)", "쇼츠 자막 (9:16)"])

    with sub_tl:
        st.subheader("롱폼 자막 설정")
        ctrl, prev = st.columns([1, 1])
        with ctrl:
            long_settings = subtitle_settings_ui("long", "16:9")
            st.session_state.sub_settings_longform = long_settings
        with prev:
            st.markdown("**실시간 미리보기**")
            lpt = st.text_input("미리보기 텍스트", "자막 미리보기 샘플입니다", key="lpt")
            st.components.v1.html(build_subtitle_preview_html(long_settings, lpt, "16:9"), height=360)
            st.divider()
            with st.container(border=True):
                st.caption(f"글씨체: {long_settings['font']} {long_settings['size']}px | "
                           f"{'굵게 ' if long_settings['bold'] else ''}{'기울임 ' if long_settings['italic'] else ''}"
                           f"| 자간:{long_settings['letter_spacing']} 행간:{long_settings['line_height']}")
                st.caption(f"색상: {long_settings['color']} 외곽:{long_settings['outline_color']}({long_settings['outline_width']}px) "
                           f"그림자:{long_settings['shadow_color']}({long_settings['shadow_blur']}px) 배경:{long_settings['bg_opacity']}%")
                st.caption(f"위치: {long_settings['position']} {long_settings['align']} | "
                           f"여백 상:{long_settings['pos_top']} 하:{long_settings['pos_bottom']} 좌:{long_settings['pos_left']} 우:{long_settings['pos_right']}px")

            # 실제 자막 싱크 미리보기
            if st.session_state.tts_longform_timestamps:
                st.divider()
                st.markdown("**실제 자막 싱크 미리보기**")
                ts = st.session_state.tts_longform_timestamps
                sel = st.slider("자막 번호", 1, len(ts), 1, key="long_sub_sel")
                selected_ts = ts[sel - 1]
                st.caption(f"#{sel} | {selected_ts['start']:.1f}s ~ {selected_ts['end']:.1f}s")
                st.components.v1.html(build_subtitle_preview_html(long_settings, selected_ts["text"], "16:9"), height=360)

    with sub_ts:
        st.subheader("쇼츠 자막 설정")
        ctrl2, prev2 = st.columns([1, 1])
        with ctrl2:
            shorts_settings = subtitle_settings_ui("shorts", "9:16")
            st.session_state.sub_settings_shorts = shorts_settings
        with prev2:
            st.markdown("**실시간 미리보기**")
            spt = st.text_input("미리보기 텍스트", "쇼츠 자막 미리보기", key="spt")
            st.components.v1.html(build_subtitle_preview_html(shorts_settings, spt, "9:16"), height=540)
            st.divider()
            with st.container(border=True):
                st.caption(f"글씨체: {shorts_settings['font']} {shorts_settings['size']}px | "
                           f"{'굵게 ' if shorts_settings['bold'] else ''}{'기울임 ' if shorts_settings['italic'] else ''}")
                st.caption(f"위치: {shorts_settings['position']} {shorts_settings['align']} | "
                           f"여백 상:{shorts_settings['pos_top']} 하:{shorts_settings['pos_bottom']} 좌:{shorts_settings['pos_left']} 우:{shorts_settings['pos_right']}px")

            # 쇼츠 자막 싱크 미리보기
            if st.session_state.tts_shorts_timestamps:
                st.divider()
                st.markdown("**편별 자막 싱크 미리보기**")
                ep_nums = list(st.session_state.tts_shorts_timestamps.keys())
                if ep_nums:
                    sel_ep = st.selectbox("편 선택", ep_nums, key="shorts_sub_ep")
                    ts = st.session_state.tts_shorts_timestamps.get(sel_ep, [])
                    if ts:
                        sel2 = st.slider("자막 번호", 1, len(ts), 1, key="shorts_sub_sel")
                        selected_ts = ts[sel2 - 1]
                        st.caption(f"편{sel_ep} #{sel2} | {selected_ts['start']:.1f}s ~ {selected_ts['end']:.1f}s")
                        st.components.v1.html(build_subtitle_preview_html(shorts_settings, selected_ts["text"], "9:16"), height=540)

    # 글씨체 갤러리
    st.divider()
    st.subheader("글씨체 미리보기 갤러리")
    FONTS = ["Noto Sans KR","Noto Serif KR","Black Han Sans","Jua","Do Hyeon","Gothic A1","Sunflower",
             "Gaegu","Hi Melody","Song Myung","Stylish","Gugi","Gamja Flower","East Sea Dokdo",
             "Cute Font","Yeon Sung","Poor Story","Single Day","Black And White Picture","Dokdo"]
    gt = st.text_input("갤러리 텍스트", "떡상 콘텐츠 팩토리", key="gt")
    links = "".join([f'<link href="https://fonts.googleapis.com/css2?family={f.replace(" ","+")}&display=swap" rel="stylesheet">' for f in FONTS])
    cards = "".join([f"""<div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:12px 16px;margin:4px;display:inline-block;min-width:200px;">
        <div style="color:#888;font-size:10px;margin-bottom:4px;font-family:monospace;">{f}</div>
        <div style="font-family:'{f}',sans-serif;font-size:18px;color:#fff;-webkit-text-stroke:1px #000;paint-order:stroke fill;text-shadow:2px 2px 4px #000;">{gt}</div></div>""" for f in FONTS])
    st.components.v1.html(f"{links}<div style='display:flex;flex-wrap:wrap;gap:6px;padding:10px;'>{cards}</div>", height=500, scrolling=True)


# ════════════════════════════════════════════
# 탭8: 최종 합치기
# ════════════════════════════════════════════
with tab8:
    st.header("최종 합치기")
    st.info("Streamlit Cloud에서는 FFmpeg 직접 실행 불가. 아래 파일들을 다운로드해서 로컬에서 합성하세요.")

    st.subheader("현재 상태")
    checks = {
        "선택된 주제": st.session_state.selected_topic or "없음",
        "롱폼 대본": "생성됨" if st.session_state.longform_metadata else "없음",
        "쇼츠 대본": f"{len(st.session_state.shorts_data)}편" if st.session_state.shorts_data else "없음",
        "롱폼 이미지": f"{len(st.session_state.generated_images_longform)}장" if st.session_state.generated_images_longform else "없음",
        "롱폼 음성": "생성됨" if st.session_state.tts_longform_audio else "없음",
        "롱폼 자막(SRT)": "생성됨" if st.session_state.tts_longform_srt else "없음",
        "쇼츠 음성": f"{len(st.session_state.tts_shorts_audio)}편" if st.session_state.tts_shorts_audio else "없음",
        "쇼츠 자막(SRT)": f"{len(st.session_state.tts_shorts_srt)}편" if st.session_state.tts_shorts_srt else "없음",
        "롱폼 자막 설정": "설정됨" if st.session_state.sub_settings_longform else "없음",
        "쇼츠 자막 설정": "설정됨" if st.session_state.sub_settings_shorts else "없음",
        "레퍼런스 이미지": "업로드됨" if st.session_state.reference_image else "없음",
    }
    for k, v in checks.items():
        (st.success if v != "없음" else st.warning)(f"{k}: {v}")

    st.divider()
    st.subheader("전체 설정 내보내기")
    if any([st.session_state.sub_settings_longform, st.session_state.sub_settings_shorts,
            st.session_state.tts_longform_srt, st.session_state.tts_shorts_srt]):
        export = {
            "subtitle_longform": st.session_state.sub_settings_longform,
            "subtitle_shorts": st.session_state.sub_settings_shorts,
            "srt_longform": st.session_state.tts_longform_srt,
            "srt_shorts": dict(st.session_state.tts_shorts_srt),
            "timestamps_longform": st.session_state.tts_longform_timestamps,
            "timestamps_shorts": dict(st.session_state.tts_shorts_timestamps),
        }
        st.download_button("전체 설정 JSON 다운로드",
                           json.dumps(export, ensure_ascii=False, indent=2, default=str),
                           f"settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")

    # FFmpeg 명령어 예시
    st.divider()
    st.subheader("로컬 합성 가이드")
    with st.expander("FFmpeg 자막 합성 명령어 예시"):
        if st.session_state.sub_settings_longform:
            s = st.session_state.sub_settings_longform
            force_style = f"FontName={s.get('font','Noto Sans KR')},FontSize={s.get('size',48)},PrimaryColour=&H00{s.get('color','#FFFFFF')[5:7]}{s.get('color','#FFFFFF')[3:5]}{s.get('color','#FFFFFF')[1:3]}&,OutlineColour=&H00{s.get('outline_color','#000000')[5:7]}{s.get('outline_color','#000000')[3:5]}{s.get('outline_color','#000000')[1:3]}&,Outline={s.get('outline_width',2)},Shadow={s.get('shadow_blur',4)},MarginV={s.get('pos_bottom',40)},Alignment=2,Bold={'1' if s.get('bold') else '0'}"
            st.code(f"""ffmpeg -i video.mp4 -i audio.mp3 \\
  -vf "subtitles=longform.srt:force_style='{force_style}'" \\
  -c:v libx264 -c:a aac output_longform.mp4""", language="bash")
        else:
            st.code("""ffmpeg -i video.mp4 -i audio.mp3 \\
  -vf "subtitles=longform.srt" \\
  -c:v libx264 -c:a aac output.mp4""", language="bash")
