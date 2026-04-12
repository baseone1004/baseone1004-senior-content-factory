import streamlit as st
import re
import os
import time
import json
import base64
from utils.api_handler import APIHandler

st.set_page_config(page_title="시니어 콘텐츠 팩토리", page_icon="🎬", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = APIHandler()

default_keys = [
    "news_results", "selected_topic", "longform_script", "longform_meta",
    "shorts_scripts", "image_prompts", "image_urls", "image_paths",
    "video_urls", "audio_data", "scenes", "shorts_image_prompts",
    "shorts_image_urls", "shorts_video_urls", "shorts_audio_data",
    "subtitle_settings"
]
for key in default_keys:
    if key not in st.session_state:
        st.session_state[key] = None

if "step" not in st.session_state:
    st.session_state.step = "home"

if "subtitle_settings" not in st.session_state or st.session_state.subtitle_settings is None:
    st.session_state.subtitle_settings = {
        "font_size": 28,
        "font_family": "NanumGothicBold",
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "position": "하단",
        "margin_bottom": 30,
        "margin_top": 30
    }

# CSS
st.markdown("""<style>
.main-title{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#FF6B6B,#FFE66D);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:.5rem}
.sub-title{font-size:1rem;color:#888;text-align:center;margin-bottom:2rem}
.news-card{background:#1A1F2E;border:1px solid #333;border-radius:12px;padding:1rem;margin-bottom:.8rem}
.news-title{color:#FFE66D;font-weight:700;font-size:1rem}
.news-desc{color:#ccc;font-size:.85rem;margin-top:.3rem}
.news-meta{color:#888;font-size:.75rem;margin-top:.3rem}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="main-title">시니어 콘텐츠 팩토리 올인원</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">네이버 뉴스 + 스카이워크 + Kie AI + 인월드 TTS | 주제추천 → 대본 → 이미지 → 영상 → 음성 → 자막 → 합성</div>', unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.markdown("### API 연결 상태")
    if st.button("전체 연결 테스트", use_container_width=True):
        ok, msg = st.session_state.api.test_connection()
        if ok:
            st.success(msg)
        else:
            st.warning(msg)
    st.markdown("---")
    ref_image = st.file_uploader("레퍼런스 캐릭터 이미지", type=["png", "jpg", "jpeg"])
    if ref_image:
        st.image(ref_image, caption="레퍼런스 캐릭터", width=150)
        st.session_state["ref_image"] = ref_image
    ref_url = st.text_input("또는 이미지 URL 입력")
    if ref_url:
        st.session_state["ref_image_url"] = ref_url
    st.markdown("---")
    if st.button("처음으로 초기화", use_container_width=True):
        for key in default_keys:
            st.session_state[key] = None
        st.session_state.step = "home"
        st.rerun()

# 탭 구성
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "1.주제추천", "2.롱폼대본", "3.쇼츠대본", "4.이미지생성",
    "5.영상변환", "6.음성생성", "7.자막조정", "8.최종합성"
])

# === 탭1: 주제 추천 (네이버 뉴스 + 스카이워크 분석) ===
with tab1:
    st.markdown("### 실시간 뉴스 기반 유튜브 떡상 주제 추천")
    st.caption("네이버 뉴스에서 최신 트렌드를 수집하고, 스카이워크 AI가 유튜브 떡상 확률을 분석합니다.")

    col_search1, col_search2 = st.columns([3, 1])
    with col_search1:
        custom_keywords = st.text_input(
            "검색 키워드 (쉼표로 구분, 비워두면 기본 키워드 사용)",
            placeholder="예: 부동산 폭락, AI 일자리, 물가 상승"
        )
    with col_search2:
        news_count = st.selectbox("키워드당 뉴스 수", [3, 5, 10], index=1)

    if st.button("떡상 주제 추천 받기", type="primary", use_container_width=True):
        with st.spinner("네이버 뉴스 수집 중..."):
            if custom_keywords.strip():
                kw_list = [k.strip() for k in custom_keywords.split(",") if k.strip()]
            else:
                kw_list = None
            results = st.session_state.api.naver.search_trending_topics(
                keywords=kw_list, display_per_keyword=news_count
            )

        if not results:
            st.error("뉴스 검색 결과가 없습니다. API 키를 확인하세요.")
        else:
            st.success(f"총 {len(results)}개 뉴스 수집 완료. 스카이워크 AI 분석 중...")

            news_summary = ""
            for i, r in enumerate(results[:30]):
                news_summary += f"{i+1}. [{r.get('keyword','')}] {r['title']} - {r['description'][:100]}\n"

            with st.spinner("스카이워크 AI가 떡상 주제를 분석 중... (약 1-2분)"):
                analysis_prompt = f"""당신은 대한민국 최고의 유튜브 경제 사회 채널 기획자입니다.
아래는 오늘 수집된 최신 뉴스 목록입니다.

{news_summary}

위 뉴스를 분석하여 유튜브 영상으로 만들었을 때 조회수가 폭발할 가능성이 높은 주제 열 개를 추천하십시오.

반드시 아래 형식을 정확히 지켜서 출력하십시오. 다른 설명이나 인사말 없이 바로 시작하십시오.

주제1: (유튜브 영상 제목 형태로 작성) | 떡상확률: (숫자)%
출처: (참고한 뉴스 키워드)
대안A: (같은 주제의 다른 제목 버전)
대안B: (같은 주제의 또 다른 제목 버전)
태그: (관련 태그 다섯 개를 쉼표로 구분)
---
주제2: (유튜브 영상 제목 형태로 작성) | 떡상확률: (숫자)%
출처: (참고한 뉴스 키워드)
대안A: (같은 주제의 다른 제목 버전)
대안B: (같은 주제의 또 다른 제목 버전)
태그: (관련 태그 다섯 개를 쉼표로 구분)
---
(이하 주제10까지 반복)

떡상확률 판단 기준:
구십 퍼센트 이상: 사회적 분노나 공포를 자극하는 초대형 이슈. 지금 당장 올리면 터지는 주제.
칠십에서 팔십구 퍼센트: 대중의 관심이 높고 논쟁이 있는 주제. 타이밍이 중요.
오십에서 육십구 퍼센트: 꾸준한 관심은 있지만 폭발력은 중간.
오십 퍼센트 미만: 니치한 주제이거나 시의성이 약함.

제목 작성 규칙:
시청자가 클릭하지 않을 수 없는 강렬한 후킹 제목으로 작성하십시오.
숫자와 구체적인 키워드를 포함하십시오.
공포, 분노, 놀라움, 공감 중 하나의 감정을 자극하십시오."""

                result, error = st.session_state.api.generate_long(analysis_prompt)
                if error:
                    st.error(f"분석 실패: {error}")
                    st.session_state.news_results = results
                else:
                    st.session_state.news_results = results
                    st.session_state["topic_analysis"] = result
                    st.rerun()

    if st.session_state.get("topic_analysis"):
        st.markdown("### 떡상 주제 TOP 10")
        raw = st.session_state["topic_analysis"]

        topics = []
        blocks = raw.split("---")
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            topic = {"title": "", "prob": "0", "source": "", "alt_a": "", "alt_b": "", "tags": ""}
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                prob_match = re.search(r'주제\d+:\s*(.+?)\s*\|\s*떡상확률:\s*(\d+)%', line)
                if prob_match:
                    topic["title"] = prob_match.group(1).strip()
                    topic["prob"] = prob_match.group(2).strip()
                elif line.startswith("출처:"):
                    topic["source"] = line.split(":", 1)[1].strip()
                elif "대안A" in line or "대안 A" in line:
                    topic["alt_a"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif "대안B" in line or "대안 B" in line:
                    topic["alt_b"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif line.startswith("태그:"):
                    topic["tags"] = line.split(":", 1)[1].strip()
            if topic["title"]:
                topics.append(topic)

        if not topics:
            st.text_area("분석 원본 (파싱 실패 시 참고)", raw, height=400)
        else:
            for i, t in enumerate(topics):
                prob = int(t["prob"])
                if prob >= 90:
                    prob_color = "#FF0000"
                    prob_emoji = "🔥🔥🔥"
                    bar_color = "#FF0000"
                elif prob >= 70:
                    prob_color = "#FF6B00"
                    prob_emoji = "🔥🔥"
                    bar_color = "#FF6B00"
                elif prob >= 50:
                    prob_color = "#FFD700"
                    prob_emoji = "🔥"
                    bar_color = "#FFD700"
                else:
                    prob_color = "#888888"
                    prob_emoji = ""
                    bar_color = "#888888"

                st.markdown(f"""<div style="background:linear-gradient(135deg,#1A1F2E,#2A2F3E);border:1px solid #333;border-radius:12px;padding:1.2rem;margin-bottom:1rem;">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
<span style="color:#FFE66D;font-weight:800;font-size:1.1rem;">{i+1}. {t['title']}</span>
<span style="background:{prob_color};color:#fff;padding:4px 12px;border-radius:20px;font-weight:800;font-size:1rem;">{prob_emoji} {t['prob']}%</span>
</div>
<div style="background:#333;border-radius:8px;height:8px;margin-bottom:.5rem;">
<div style="background:{bar_color};border-radius:8px;height:8px;width:{t['prob']}%;"></div>
</div>
<div style="color:#aaa;font-size:.8rem;">출처: {t.get('source','')} | 태그: {t.get('tags','')}</div>
<div style="color:#888;font-size:.8rem;margin-top:.3rem;">대안A: {t.get('alt_a','')} | 대안B: {t.get('alt_b','')}</div>
</div>""", unsafe_allow_html=True)

                if st.button(f"이 주제로 대본 만들기", key=f"pick_topic_{i}"):
                    st.session_state.selected_topic = t["title"]
                    st.success(f"선택됨: {t['title']}")

        st.markdown("---")
        manual_topic = st.text_input("또는 직접 주제 입력", key="manual_input")
        if manual_topic:
            if st.button("이 주제로 진행", key="manual_btn"):
                st.session_state.selected_topic = manual_topic
                st.success(f"선택됨: {manual_topic}")

    elif st.session_state.news_results and not st.session_state.get("topic_analysis"):
        st.markdown(f"### 뉴스 원본 ({len(st.session_state.news_results)}건)")
        for i, news in enumerate(st.session_state.news_results[:20]):
            st.markdown(f"""<div class="news-card">
<div class="news-title">[{news.get('keyword','')}] {news['title']}</div>
<div class="news-desc">{news['description'][:150]}</div>
<div class="news-meta">{news.get('pubDate','')}</div>
</div>""", unsafe_allow_html=True)

    if st.session_state.selected_topic:
        st.info(f"현재 선택된 주제: **{st.session_state.selected_topic}**")


# === 탭2: 롱폼 대본 ===
with tab2:
    st.markdown("### 롱폼 대본 생성 (스카이워크)")
    if st.session_state.selected_topic:
        st.info(f"주제: {st.session_state.selected_topic}")

        if st.session_state.longform_script is None:
            if st.button("롱폼 대본 생성 시작", type="primary", use_container_width=True):
                with st.spinner("네이버 뉴스로 추가 자료 수집 중..."):
                    extra_news, _ = st.session_state.api.naver.search(
                        st.session_state.selected_topic, display=10, sort="date"
                    )
                    news_context = ""
                    if extra_news:
                        news_context = "\n".join([
                            f"- {n['title']}: {n['description']}" for n in extra_news[:10]
                        ])

                with st.spinner("스카이워크로 대본 생성 중... (약 2-5분)"):
                    prompt = f"""당신은 대한민국 최고의 유튜브 전문 작가이자 경제 사회 분석가입니다.
시청자의 클릭을 유발하는 강렬한 후킹과 끝까지 보게 만드는 시네마틱 스토리텔링을 구사하여 백만 조회수를 보장하는 대본을 작성합니다.

주제: {st.session_state.selected_topic}

참고 뉴스 자료:
{news_context}

출력 형식 (반드시 준수):
인사말이나 알겠습니다 같은 부연 설명 없이 아래 구분자를 사용하여 섹션을 완벽히 분리하여 출력하십시오.

제목: (오십 자 이내. 숫자는 아라비아 숫자 사용)

설명글: (약 이백 자)

태그: (해시태그 다섯 개)

(여기서부터 대본 본문. 대본이라는 단어 없이 바로 시작)

대본 규칙:
분량은 만 자 이상. 문장 수는 백 문장 이내.
시네마틱 오프닝으로 시작. 날짜나 정의로 시작하지 마십시오.
현장의 시각적 청각적 묘사로 영화처럼 시작하십시오.
구어체 사용. 시청자와 마주 앉아 이야기하듯 합니다체 사용.
논리 구조: 현상의 실태 → 심층 원인 분석 → 피해자 또는 현장의 목소리 → 사회적 역사적 비교 분석 → 시청자에게 던지는 묵직한 메시지.
모든 영어와 외래어는 한글 순화어로 교체.
모든 숫자는 읽기 방식 그대로 한글로 표기. 연도는 천구백구십구년 이천이십육년 형식.
특수기호 전면 제거. 마침표만 사용.
줄글 형태 유지. 번호 매기기 금지. 소제목 금지.
문장이 완전히 끝날 때만 마침표 사용. 마침표 반복 금지."""

                    result, error = st.session_state.api.generate_long(prompt)
                    if error:
                        st.error(f"대본 생성 실패: {error}")
                    elif result:
                        st.session_state.longform_script = result
                        lines = result.strip().split("\n")
                        meta = {"title": "", "desc": "", "tags": ""}
                        for line in lines:
                            stripped = line.strip()
                            if stripped.startswith("제목:"):
                                meta["title"] = stripped.replace("제목:", "").strip()
                            elif stripped.startswith("설명글:"):
                                meta["desc"] = stripped.replace("설명글:", "").strip()
                            elif stripped.startswith("태그:"):
                                meta["tags"] = stripped.replace("태그:", "").strip()
                        st.session_state.longform_meta = meta
                        st.rerun()
        else:
            meta = st.session_state.longform_meta or {}
            if meta.get("title"):
                st.markdown(f"**제목:** {meta['title']}")
            if meta.get("desc"):
                st.markdown(f"**설명글:** {meta['desc']}")
            if meta.get("tags"):
                st.markdown(f"**태그:** {meta['tags']}")
            st.text_area("대본 전문", st.session_state.longform_script, height=500)
            st.download_button(
                "대본 다운로드",
                st.session_state.longform_script,
                file_name="longform_script.txt"
            )

            st.markdown("---")
            st.markdown("**대본 문장 분리**")
            if st.button("문장 분리 실행"):
                raw = st.session_state.longform_script
                lines = raw.strip().split("\n")
                script_lines = []
                skip_prefixes = ["제목:", "설명글:", "태그:"]
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if any(stripped.startswith(p) for p in skip_prefixes):
                        continue
                    sentences = re.split(r'(?<=[.?!])\s*', stripped)
                    for s in sentences:
                        s = s.strip()
                        if len(s) > 5:
                            script_lines.append(s)
                st.session_state.scenes = script_lines[:100]
                st.success(f"총 {len(st.session_state.scenes)}개 문장 분리 완료")

            if st.session_state.scenes:
                st.markdown(f"분리된 문장: {len(st.session_state.scenes)}개")
                for i, s in enumerate(st.session_state.scenes[:10]):
                    st.caption(f"{i+1}. {s[:80]}...")
                if len(st.session_state.scenes) > 10:
                    st.caption(f"... 외 {len(st.session_state.scenes)-10}개")
    else:
        st.warning("탭1에서 먼저 주제를 선택하세요.")

# === 탭3: 쇼츠 대본 ===
with tab3:
    st.markdown("### 쇼츠 대본 생성 (롱폼에서 3편 추출)")
    if st.session_state.longform_script:
        if st.session_state.shorts_scripts is None:
            if st.button("쇼츠 3편 생성", type="primary", use_container_width=True):
                with st.spinner("쇼츠 대본 생성 중..."):
                    summary = st.session_state.longform_script[:3000]
                    meta = st.session_state.longform_meta or {}
                    title = meta.get("title", st.session_state.selected_topic or "")

                    prompt = f"""당신은 유튜브 쇼츠 백만 조회수 전문 대본 작가입니다.

아래 롱폼 대본에서 가장 흥미로운 부분을 골라 쇼츠 세 편의 대본을 작성하십시오.

롱폼 제목: {title}
롱폼 대본 요약:
{summary}

각 쇼츠 편 출력 형식:

=001=
제목: (오십 자 이내. 숫자는 아라비아 숫자)
상단제목 첫째 줄: (십오 자 이내)
상단제목 둘째 줄: (십오 자 이내)
설명글: (약 이백 자. 해시태그 세 개에서 다섯 개)
태그: (쉼표로 구분. 십오 개에서 이십 개)
순수 대본: (팔 문장에서 십오 문장. 마침표로 구분. 대본이라는 단어 쓰지 않음)

쇼츠 대본 규칙:
인사하지 않는다. 자기소개하지 않는다. 구독 좋아요 언급하지 않는다.
첫 문장은 현장 한가운데에 시청자를 던져 넣는 문장.
습니다체 기본에 까요체 질문을 섞는다.
모든 숫자는 한글 발음대로 표기.
특수기호 금지. 마침표만 사용.
번호 매기기 금지. 하나의 이야기 흐름으로 이어간다.
마지막 문장은 묵직한 여운 또는 다음 편 유도.

=002=
(같은 형식)

=003=
(같은 형식)"""

                    result, error = st.session_state.api.generate_long(prompt)
                    if error:
                        st.error(f"쇼츠 생성 실패: {error}")
                    elif result:
                        st.session_state.shorts_scripts = result
                        st.rerun()
        else:
            st.text_area("쇼츠 대본 전문", st.session_state.shorts_scripts, height=500)
            st.download_button(
                "쇼츠 대본 다운로드",
                st.session_state.shorts_scripts,
                file_name="shorts_scripts.txt"
            )
    else:
        st.warning("탭2에서 먼저 롱폼 대본을 생성하세요.")

# === 탭4: 이미지 생성 ===
with tab4:
    st.markdown("### 이미지 생성 (스카이워크)")
    mode = st.radio("이미지 생성 대상", ["롱폼 장면", "쇼츠 장면"], horizontal=True)

    if mode == "롱폼 장면":
        if st.session_state.scenes:
            total = len(st.session_state.scenes)
            st.markdown(f"총 **{total}개** 장면")
            aspect = st.selectbox("이미지 비율", ["16:9 (롱폼)", "9:16 (쇼츠)", "1:1"], key="lf_aspect")
            ar_map = {"16:9 (롱폼)": "16:9", "9:16 (쇼츠)": "9:16", "1:1": "1:1"}
            ar = ar_map[aspect]

            scene_idx = st.number_input("장면 번호", min_value=1, max_value=total, value=1, key="lf_scene_sel")
            st.text_area("선택된 장면 대사", st.session_state.scenes[scene_idx - 1], height=80, key="lf_scene_preview")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("이 장면 이미지 생성", key="gen_one_lf"):
                    idx = scene_idx - 1
                    with st.spinner(f"장면 {scene_idx} 이미지 생성 중..."):
                        prompt = f"SD 2D anime style, cinematic scene, {st.session_state.scenes[idx][:200]}, high quality, detailed, Korean sign visible, {ar} aspect ratio"
                        file_url, err = st.session_state.api.generate_image(prompt, aspect_ratio=ar)
                        if err:
                            st.error(err)
                        elif file_url:
                            if st.session_state.image_urls is None:
                                st.session_state.image_urls = {}
                            st.session_state.image_urls[idx] = file_url
                            st.success(f"장면 {scene_idx} 완료")
                            st.image(file_url, caption=f"장면 {scene_idx}")

            with col2:
                batch_start = st.number_input("시작 장면", min_value=1, max_value=total, value=1, key="batch_start")
                if st.button("6장 일괄 생성", key="gen_batch_lf"):
                    progress = st.progress(0)
                    for bi in range(6):
                        idx = batch_start - 1 + bi
                        if idx >= total:
                            break
                        progress.progress((bi + 1) / 6, text=f"장면 {idx + 1} 생성 중... ({bi + 1}/6)")
                        if st.session_state.image_urls and idx in st.session_state.image_urls:
                            continue
                        prompt = f"SD 2D anime style, cinematic scene, {st.session_state.scenes[idx][:200]}, high quality, detailed, Korean sign visible, {ar} aspect ratio"
                        file_url, err = st.session_state.api.generate_image(prompt, aspect_ratio=ar)
                        if file_url:
                            if st.session_state.image_urls is None:
                                st.session_state.image_urls = {}
                            st.session_state.image_urls[idx] = file_url
                    progress.progress(1.0, text="완료")

            if st.session_state.image_urls:
                st.markdown(f"### 생성된 이미지 ({len(st.session_state.image_urls)}개)")
                for idx in sorted(st.session_state.image_urls.keys()):
                    st.image(st.session_state.image_urls[idx], caption=f"장면 {idx + 1}", width=300)
        else:
            st.warning("탭2에서 문장 분리를 먼저 실행하세요.")
    else:
        st.info("쇼츠 장면 이미지 생성은 탭3에서 쇼츠 대본을 먼저 만든 후 진행하세요.")

# === 탭5: 영상 변환 ===
with tab5:
    st.markdown("### 이미지 → 영상 변환 (Kie AI)")
    if st.session_state.image_urls:
        duration = st.selectbox("영상 길이", ["5초", "10초"], key="vid_dur")
        dur_val = 5 if duration == "5초" else 10
        vid_idx = st.number_input("변환할 장면", min_value=1, max_value=len(st.session_state.image_urls), value=1, key="vid_sel2")

        if st.button("영상 변환 시작", key="conv_vid"):
            idx = vid_idx - 1
            sorted_keys = sorted(st.session_state.image_urls.keys())
            if idx < len(sorted_keys):
                real_idx = sorted_keys[idx]
                with st.spinner(f"장면 {real_idx + 1} 영상변환 중... (약 3-5분)"):
                    task_id, err = st.session_state.api.kie.image_to_video(
                        st.session_state.image_urls[real_idx], duration=dur_val
                    )
                    if err:
                        st.error(err)
                    else:
                        video_url, err2 = st.session_state.api.kie.wait_for_task(task_id)
                        if err2:
                            st.error(err2)
                        else:
                            if st.session_state.video_urls is None:
                                st.session_state.video_urls = {}
                            st.session_state.video_urls[real_idx] = video_url
                            st.success("변환 완료")
                            st.video(video_url)

        if st.session_state.video_urls:
            st.markdown(f"### 변환된 영상 ({len(st.session_state.video_urls)}개)")
            for idx in sorted(st.session_state.video_urls.keys()):
                st.video(st.session_state.video_urls[idx])
                st.caption(f"장면 {idx + 1}")
    else:
        st.info("탭4에서 이미지를 먼저 생성하세요.")

# === 탭6: 음성 생성 ===
with tab6:
    st.markdown("### 음성 생성 (인월드 TTS)")
    voice_id = st.text_input("음성 ID", value="Sarah", key="voice_input")

    if st.button("음성 목록 조회", key="list_v"):
        with st.spinner("조회 중..."):
            voices, err = st.session_state.api.inworld.list_voices()
            if err:
                st.error(err)
            else:
                for v in voices:
                    st.markdown(f"**{v.get('voiceId', '?')}** | {v.get('langCode', '?')}")

    if st.session_state.scenes:
        scene_for_tts = st.number_input("음성 생성할 장면", min_value=1, max_value=len(st.session_state.scenes), value=1, key="tts_sel")
        if st.button("이 장면 음성 생성", key="gen_one_tts"):
            with st.spinner("음성 생성 중..."):
                text = st.session_state.scenes[scene_for_tts - 1]
                audio_bytes, ts, err = st.session_state.api.inworld.synthesize(text, voice_id=voice_id)
                if err:
                    st.error(err)
                else:
                    if st.session_state.audio_data is None:
                        st.session_state.audio_data = {}
                    st.session_state.audio_data[scene_for_tts - 1] = audio_bytes
                    st.audio(audio_bytes, format="audio/mp3")
                    st.success("완료")

        if st.button("전체 음성 생성", key="gen_all_tts"):
            total = len(st.session_state.scenes)
            progress = st.progress(0)
            audio_data = {}
            for i, scene in enumerate(st.session_state.scenes):
                progress.progress((i + 1) / total, text=f"음성 {i + 1}/{total}")
                audio_bytes, ts, err = st.session_state.api.inworld.synthesize(scene, voice_id=voice_id)
                if not err and audio_bytes:
                    audio_data[i] = audio_bytes
            st.session_state.audio_data = audio_data
            progress.progress(1.0, text=f"완료 ({len(audio_data)}개)")

        if st.session_state.audio_data:
            st.markdown(f"### 생성된 음성 ({len(st.session_state.audio_data)}개)")
            for idx in sorted(st.session_state.audio_data.keys())[:10]:
                st.audio(st.session_state.audio_data[idx], format="audio/mp3")
                st.caption(f"장면 {idx + 1}")
    else:
        st.info("탭2에서 문장 분리를 먼저 실행하세요.")

# === 탭7: 자막 미세조정 ===
with tab7:
    st.markdown("### 자막 스타일 미세조정")
    st.caption("여기서 설정한 값이 최종 합성 시 자막에 적용됩니다.")

    settings = st.session_state.subtitle_settings

    col1, col2 = st.columns(2)
    with col1:
        settings["font_family"] = st.selectbox(
            "글꼴",
            ["NanumGothicBold", "NanumGothic", "NanumMyeongjo", "NanumBarunGothic",
             "MaruBuri", "Pretendard", "SUITE", "IBMPlexSansKR"],
            index=0, key="font_sel"
        )
        settings["font_size"] = st.slider("글자 크기 (px)", 16, 60, settings["font_size"], key="font_size_sl")
        settings["outline_width"] = st.slider("외곽선 두께 (px)", 0, 6, settings["outline_width"], key="outline_sl")

    with col2:
        settings["color"] = st.color_picker("글자 색상", settings["color"], key="font_color")
        settings["outline_color"] = st.color_picker("외곽선 색상", settings["outline_color"], key="outline_color")
        settings["position"] = st.selectbox("자막 위치", ["상단", "중앙", "하단"], index=2, key="sub_pos")

    if settings["position"] == "하단":
        settings["margin_bottom"] = st.slider("하단 여백 (px)", 10, 150, settings["margin_bottom"], key="margin_b")
    elif settings["position"] == "상단":
        settings["margin_top"] = st.slider("상단 여백 (px)", 10, 150, settings["margin_top"], key="margin_t")

    st.session_state.subtitle_settings = settings

    st.markdown("---")
    st.markdown("### 미리보기")
    preview_text = "이것은 자막 미리보기 문장입니다."
    if st.session_state.scenes:
        preview_text = st.session_state.scenes[0][:50]

    bg_color = "#1a1a2e"
    text_y = "80%" if settings["position"] == "하단" else ("20%" if settings["position"] == "상단" else "50%")

    st.markdown(f"""
<div style="
    background:{bg_color};
    width:100%;
    height:200px;
    border-radius:12px;
    position:relative;
    display:flex;
    align-items:{'flex-end' if settings['position'] == '하단' else ('flex-start' if settings['position'] == '상단' else 'center')};
    justify-content:center;
    padding:20px;
">
<span style="
    font-family:{settings['font_family']}, sans-serif;
    font-size:{settings['font_size']}px;
    color:{settings['color']};
    text-shadow: -{settings['outline_width']}px 0 {settings['outline_color']},
                  0 {settings['outline_width']}px {settings['outline_color']},
                  {settings['outline_width']}px 0 {settings['outline_color']},
                  0 -{settings['outline_width']}px {settings['outline_color']};
    text-align:center;
    {'margin-bottom:' + str(settings['margin_bottom']) + 'px;' if settings['position'] == '하단' else ''}
    {'margin-top:' + str(settings['margin_top']) + 'px;' if settings['position'] == '상단' else ''}
">{preview_text}</span>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**현재 설정값:**")
    st.json(settings)

# === 탭8: 최종 합성 ===
with tab8:
    st.markdown("### 최종 영상 합성")
    st.caption("영상 + 음성 + 자막을 합쳐서 최종 MP4를 생성합니다.")

    ready_video = len(st.session_state.video_urls) if st.session_state.video_urls else 0
    ready_audio = len(st.session_state.audio_data) if st.session_state.audio_data else 0

    st.markdown(f"**준비 현황:** 영상 {ready_video}개 | 음성 {ready_audio}개")
    st.markdown(f"**자막 설정:** {st.session_state.subtitle_settings['font_family']} / {st.session_state.subtitle_settings['font_size']}px / {st.session_state.subtitle_settings['position']}")

    if ready_video > 0 and ready_audio > 0:
        st.warning("Streamlit Cloud에서는 FFmpeg가 제한됩니다. 아래에서 개별 파일을 다운로드한 후 로컬에서 합성하거나, 로컬 환경에서 이 앱을 실행하세요.")

        if st.button("개별 파일 목록 표시", type="primary"):
            matched = 0
            for idx in sorted(st.session_state.video_urls.keys()):
                if idx in st.session_state.audio_data:
                    matched += 1
                    st.markdown(f"**장면 {idx + 1}**")
                    st.video(st.session_state.video_urls[idx])
                    st.audio(st.session_state.audio_data[idx], format="audio/mp3")
                    if st.session_state.scenes and idx < len(st.session_state.scenes):
                        st.caption(f"대사: {st.session_state.scenes[idx][:80]}")
                    st.markdown("---")
            st.success(f"영상+음성 매칭 완료: {matched}개 장면")

        st.markdown("---")
        st.markdown("**자막 설정 내보내기 (편집 프로그램용)**")
        sub_export = {
            "subtitle_settings": st.session_state.subtitle_settings,
            "scenes": st.session_state.scenes[:100] if st.session_state.scenes else []
        }
        st.download_button(
            "자막 설정 + 대사 JSON 다운로드",
            json.dumps(sub_export, ensure_ascii=False, indent=2),
            file_name="subtitle_config.json"
        )
    else:
        st.info("영상(탭5)과 음성(탭6)을 먼저 생성하세요.")

st.markdown('---')
st.markdown('<div style="text-align:center;color:#555;font-size:.8rem;">시니어 콘텐츠 팩토리 올인원 v2.0 | 네이버 뉴스 + 스카이워크 + Kie AI + 인월드 TTS</div>', unsafe_allow_html=True)
