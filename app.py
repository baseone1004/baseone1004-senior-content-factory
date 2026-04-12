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


# ── 자막 미리보기 HTML 생성 함수 ──
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
    pos_top = settings.get("pos_top", None)
    pos_bottom = settings.get("pos_bottom", 40)
    pos_left = settings.get("pos_left", 20)
    pos_right = settings.get("pos_right", 20)
    align = settings.get("align", "center")
    bold = settings.get("bold", True)
    italic = settings.get("italic", False)
    letter_spacing = settings.get("letter_spacing", 0)
    line_height = settings.get("line_height", 1.5)

    if ratio == "9:16":
        cw, ch = 270, 480
        display_size = max(10, size // 4)
    else:
        cw, ch = 540, 304
        display_size = max(10, size // 3)

    # 위치 CSS
    position = settings.get("position", "하단")
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

    google_font_link = f'<link href="https://fonts.googleapis.com/css2?family={font.replace(" ", "+")}&display=swap" rel="stylesheet">'

    html = f"""
    {google_font_link}
    <div style="
        position: relative;
        width: {cw}px;
        height: {ch}px;
        background: linear-gradient(180deg, #0a0a1a 0%, #1a1a3e 30%, #0a0a1a 60%, #1a0a2e 100%);
        border-radius: 12px;
        overflow: hidden;
        margin: 10px auto;
        border: 1px solid #444;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    ">
        <div style="position:absolute;top:0;left:0;right:0;bottom:0;
            background: radial-gradient(ellipse at 30% 40%, rgba(100,100,200,0.08) 0%, transparent 60%),
                        radial-gradient(ellipse at 70% 60%, rgba(200,100,100,0.06) 0%, transparent 60%);
            pointer-events:none;"></div>

        <div style="position:absolute;top:12px;left:12px;display:flex;gap:4px;">
            <div style="width:8px;height:8px;border-radius:50%;background:#ff5f57;"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:#febc2e;"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:#28c840;"></div>
        </div>

        <div style="position:absolute;top:10px;right:12px;color:#ffffff30;font-size:9px;font-family:monospace;">
            {ratio} PREVIEW
        </div>

        <div style="
            position:absolute;
            top:45%;left:50%;transform:translate(-50%,-50%);
            color:#ffffff08;font-size:40px;font-weight:bold;pointer-events:none;
        ">VIDEO</div>

        <div style="
            position: absolute;
            {pos_css}
            left: {pos_left}px;
            right: {pos_right}px;
            text-align: {align};
            z-index: 10;
        ">
            <span style="
                font-family: '{font}', 'Noto Sans KR', sans-serif;
                font-size: {display_size}px;
                font-weight: {fw};
                font-style: {fs};
                color: {color};
                -webkit-text-stroke: {max(1, outline_w)}px {outline_color};
                paint-order: stroke fill;
                text-shadow: {shadow_blur}px {shadow_blur}px {shadow_blur * 2}px {shadow_color},
                             -{shadow_blur}px -{shadow_blur}px {shadow_blur * 2}px {shadow_color};
                background: {bg_rgba};
                padding: 6px 14px;
                border-radius: 6px;
                letter-spacing: {letter_spacing}px;
                line-height: {line_height};
                display: inline-block;
                max-width: 100%;
                word-break: keep-all;
            ">{preview_text}</span>
        </div>
    </div>
    """
    return html


# ── 자막 설정 UI 빌더 ──
def subtitle_settings_ui(prefix, ratio="16:9"):
    FONT_LIST = [
        "Noto Sans KR",
        "Noto Serif KR",
        "Black Han Sans",
        "Jua",
        "Do Hyeon",
        "Gothic A1",
        "Sunflower",
        "Gaegu",
        "Hi Melody",
        "Song Myung",
        "Stylish",
        "Gugi",
        "Gamja Flower",
        "East Sea Dokdo",
        "Cute Font",
        "Yeon Sung",
        "Poor Story",
        "Single Day",
        "Black And White Picture",
        "Dokdo",
    ]

    settings = {}

    st.markdown("**글씨체 선택**")
    font_col1, font_col2 = st.columns([2, 1])
    with font_col1:
        settings["font"] = st.selectbox(
            "글씨체", FONT_LIST,
            index=0, key=f"{prefix}_font",
            help="구글 폰트 기반 한글 글씨체"
        )
    with font_col2:
        settings["size"] = st.number_input(
            "크기 (px)", min_value=16, max_value=120, value=48,
            step=1, key=f"{prefix}_size"
        )

    st.markdown("**글자 스타일**")
    style_cols = st.columns(4)
    with style_cols[0]:
        settings["bold"] = st.checkbox("굵게", value=True, key=f"{prefix}_bold")
    with style_cols[1]:
        settings["italic"] = st.checkbox("기울임", value=False, key=f"{prefix}_italic")
    with style_cols[2]:
        settings["letter_spacing"] = st.number_input(
            "자간", min_value=-5, max_value=20, value=0,
            step=1, key=f"{prefix}_ls"
        )
    with style_cols[3]:
        settings["line_height"] = st.number_input(
            "행간", min_value=1.0, max_value=3.0, value=1.5,
            step=0.1, key=f"{prefix}_lh"
        )

    st.markdown("**색상 설정**")
    color_cols = st.columns(4)
    with color_cols[0]:
        settings["color"] = st.color_picker("글자색", "#FFFFFF", key=f"{prefix}_color")
    with color_cols[1]:
        settings["outline_color"] = st.color_picker("외곽선", "#000000", key=f"{prefix}_oc")
    with color_cols[2]:
        settings["shadow_color"] = st.color_picker("그림자", "#000000", key=f"{prefix}_sc")
    with color_cols[3]:
        settings["bg_color"] = st.color_picker("배경색", "#000000", key=f"{prefix}_bgc")

    st.markdown("**외곽선 / 그림자 / 배경**")
    effect_cols = st.columns(3)
    with effect_cols[0]:
        settings["outline_width"] = st.slider(
            "외곽선 두께", 0, 8, 2, step=1, key=f"{prefix}_ow"
        )
    with effect_cols[1]:
        settings["shadow_blur"] = st.slider(
            "그림자 번짐", 0, 20, 4, step=1, key=f"{prefix}_sb"
        )
    with effect_cols[2]:
        settings["bg_opacity"] = st.slider(
            "배경 투명도 (%)", 0, 100, 0, step=5, key=f"{prefix}_bgo",
            help="0 = 투명, 100 = 불투명"
        )

    st.markdown("**위치 설정**")
    settings["position"] = st.radio(
        "기본 위치", ["상단", "중앙", "하단"],
        index=2, horizontal=True, key=f"{prefix}_pos"
    )

    st.markdown("**상하좌우 미세조절 (px)**")
    pos_cols = st.columns(4)
    with pos_cols[0]:
        settings["pos_top"] = st.number_input(
            "위 여백", min_value=0, max_value=500, value=30,
            step=1, key=f"{prefix}_mt"
        )
    with pos_cols[1]:
        settings["pos_bottom"] = st.number_input(
            "아래 여백", min_value=0, max_value=500, value=40,
            step=1, key=f"{prefix}_mb"
        )
    with pos_cols[2]:
        settings["pos_left"] = st.number_input(
            "왼쪽 여백", min_value=0, max_value=300, value=20,
            step=1, key=f"{prefix}_ml"
        )
    with pos_cols[3]:
        settings["pos_right"] = st.number_input(
            "오른쪽 여백", min_value=0, max_value=300, value=20,
            step=1, key=f"{prefix}_mr"
        )

    st.markdown("**정렬**")
    settings["align"] = st.radio(
        "텍스트 정렬", ["left", "center", "right"],
        index=1, horizontal=True, key=f"{prefix}_align",
        format_func=lambda x: {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}[x]
    )

    return settings


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
                elif isinstance(result, str):
                    st.info(result)
                else:
                    st.success("API 연결 확인됨")
            except Exception as e:
                st.error(f"테스트 실패: {e}")
    st.divider()
    if st.button("전체 초기화", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ── 메인 탭 ──
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
    col_keyword, col_count = st.columns([3, 1])
    with col_keyword:
        keyword = st.text_input("검색 키워드", value="시니어", key="search_keyword")
    with col_count:
        news_count = st.number_input("뉴스 수", min_value=3, max_value=20, value=10, key="news_count")

    if st.button("떡상 주제 추천 받기", type="primary", use_container_width=True):
        if not api:
            st.error("API가 연결되지 않았습니다")
        else:
            with st.spinner("네이버 뉴스 분석 중..."):
                news = safe_naver_search(keyword, news_count)
                news_text = ""
                if news:
                    for item in news[:news_count]:
                        title = item.get("title", "") if isinstance(item, dict) else str(item)
                        desc = item.get("description", "") if isinstance(item, dict) else ""
                        title = re.sub(r'<[^>]+>', '', str(title))
                        desc = re.sub(r'<[^>]+>', '', str(desc))
                        news_text += f"- {title}: {desc}\n"

                with st.expander("수집된 뉴스 데이터 (디버그)"):
                    st.text(f"뉴스 항목 수: {len(news)}")
                    st.text(news_text if news_text else "(뉴스 없음)")

                prompt = f"""아래 뉴스 트렌드를 분석해서 유튜브 영상 주제 10개를 추천해줘.

뉴스 트렌드:
{news_text if news_text else '(뉴스 없음 - 일반 트렌드 기반 추천)'}

키워드: {keyword}

반드시 아래 형식으로만 출력해. 다른 말 붙이지 마.

1번|제목: (주제 제목)|확률: (떡상 확률 퍼센트)|출처: (관련 뉴스 키워드)|대안: (비슷한 대안 주제)|태그: (관련 태그 3개 쉼표 구분)
2번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ...
10번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ..."""

                try:
                    raw = api.generate(prompt)
                except Exception as e:
                    raw = ""
                    st.error(f"AI 생성 실패: {e}")

                with st.expander("AI 원본 응답 (디버그)"):
                    st.code(raw if raw else "(응답 없음)")

                topics = []
                if raw:
                    lines = raw.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        m = re.search(r'제목:\s*(.+?)(?:\||$)', line)
                        if m:
                            title_val = m.group(1).strip().strip("*").strip()
                            prob_m = re.search(r'확률:\s*(.+?)(?:\||$)', line)
                            source_m = re.search(r'출처:\s*(.+?)(?:\||$)', line)
                            alt_m = re.search(r'대안:\s*(.+?)(?:\||$)', line)
                            tag_m = re.search(r'태그:\s*(.+?)(?:\||$)', line)
                            topics.append({
                                "title": title_val,
                                "probability": prob_m.group(1).strip() if prob_m else "",
                                "source": source_m.group(1).strip() if source_m else "",
                                "alternative": alt_m.group(1).strip() if alt_m else "",
                                "tags": tag_m.group(1).strip() if tag_m else "",
                            })
                    st.session_state.topics_list = topics
                if not topics:
                    st.warning("주제 파싱에 실패했습니다. 디버그 창을 확인하세요.")

    if st.session_state.topics_list:
        st.subheader("추천 주제 목록")
        for i, t in enumerate(st.session_state.topics_list):
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{i+1}. {t['title']}**")
                    st.caption(f"떡상 확률: {t['probability']} | 출처: {t['source']}")
                    st.caption(f"대안: {t['alternative']} | 태그: {t['tags']}")
                with col2:
                    if st.button("선택", key=f"pick_{i}", use_container_width=True):
                        st.session_state.selected_topic = t["title"]
                        sync_topic()
                        st.rerun()

    st.divider()
    st.subheader("수동 주제 입력")
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
    st.header("롱폼 대본 생성 (약 30분 분량)")
    if st.session_state.selected_topic and not st.session_state.get("longform_topic"):
        st.session_state["longform_topic"] = st.session_state.selected_topic
    topic_long = st.text_input("영상 주제", key="longform_topic")

    if st.button("롱폼 대본 생성", type="primary", use_container_width=True):
        if not topic_long.strip():
            st.warning("주제를 입력하세요")
        elif not api:
            st.error("API 연결 필요")
        else:
            with st.spinner("롱폼 대본 생성 중... (1~3분 소요)"):
                try:
                    from prompts.senior_longform import get_prompt
                    prompt = get_prompt(topic_long.strip())
                except Exception:
                    prompt = f"""'{topic_long.strip()}' 주제로 유튜브 30분 분량 롱폼 대본을 작성해줘.
분당 350자 이상, 총 10500자 이상.
형식:
제목: (제목)
태그: (태그 15~20개 쉼표 구분)
설명글: (200자 내외, 해시태그 3~5개)
---대본시작---
(대본 본문)
---대본끝---"""
                try:
                    raw = api.generate(prompt)
                    st.session_state.longform_script = raw
                    meta = {}
                    title_m = re.search(r'제목:\s*(.+)', raw)
                    if title_m:
                        meta["title"] = title_m.group(1).strip()
                    tag_m = re.search(r'태그:\s*(.+)', raw)
                    if tag_m:
                        meta["tags"] = tag_m.group(1).strip()
                    desc_m = re.search(r'설명글:\s*(.+)', raw)
                    if desc_m:
                        meta["description"] = desc_m.group(1).strip()
                    body_m = re.search(r'---대본시작---(.+?)---대본끝---', raw, re.DOTALL)
                    if body_m:
                        meta["body"] = body_m.group(1).strip()
                    else:
                        meta["body"] = raw
                    st.session_state.longform_metadata = meta
                except Exception as e:
                    st.error(f"생성 실패: {e}")

    if st.session_state.longform_metadata:
        meta = st.session_state.longform_metadata
        with st.container(border=True):
            st.subheader(meta.get("title", "제목 없음"))
            if meta.get("tags"):
                st.caption(f"태그: {meta['tags']}")
            if meta.get("description"):
                st.info(meta["description"])
        with st.expander("대본 전문 보기", expanded=True):
            body = meta.get("body", "")
            st.text_area("대본", value=body, height=500, key="longform_body_display")
            st.caption(f"글자 수: {len(body)}자 | 예상 분량: 약 {len(body)//350}분")
        st.download_button(
            "대본 다운로드 (TXT)", data=st.session_state.longform_script,
            file_name=f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain"
        )


# ════════════════════════════════════════════
# 탭3: 쇼츠 대본 (3편 세트)
# ════════════════════════════════════════════
with tab3:
    st.header("쇼츠 대본 생성 (3편 세트 / 각 40초 이내)")
    if st.session_state.selected_topic and not st.session_state.get("shorts_topic"):
        st.session_state["shorts_topic"] = st.session_state.selected_topic
    topic_shorts = st.text_input("쇼츠 주제", key="shorts_topic")

    if st.button("쇼츠 3편 세트 생성", type="primary", use_container_width=True):
        if not topic_shorts.strip():
            st.warning("주제를 입력하세요")
        elif not api:
            st.error("API 연결 필요")
        else:
            with st.spinner("쇼츠 3편 세트 생성 중..."):
                prompt = f"""너는 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가야.

대주제: '{topic_shorts.strip()}'

이 대주제에서 파생되는 연관성 높고 중복 없는 쇼츠 3편을 세트로 기획해.

아래 여덟 가지 관점에서 3개의 소주제를 골고루 뽑아.
관점1 몰락 원인 분석. 관점2 전성기 실태. 관점3 내부 폭로. 관점4 비교 분석.
관점5 수익 구조. 관점6 피해자 시점. 관점7 현재 상황. 관점8 미래 전망.

대본 핵심 원칙:
- 인사 자기소개 구독 좋아요 언급 금지
- 첫 문장은 현장 한가운데에 시청자를 던져 넣는 문장
- 첫 세 문장 안에 열린 고리 설치
- 접속사는 근데 그래서 결국 알고보니 문제는 사용
- 한 문장 15자에서 40자. 번호 매기기 금지
- 습니다체 기본에 까요체 질문 혼합
- 각 편 8문장에서 12문장 (40초 이내 분량)
- 모든 영어와 숫자는 한글로. 특수기호는 마침표만 사용

이미지 프롬프트 규칙:
- 장면 수와 대사 문장 수 1대1 매칭
- 모든 프롬프트 앞에 SD 2D anime style, 붙임
- 주인공 등장 장면 뒤에 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 9:16 vertical aspect ratio
- 주인공 미등장 장면 뒤에 9:16 vertical aspect ratio

상단제목: 한 줄당 15자 이내 두 줄 구성

반드시 정확히 아래 형식으로만 출력해. 다른 말 절대 붙이지 마.

=001=
제목: (50자 이내)
상단제목첫째줄: (15자 이내)
상단제목둘째줄: (15자 이내)
설명글: (약 200자 해시태그 3개에서 5개 포함)
태그: (쉼표 구분 15개에서 20개)
순수대본: (문장만 마침표로 나열)
=장면001=
대사: (첫번째 문장)
프롬프트: SD 2D anime style, (영어 장면묘사), (접미어)
=장면002=
대사: (두번째 문장)
프롬프트: SD 2D anime style, (영어 장면묘사), (접미어)
(대사 문장 수만큼 반복)

=002=
(동일 형식)

=003=
(동일 형식)"""

                try:
                    raw = api.generate(prompt)
                    st.session_state.shorts_raw = raw
                    episodes = []
                    ep_blocks = re.split(r'=00(\d)=', raw)
                    i = 1
                    while i < len(ep_blocks) - 1:
                        ep_num = ep_blocks[i].strip()
                        ep_content = ep_blocks[i + 1].strip()
                        ep = {"num": ep_num, "raw": ep_content}
                        m = re.search(r'제목:\s*(.+)', ep_content)
                        ep["title"] = m.group(1).strip() if m else f"쇼츠 {ep_num}편"
                        m1 = re.search(r'상단제목첫째줄:\s*(.+)', ep_content)
                        m2 = re.search(r'상단제목둘째줄:\s*(.+)', ep_content)
                        ep["top_line1"] = m1.group(1).strip() if m1 else ""
                        ep["top_line2"] = m2.group(1).strip() if m2 else ""
                        m = re.search(r'설명글:\s*(.+?)(?=\n태그:|\n=장면)', ep_content, re.DOTALL)
                        ep["description"] = m.group(1).strip() if m else ""
                        m = re.search(r'태그:\s*(.+)', ep_content)
                        ep["tags"] = m.group(1).strip() if m else ""
                        m = re.search(r'순수대본:\s*(.+?)(?=\n=장면)', ep_content, re.DOTALL)
                        ep["script"] = m.group(1).strip() if m else ""
                        scenes = []
                        scene_blocks = re.findall(
                            r'=장면\d+=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?=\n=장면|\n=00|$)',
                            ep_content, re.DOTALL
                        )
                        for dialogue, prompt_text in scene_blocks:
                            scenes.append({"dialogue": dialogue.strip(), "prompt": prompt_text.strip()})
                        ep["scenes"] = scenes
                        episodes.append(ep)
                        i += 2
                    st.session_state.shorts_data = episodes
                except Exception as e:
                    st.error(f"생성 실패: {e}")

    if st.session_state.shorts_data:
        with st.expander("AI 원본 응답 (디버그)"):
            st.code(st.session_state.shorts_raw)
        for ep in st.session_state.shorts_data:
            st.divider()
            with st.container(border=True):
                title_col, top_col = st.columns([3, 2])
                with title_col:
                    st.subheader(f"편 {ep['num']}. {ep['title']}")
                with top_col:
                    if ep.get("top_line1") or ep.get("top_line2"):
                        st.markdown("**상단제목**")
                        st.write(f"{ep.get('top_line1', '')} / {ep.get('top_line2', '')}")
                if ep.get("tags"):
                    with st.container(border=True):
                        st.markdown("**태그**")
                        st.write(ep["tags"])
                if ep.get("description"):
                    with st.container(border=True):
                        st.markdown("**설명글**")
                        st.write(ep["description"])
                with st.container(border=True):
                    st.markdown("**대본 (40초 이내)**")
                    script_text = ep.get("script", "(대본 없음)")
                    st.write(script_text)
                    if script_text and script_text != "(대본 없음)":
                        char_count = len(script_text)
                        est_sec = min(40, max(10, char_count // 7))
                        st.caption(f"글자 수: {char_count}자 | 예상: 약 {est_sec}초")
                if ep.get("scenes"):
                    with st.expander(f"장면 프롬프트 ({len(ep['scenes'])}개)"):
                        for j, scene in enumerate(ep["scenes"]):
                            st.markdown(f"**장면 {j+1}**")
                            st.write(f"대사: {scene['dialogue']}")
                            st.code(scene["prompt"], language="text")
        st.divider()
        st.download_button(
            "쇼츠 3편 전체 다운로드 (TXT)", data=st.session_state.shorts_raw,
            file_name=f"shorts_3set_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain"
        )


# ════════════════════════════════════════════
# 탭4: 이미지 생성 (롱폼 / 쇼츠 분리)
# ════════════════════════════════════════════
with tab4:
    st.header("이미지 생성")
    img_tab_long, img_tab_shorts = st.tabs(["롱폼 이미지 (16:9)", "쇼츠 이미지 (9:16)"])

    with img_tab_long:
        st.subheader("롱폼 대본 기반 이미지 생성")
        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
            st.info(f"총 {len(paragraphs)}개 문단 감지됨")
            if st.button("롱폼 이미지 프롬프트 생성", key="gen_long_prompts"):
                with st.spinner("프롬프트 생성 중..."):
                    prompt_req = f"""아래 대본의 각 문단에 대해 이미지 프롬프트를 생성해줘.
규칙:
- 모든 프롬프트는 SD 2D anime style, 로 시작
- 16:9 가로 비율
- 주인공 등장 장면은 뒤에 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 16:9 horizontal aspect ratio
- 주인공 미등장 장면은 뒤에 16:9 horizontal aspect ratio

형식:
[장면1]
내용요약: (한글 한줄)
프롬프트: SD 2D anime style, (영어 장면묘사), (접미어)

대본:
{body[:3000]}"""
                    try:
                        result = api.generate(prompt_req)
                        st.session_state["longform_prompts_raw"] = result
                    except Exception as e:
                        st.error(f"프롬프트 생성 실패: {e}")
            if st.session_state.get("longform_prompts_raw"):
                st.text_area("생성된 프롬프트", value=st.session_state["longform_prompts_raw"],
                             height=400, key="long_prompts_display")
                prompts = re.findall(r'프롬프트:\s*(SD 2D anime style,.+?)(?=\n\[장면|\n$|$)',
                                     st.session_state["longform_prompts_raw"], re.DOTALL)
                if prompts:
                    st.info(f"총 {len(prompts)}개 프롬프트 감지")
                    if st.button("전체 이미지 생성 (롱폼)", key="gen_long_images"):
                        progress = st.progress(0)
                        generated = []
                        for idx, p in enumerate(prompts):
                            try:
                                img_url = api.generate_image(p.strip(), aspect_ratio="16:9")
                                generated.append({"prompt": p.strip(), "url": img_url, "index": idx + 1})
                            except Exception as e:
                                generated.append({"prompt": p.strip(), "url": None, "error": str(e), "index": idx + 1})
                            progress.progress((idx + 1) / len(prompts))
                        st.session_state.generated_images_longform = generated
            if st.session_state.generated_images_longform:
                st.subheader("생성된 롱폼 이미지")
                cols = st.columns(3)
                for idx, img in enumerate(st.session_state.generated_images_longform):
                    with cols[idx % 3]:
                        st.caption(f"장면 {img['index']}")
                        if img.get("url"):
                            st.image(img["url"], use_container_width=True)
                        else:
                            st.error(f"실패: {img.get('error', '')}")
                        with st.expander("프롬프트"):
                            st.code(img["prompt"], language="text")
        else:
            st.warning("먼저 [롱폼 대본] 탭에서 대본을 생성하세요.")

    with img_tab_shorts:
        st.subheader("쇼츠 대본 기반 이미지 생성 (9:16 세로)")
        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                with st.container(border=True):
                    st.markdown(f"**편 {ep['num']}. {ep['title']}**")
                    if ep.get("scenes"):
                        for j, scene in enumerate(ep["scenes"]):
                            st.caption(f"장면{j+1}: {scene['dialogue'][:30]}...")
                            st.code(scene["prompt"], language="text")
                        if st.button(f"편 {ep['num']} 이미지 생성", key=f"gen_shorts_img_{ep['num']}"):
                            progress = st.progress(0)
                            ep_images = []
                            for j, scene in enumerate(ep["scenes"]):
                                try:
                                    img_url = api.generate_image(scene["prompt"], aspect_ratio="9:16")
                                    ep_images.append({"url": img_url, "scene": j+1, "dialogue": scene["dialogue"]})
                                except Exception as e:
                                    ep_images.append({"url": None, "scene": j+1, "error": str(e), "dialogue": scene["dialogue"]})
                                progress.progress((j+1) / len(ep["scenes"]))
                            st.session_state[f"shorts_images_ep{ep['num']}"] = ep_images
                        key = f"shorts_images_ep{ep['num']}"
                        if st.session_state.get(key):
                            cols = st.columns(4)
                            for j, img in enumerate(st.session_state[key]):
                                with cols[j % 4]:
                                    st.caption(f"장면{img['scene']}: {img['dialogue'][:20]}")
                                    if img.get("url"):
                                        st.image(img["url"], use_container_width=True)
                                    else:
                                        st.error(f"실패: {img.get('error', '')}")
            st.divider()
            if st.button("쇼츠 3편 전체 이미지 일괄 생성", type="primary", key="gen_all_shorts_imgs"):
                for ep in st.session_state.shorts_data:
                    if ep.get("scenes"):
                        st.write(f"편 {ep['num']} 생성 중...")
                        progress = st.progress(0)
                        ep_images = []
                        for j, scene in enumerate(ep["scenes"]):
                            try:
                                img_url = api.generate_image(scene["prompt"], aspect_ratio="9:16")
                                ep_images.append({"url": img_url, "scene": j+1, "dialogue": scene["dialogue"]})
                            except Exception as e:
                                ep_images.append({"url": None, "scene": j+1, "error": str(e), "dialogue": scene["dialogue"]})
                            progress.progress((j+1) / len(ep["scenes"]))
                        st.session_state[f"shorts_images_ep{ep['num']}"] = ep_images
                st.success("전체 쇼츠 이미지 생성 완료")
                st.rerun()
        else:
            st.warning("먼저 [쇼츠 대본] 탭에서 대본을 생성하세요.")


# ════════════════════════════════════════════
# 탭5: 영상 변환
# ════════════════════════════════════════════
with tab5:
    st.header("이미지 → 영상 변환 (Kie AI)")
    st.info("탭4에서 생성된 이미지를 영상으로 변환합니다.")
    if api:
        img_url_input = st.text_input("이미지 URL 입력", key="video_img_url")
        if st.button("영상 변환 시작"):
            if img_url_input.strip():
                with st.spinner("영상 변환 중..."):
                    try:
                        task_id = api.kie.create_task(img_url_input.strip())
                        st.info(f"작업 ID: {task_id}")
                        result = api.kie.wait_for_completion(task_id)
                        if result:
                            st.success("영상 변환 완료!")
                            st.video(result)
                        else:
                            st.error("영상 변환 실패")
                    except Exception as e:
                        st.error(f"오류: {e}")


# ════════════════════════════════════════════
# 탭6: 음성 합성
# ════════════════════════════════════════════
with tab6:
    st.header("음성 합성 (Inworld TTS)")
    tts_source = st.radio("음성 합성 대상", ["롱폼 대본", "쇼츠 대본"], key="tts_source")
    if tts_source == "롱폼 대본":
        text = st.session_state.longform_metadata.get("body", "") if st.session_state.longform_metadata else ""
    else:
        parts = []
        for ep in st.session_state.shorts_data:
            if ep.get("script"):
                parts.append(f"[편{ep['num']}]\n{ep['script']}")
        text = "\n\n".join(parts)
    tts_text = st.text_area("합성할 텍스트", value=text, height=200, key="tts_text_input")
    if st.button("음성 합성 시작"):
        if not tts_text.strip():
            st.warning("텍스트를 입력하세요")
        elif api:
            with st.spinner("음성 합성 중..."):
                try:
                    result = api.inworld.synthesize(tts_text.strip())
                    if isinstance(result, tuple):
                        if len(result) == 3:
                            audio, timestamps, error = result
                        elif len(result) == 2:
                            audio, timestamps = result
                            error = None
                        else:
                            audio = result[0] if result else None
                            timestamps = None
                            error = None
                    else:
                        audio = result
                        timestamps = None
                        error = None
                    if error:
                        st.error(f"합성 오류: {error}")
                    elif audio:
                        st.success("음성 합성 완료!")
                        audio_bytes = base64.b64decode(audio) if isinstance(audio, str) else audio
                        st.audio(audio_bytes, format="audio/mp3")
                        st.download_button("MP3 다운로드", data=audio_bytes,
                                           file_name="tts_output.mp3", mime="audio/mp3")
                except Exception as e:
                    st.error(f"합성 실패: {e}")


# ════════════════════════════════════════════
# 탭7: 자막 설정 (롱폼 / 쇼츠 분리, 미세조절, 실시간 미리보기)
# ════════════════════════════════════════════
with tab7:
    st.header("자막 설정")
    st.caption("롱폼과 쇼츠 자막을 따로 설정하고, 실제 영상 위에서 어떻게 보이는지 실시간으로 확인하세요.")

    sub_tab_long, sub_tab_shorts = st.tabs(["롱폼 자막 (16:9)", "쇼츠 자막 (9:16)"])

    # ── 롱폼 자막 ──
    with sub_tab_long:
        st.subheader("롱폼 자막 설정 (16:9 가로)")
        ctrl_col, preview_col = st.columns([1, 1])

        with ctrl_col:
            long_settings = subtitle_settings_ui("long", "16:9")
            st.session_state.sub_settings_longform = long_settings

        with preview_col:
            st.markdown("**실시간 미리보기**")
            long_preview_text = st.text_input(
                "미리보기 텍스트",
                value="자막 미리보기 샘플 텍스트입니다",
                key="long_preview_text"
            )
            html = build_subtitle_preview_html(long_settings, long_preview_text, "16:9")
            st.components.v1.html(html, height=360)

            st.divider()
            st.markdown("**현재 설정값 요약**")
            with st.container(border=True):
                st.write(f"글씨체: {long_settings['font']} / 크기: {long_settings['size']}px")
                st.write(f"굵게: {'O' if long_settings['bold'] else 'X'} / 기울임: {'O' if long_settings['italic'] else 'X'}")
                st.write(f"자간: {long_settings['letter_spacing']}px / 행간: {long_settings['line_height']}")
                st.write(f"글자색: {long_settings['color']} / 외곽선: {long_settings['outline_color']} ({long_settings['outline_width']}px)")
                st.write(f"그림자: {long_settings['shadow_color']} (번짐 {long_settings['shadow_blur']}px)")
                st.write(f"배경: {long_settings['bg_color']} (투명도 {long_settings['bg_opacity']}%)")
                st.write(f"위치: {long_settings['position']} / 정렬: {long_settings['align']}")
                st.write(f"여백 - 위:{long_settings['pos_top']} 아래:{long_settings['pos_bottom']} 좌:{long_settings['pos_left']} 우:{long_settings['pos_right']}px")

            if st.button("롱폼 자막 설정 저장", key="save_long_sub"):
                st.session_state.sub_settings_longform = long_settings
                st.success("롱폼 자막 설정이 저장되었습니다")

    # ── 쇼츠 자막 ──
    with sub_tab_shorts:
        st.subheader("쇼츠 자막 설정 (9:16 세로)")
        ctrl_col2, preview_col2 = st.columns([1, 1])

        with ctrl_col2:
            shorts_settings = subtitle_settings_ui("shorts", "9:16")
            st.session_state.sub_settings_shorts = shorts_settings

        with preview_col2:
            st.markdown("**실시간 미리보기**")
            shorts_preview_text = st.text_input(
                "미리보기 텍스트",
                value="쇼츠 자막 미리보기입니다",
                key="shorts_preview_text"
            )
            html2 = build_subtitle_preview_html(shorts_settings, shorts_preview_text, "9:16")
            st.components.v1.html(html2, height=540)

            st.divider()
            st.markdown("**현재 설정값 요약**")
            with st.container(border=True):
                st.write(f"글씨체: {shorts_settings['font']} / 크기: {shorts_settings['size']}px")
                st.write(f"굵게: {'O' if shorts_settings['bold'] else 'X'} / 기울임: {'O' if shorts_settings['italic'] else 'X'}")
                st.write(f"자간: {shorts_settings['letter_spacing']}px / 행간: {shorts_settings['line_height']}")
                st.write(f"글자색: {shorts_settings['color']} / 외곽선: {shorts_settings['outline_color']} ({shorts_settings['outline_width']}px)")
                st.write(f"그림자: {shorts_settings['shadow_color']} (번짐 {shorts_settings['shadow_blur']}px)")
                st.write(f"배경: {shorts_settings['bg_color']} (투명도 {shorts_settings['bg_opacity']}%)")
                st.write(f"위치: {shorts_settings['position']} / 정렬: {shorts_settings['align']}")
                st.write(f"여백 - 위:{shorts_settings['pos_top']} 아래:{shorts_settings['pos_bottom']} 좌:{shorts_settings['pos_left']} 우:{shorts_settings['pos_right']}px")

            if st.button("쇼츠 자막 설정 저장", key="save_shorts_sub"):
                st.session_state.sub_settings_shorts = shorts_settings
                st.success("쇼츠 자막 설정이 저장되었습니다")

    # ── 글씨체 미리보기 갤러리 ──
    st.divider()
    st.subheader("글씨체 미리보기 갤러리")
    st.caption("선택 전에 각 글씨체가 어떻게 보이는지 한눈에 확인하세요.")

    FONT_GALLERY = [
        "Noto Sans KR", "Noto Serif KR", "Black Han Sans", "Jua", "Do Hyeon",
        "Gothic A1", "Sunflower", "Gaegu", "Hi Melody", "Song Myung",
        "Stylish", "Gugi", "Gamja Flower", "East Sea Dokdo", "Cute Font",
        "Yeon Sung", "Poor Story", "Single Day", "Black And White Picture", "Dokdo",
    ]

    gallery_text = st.text_input("갤러리 미리보기 텍스트", value="떡상 유튜브 콘텐츠 팩토리", key="gallery_text")

    font_links = ""
    font_previews = ""
    for f in FONT_GALLERY:
        font_links += f'<link href="https://fonts.googleapis.com/css2?family={f.replace(" ", "+")}&display=swap" rel="stylesheet">'
        font_previews += f"""
        <div style="
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 4px;
            display: inline-block;
            min-width: 200px;
        ">
            <div style="color:#888;font-size:10px;margin-bottom:4px;font-family:monospace;">{f}</div>
            <div style="
                font-family: '{f}', sans-serif;
                font-size: 18px;
                color: #ffffff;
                -webkit-text-stroke: 1px #000;
                paint-order: stroke fill;
                text-shadow: 2px 2px 4px #000;
            ">{gallery_text}</div>
        </div>
        """

    gallery_html = f"""
    {font_links}
    <div style="display:flex;flex-wrap:wrap;gap:6px;padding:10px;">
        {font_previews}
    </div>
    """
    st.components.v1.html(gallery_html, height=500, scrolling=True)


# ════════════════════════════════════════════
# 탭8: 최종 합치기
# ════════════════════════════════════════════
with tab8:
    st.header("최종 합치기")
    st.info("Streamlit Cloud에서는 FFmpeg를 직접 실행할 수 없습니다. 아래에서 상태를 확인하고 로컬에서 합성하세요.")

    st.subheader("현재 상태")
    checks = {
        "선택된 주제": st.session_state.selected_topic or "없음",
        "롱폼 대본": "생성됨" if st.session_state.longform_metadata else "없음",
        "쇼츠 대본": f"{len(st.session_state.shorts_data)}편" if st.session_state.shorts_data else "없음",
        "롱폼 이미지": f"{len(st.session_state.generated_images_longform)}장" if st.session_state.generated_images_longform else "없음",
        "레퍼런스 이미지": "업로드됨" if st.session_state.reference_image else "없음",
        "롱폼 자막 설정": "설정됨" if st.session_state.sub_settings_longform else "없음",
        "쇼츠 자막 설정": "설정됨" if st.session_state.sub_settings_shorts else "없음",
    }
    for k, v in checks.items():
        if v == "없음":
            st.warning(f"{k}: {v}")
        else:
            st.success(f"{k}: {v}")

    st.divider()
    st.subheader("자막 설정 내보내기")
    if st.session_state.sub_settings_longform or st.session_state.sub_settings_shorts:
        export_data = {
            "longform": st.session_state.sub_settings_longform,
            "shorts": st.session_state.sub_settings_shorts,
        }
        st.download_button(
            "자막 설정 JSON 다운로드",
            data=json.dumps(export_data, ensure_ascii=False, indent=2),
            file_name=f"subtitle_settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
