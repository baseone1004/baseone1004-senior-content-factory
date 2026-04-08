import streamlit as st
import re
from utils.api_handler import APIHandler
from prompts.topic_recommend import TOPIC_RECOMMEND_ECONOMY, TOPIC_RECOMMEND_SENIOR
from prompts.economy_script import ECONOMY_SCRIPT_PROMPT
from prompts.senior_longform import SENIOR_LONGFORM_PROMPT
from prompts.shorts_prompt import SHORTS_PROMPT
from prompts.script_polish import SCRIPT_POLISH_PROMPT

st.set_page_config(page_title="시니어 콘텐츠 팩토리", page_icon="\U0001F3AC", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = APIHandler()
for key in ["topics","selected_topic_data","longform_result","polished_result","shorts_result"]:
    if key not in st.session_state:
        st.session_state[key] = None
if "step" not in st.session_state:
    st.session_state.step = "home"

def parse_topics(raw_text):
    topics = []
    pattern = r"\uc8fc\uc81c\d+:\s*(.+?)\s*\|\s*\ub5a1\uc0c1\ud655\ub960:\s*(\d+)%"
    lines = raw_text.strip().split("\n")
    current = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(pattern, line)
        if match:
            if current and current["title"]:
                topics.append(current)
            current = {"title": match.group(1).strip(), "prob": match.group(2).strip(), "alt_a": "", "alt_b": "", "tags": "", "source": ""}
        elif current:
            if line.startswith("\ucd9c\ucc98:"):
                current["source"] = line.split(":", 1)[1].strip()
            elif line.startswith("\ub300\uc548A:"):
                current["alt_a"] = line.split(":", 1)[1].strip()
            elif line.startswith("\ub300\uc548B:"):
                current["alt_b"] = line.split(":", 1)[1].strip()
            elif line.startswith("\ud0dc\uadf8:"):
                current["tags"] = line.split(":", 1)[1].strip()
    if current and current["title"]:
        topics.append(current)
    return topics

def parse_longform(raw_text):
    result = {"title": "", "desc": "", "tags": "", "script": ""}
    lines = raw_text.strip().split("\n")
    in_script = False
    script_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("\uc81c\ubaa9:"):
            result["title"] = stripped.replace("\uc81c\ubaa9:", "").strip()
        elif stripped.startswith("\uc124\uba85\uae00:"):
            result["desc"] = stripped.replace("\uc124\uba85\uae00:", "").strip()
        elif stripped.startswith("\ud0dc\uadf8:") and not result["tags"]:
            result["tags"] = stripped.replace("\ud0dc\uadf8:", "").strip()
        elif stripped == "=\ub300\ubcf8 \uc2dc\uc791=":
            in_script = True
        elif stripped == "=\ub300\ubcf8 \ub05d=":
            in_script = False
        elif in_script:
            script_lines.append(line)
    result["script"] = "\n".join(script_lines).strip()
    if not result["script"]:
        result["script"] = raw_text
    return result

def parse_shorts(raw_text):
    shorts = []
    parts = re.split(r'=00[1-9]=', raw_text)
    if len(parts) > 1:
        parts = parts[1:]
    else:
        return shorts
    for part in parts:
        s = {"title": "", "top1": "", "top2": "", "desc": "", "tags": "", "pinned": "", "script": ""}
        lines = part.strip().split("\n")
        in_script = False
        script_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("\uc81c\ubaa9:"):
                s["title"] = stripped.split(":", 1)[1].strip()
            elif "\uccab\uc9f8\uc904:" in stripped or "\uccab\uc9f8 \uc904:" in stripped:
                s["top1"] = stripped.split(":", 1)[1].strip()
            elif "\ub458\uc9f8\uc904:" in stripped or "\ub458\uc9f8 \uc904:" in stripped:
                s["top2"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("\uc124\uba85\uae00:"):
                s["desc"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("\ud0dc\uadf8:"):
                s["tags"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("\uace0\uc815\ub313\uae00:"):
                s["pinned"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("\uc21c\uc218\ub300\ubcf8:") or stripped.startswith("\uc21c\uc218 \ub300\ubcf8:"):
                rest = stripped.split(":", 1)[1].strip()
                if rest:
                    script_lines.append(rest)
                in_script = True
            elif in_script:
                if stripped.startswith("="):
                    in_script = False
                else:
                    script_lines.append(stripped)
        s["script"] = "\n".join(script_lines).strip()
        if s["title"]:
            shorts.append(s)
    return shorts

def render_shorts_card(num, s):
    st.markdown(f'<div style="background:linear-gradient(90deg,#FF6B6B,#FF8E53);color:#fff;font-size:1.1rem;font-weight:800;padding:.4rem 1.2rem;border-radius:20px;display:inline-block;margin-bottom:1rem;">쇼츠 {num}편</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#FF8E53;font-size:.8rem;font-weight:700;margin-bottom:.3rem;">제목</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:1.2rem;font-weight:800;color:#FAFAFA;background:linear-gradient(135deg,#1A1F2E,#2A2F3E);border:2px solid #FF6B6B;border-radius:12px;padding:1rem;margin-bottom:1rem;">{s["title"]}</div>', unsafe_allow_html=True)
    if s["top1"] or s["top2"]:
        st.markdown(f'<div style="color:#FF8E53;font-size:.8rem;font-weight:700;margin-bottom:.3rem;">상단제목</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="background:#2A2F3E;border-left:3px solid #FF6B6B;padding:.6rem 1rem;border-radius:0 8px 8px 0;margin-bottom:.8rem;"><div style="color:#FFE66D;font-size:1rem;font-weight:700;">{s["top1"]}</div><div style="color:#FFE66D;font-size:1rem;font-weight:700;">{s["top2"]}</div></div>', unsafe_allow_html=True)
    if s["desc"]:
        st.markdown(f'<div style="color:#FF8E53;font-size:.8rem;font-weight:700;margin-bottom:.3rem;">설명글</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="background:#0E1117;border:1px solid #333;border-radius:10px;padding:1rem;color:#CCC;line-height:1.6;font-size:.9rem;margin-bottom:.8rem;">{s["desc"]}</div>', unsafe_allow_html=True)
    if s["tags"]:
        st.markdown(f'<div style="color:#FF8E53;font-size:.8rem;font-weight:700;margin-bottom:.3rem;">태그</div>', unsafe_allow_html=True)
        tag_chips = "".join([f'<span style="background:#2A2F3E;color:#FFE66D;padding:.2rem .5rem;border-radius:8px;font-size:.75rem;display:inline-block;margin:.2rem;border:1px solid #444;">{x.strip()}</span>' for x in s["tags"].split(",") if x.strip()])
        st.markdown(f'<div style="background:#0E1117;border:1px solid #333;border-radius:10px;padding:.8rem 1rem;margin-bottom:.8rem;">{tag_chips}</div>', unsafe_allow_html=True)
    if s["script"]:
        st.markdown(f'<div style="color:#FF8E53;font-size:.8rem;font-weight:700;margin-bottom:.3rem;">대본</div>', unsafe_allow_html=True)
        script_html = s["script"].replace("\n", "<br>")
        st.markdown(f'<div style="background:#0E1117;border:2px solid #FF6B6B;border-radius:10px;padding:1.2rem;color:#FAFAFA;line-height:2;font-size:.95rem;margin-bottom:.8rem;">{script_html}</div>', unsafe_allow_html=True)
    if s["pinned"]:
        st.markdown(f'<div style="color:#FF8E53;font-size:.8rem;font-weight:700;margin-bottom:.3rem;">고정댓글</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="background:linear-gradient(135deg,#2A2F3E,#1A1F2E);border:2px solid #FFE66D;border-radius:10px;padding:.8rem 1rem;color:#FFE66D;font-size:.9rem;margin-bottom:.5rem;">{s["pinned"]}</div>', unsafe_allow_html=True)

st.markdown("""
<style>
.main-title{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#FF6B6B,#FFE66D);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:.5rem}
.sub-title{font-size:1.1rem;color:#888;text-align:center;margin-bottom:2rem}
.topic-card{background:linear-gradient(135deg,#1A1F2E,#2A2F3E);border:1px solid #333;border-radius:12px;padding:1.2rem;margin-bottom:.8rem}
.topic-card:hover{border-color:#FF6B6B;box-shadow:0 0 15px rgba(255,107,107,.2)}
.prob-badge{background:linear-gradient(90deg,#FF6B6B,#FF8E53);color:#fff;padding:.3rem .8rem;border-radius:20px;font-weight:700;font-size:.9rem;display:inline-block}
.tag-chip{background:#2A2F3E;color:#FFE66D;padding:.2rem .6rem;border-radius:10px;font-size:.75rem;display:inline-block;margin:.1rem;border:1px solid #444}
.source-text{color:#FF8E53;font-size:.75rem;margin-top:.2rem}
.result-box{background:#1A1F2E;border:1px solid #333;border-radius:12px;padding:1.5rem;margin-top:1rem;white-space:pre-wrap;font-size:.95rem;line-height:1.8}
.status-bar{background:linear-gradient(90deg,#1A1F2E,#2A2F3E);border-radius:8px;padding:.8rem 1.2rem;margin-bottom:1rem;border-left:4px solid #FF6B6B}
.section-header{font-size:1.3rem;font-weight:700;color:#FFE66D;margin-top:2rem;margin-bottom:.5rem;padding-bottom:.5rem;border-bottom:2px solid #333}
.title-display{font-size:1.5rem;font-weight:800;color:#FAFAFA;background:linear-gradient(135deg,#1A1F2E,#2A2F3E);border:2px solid #FF6B6B;border-radius:12px;padding:1.2rem;margin-bottom:.8rem;text-align:center}
.ab-box{background:#2A2F3E;border:1px solid #444;border-radius:10px;padding:.8rem 1rem;margin:.3rem 0}
.ab-label{color:#FF8E53;font-weight:700;font-size:.85rem}
.desc-box{background:#1A1F2E;border:1px solid #333;border-radius:10px;padding:1rem;margin-top:.5rem;color:#CCC;line-height:1.6}
.tag-section{background:#1A1F2E;border:1px solid #333;border-radius:10px;padding:1rem;margin-top:.5rem}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">시니어 콘텐츠 팩토리</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">주제 추천 → 대본 → 교정 → 쇼츠 3편</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 채널 설정")
    channel_type = st.selectbox("채널 유형", ["경제/사회 (한국 채널)", "시니어 (한국 채널)", "시니어 (일본 채널)"])
    if channel_type == "경제/사회 (한국 채널)":
        language = "한국어"
        content_mode = "economy"
    elif channel_type == "시니어 (한국 채널)":
        language = "한국어"
        content_mode = "senior"
    else:
        language = "일본어"
        content_mode = "senior"

    mode_text = "사실 기반 (실시간 검색)" if content_mode == "economy" else "100% 창작"
    st.markdown(f'<div class="status-bar"><b>현재 채널:</b> {channel_type}<br><b>콘텐츠 방식:</b> {mode_text}<br><b>언어:</b> {language}</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### API 연결 상태")
    if st.button("연결 테스트", use_container_width=True):
        success, msg = st.session_state.api.test_connection()
        if success:
            st.success(msg)
        else:
            st.error(msg)
    st.markdown("---")
    if st.button("처음으로 돌아가기", use_container_width=True):
        for key in ["topics","selected_topic_data","longform_result","polished_result","shorts_result"]:
            st.session_state[key] = None
        st.session_state.step = "home"
        st.rerun()

if st.session_state.step == "home":
    st.markdown("---")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if st.button("주제 추천 받기", use_container_width=True, type="primary"):
            with st.spinner("실시간 뉴스 검색 및 주제 분석 중..."):
                if content_mode == "economy":
                    prompt = TOPIC_RECOMMEND_ECONOMY
                else:
                    prompt = TOPIC_RECOMMEND_SENIOR.format(language=language)
                result, error = st.session_state.api.generate_long_with_search(prompt)
                if error:
                    st.error(error)
                else:
                    st.session_state.topics = parse_topics(result)
                    st.session_state.raw_topics = result
                    st.session_state.step = "topics"
                    st.rerun()

elif st.session_state.step == "topics":
    st.markdown("### 추천 주제 목록 (2026년 실시간 기반)")
    topics = st.session_state.topics
    if not topics:
        st.warning("주제 파싱에 실패했습니다. 원본 결과를 표시합니다.")
        st.text(st.session_state.get("raw_topics", ""))
        if st.button("다시 추천받기"):
            st.session_state.step = "home"
            st.rerun()
    else:
        for i, t in enumerate(topics):
            src = f'<div class="source-text">출처: {t["source"]}</div>' if t["source"] else ""
            tgs = "".join([f'<span class="tag-chip">{x.strip()}</span>' for x in t["tags"].split(",") if x.strip()])
            st.markdown(f'<div class="topic-card"><div style="display:flex;justify-content:space-between;align-items:center;"><span style="font-size:1.1rem;font-weight:700;color:#FAFAFA;">{t["title"]}</span><span class="prob-badge">떡상확률 {t["prob"]}%</span></div>{src}<div style="color:#777;font-size:.8rem;margin-top:.3rem;">대안A: {t["alt_a"]} | 대안B: {t["alt_b"]}</div><div style="margin-top:.5rem;">{tgs}</div></div>', unsafe_allow_html=True)
            if st.button("이 주제 선택", key=f"s_{i}", use_container_width=True):
                st.session_state.selected_topic_data = t
                for key in ["longform_result","polished_result","shorts_result"]:
                    st.session_state[key] = None
                st.session_state.step = "result"
                st.rerun()

elif st.session_state.step == "result":
    t = st.session_state.selected_topic_data

    if st.session_state.longform_result is None:
        st.markdown("### 대본 생성 중...")
        with st.spinner("롱폼 대본을 생성하고 있습니다..."):
            if content_mode == "economy":
                prompt = ECONOMY_SCRIPT_PROMPT.format(topic=t["title"])
                result, error = st.session_state.api.generate_long_with_search(prompt)
            else:
                prompt = SENIOR_LONGFORM_PROMPT.format(topic=t["title"], language=language)
                result, error = st.session_state.api.generate_long(prompt)
            if error:
                st.error(error)
                if st.button("다시 시도"):
                    st.rerun()
            else:
                st.session_state.longform_result = result
                st.rerun()
    else:
        parsed = parse_longform(st.session_state.longform_result)
        display_title = parsed["title"] if parsed["title"] else t["title"]

        tab1, tab2, tab3 = st.tabs(["대본 원본", "교정 대본", "쇼츠 3편"])

        with tab1:
            st.markdown('<div class="section-header">제목</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="title-display">{display_title}</div>', unsafe_allow_html=True)

            if t["tags"]:
                tgs = "".join([f'<span class="tag-chip">{x.strip()}</span>' for x in t["tags"].split(",") if x.strip()])
                st.markdown(f'<div class="tag-section">{tgs}</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-header">A/B 테스트 대안 제목</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ab-box"><span class="ab-label">대안 A:</span> <span style="color:#FAFAFA;">{t["alt_a"]}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ab-box"><span class="ab-label">대안 B:</span> <span style="color:#FAFAFA;">{t["alt_b"]}</span></div>', unsafe_allow_html=True)

            st.markdown('<div class="section-header">대본 (원본)</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="result-box">{parsed["script"]}</div>', unsafe_allow_html=True)
            st.download_button("원본 대본 다운로드", st.session_state.longform_result, file_name="longform_original.txt", mime="text/plain")

            if parsed["desc"]:
                st.markdown('<div class="section-header">설명글</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="desc-box">{parsed["desc"]}</div>', unsafe_allow_html=True)
            if parsed["tags"]:
                st.markdown('<div class="section-header">태그</div>', unsafe_allow_html=True)
                tgs2 = "".join([f'<span class="tag-chip">{x.strip()}</span>' for x in parsed["tags"].split(",") if x.strip()])
                st.markdown(f'<div class="tag-section">{tgs2}</div>', unsafe_allow_html=True)

        with tab2:
            if st.session_state.polished_result is None:
                st.markdown("대본의 번호 매기기 제거, 반복 표현 수정, 첫 문장 강화, 구어체 최적화를 자동으로 수행합니다.")
                if st.button("대본 교정 시작", type="primary", use_container_width=True):
                    with st.spinner("대본 교정 중..."):
                        script_text = parsed["script"] if parsed["script"] else st.session_state.longform_result
                        prompt = SCRIPT_POLISH_PROMPT.format(script=script_text)
                        result, error = st.session_state.api.generate_long(prompt)
                        if error:
                            st.error(error)
                        else:
                            st.session_state.polished_result = result
                            st.rerun()
            else:
                st.markdown('<div class="section-header">교정된 대본</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="result-box">{st.session_state.polished_result}</div>', unsafe_allow_html=True)
                st.download_button("교정 대본 다운로드", st.session_state.polished_result, file_name="longform_polished.txt", mime="text/plain")

        with tab3:
            if st.session_state.shorts_result is None:
                st.markdown("롱폼 대본을 기반으로 쇼츠 3편의 제목, 상단제목, 설명글, 태그, 대본, 고정댓글을 자동 생성합니다.")
                longform_url_input = st.text_input("롱폼 영상 URL (고정댓글에 삽입)", value="", placeholder="https://youtu.be/...")
                if st.button("쇼츠 3편 생성", type="primary", use_container_width=True):
                    with st.spinner("쇼츠 3편 생성 중..."):
                        tl = parsed["title"] if parsed["title"] else t["title"]
                        sm = parsed["script"][:2000] if parsed["script"] else st.session_state.longform_result[:2000]
                        url_val = longform_url_input if longform_url_input else "[여기에 롱폼 영상 URL 삽입]"
                        prompt = SHORTS_PROMPT.format(language=language, longform_title=tl, longform_summary=sm, longform_url=url_val)
                        result, error = st.session_state.api.generate_long(prompt)
                        if error:
                            st.error(error)
                        else:
                            st.session_state.shorts_result = result
                            st.rerun()
            else:
                shorts_list = parse_shorts(st.session_state.shorts_result)
                if shorts_list:
                    for idx, s in enumerate(shorts_list):
                        render_shorts_card(idx + 1, s)
                        if idx < len(shorts_list) - 1:
                            st.markdown('<hr style="border:0;height:2px;background:linear-gradient(90deg,transparent,#FF6B6B,transparent);margin:2rem 0;">', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="result-box">{st.session_state.shorts_result}</div>', unsafe_allow_html=True)

                st.download_button("쇼츠 3편 다운로드", st.session_state.shorts_result, file_name="shorts.txt", mime="text/plain")

st.markdown('---')
st.markdown('<div style="text-align:center;color:#555;font-size:.8rem;">시니어 콘텐츠 팩토리 | Gemini API + Google Search 기반</div>', unsafe_allow_html=True)
