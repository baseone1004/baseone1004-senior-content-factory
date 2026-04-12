import streamlit as st
import json
import re
import os
import base64
import time
from datetime import datetime

# ── 페이지 설정 ──
st.set_page_config(page_title="시니어 콘텐츠 팩토리 올인원", layout="wide")

# ── 세션 스테이트 초기화 ──
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


# ── API 핸들러 로드 ──
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


# ── 주제 동기화 헬퍼 ──
def sync_topic():
    t = st.session_state.selected_topic
    if t:
        st.session_state["longform_topic"] = t
        st.session_state["shorts_topic"] = t


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
                for svc, status in result.items():
                    if status.get("status") == "connected":
                        st.success(f"{svc}: 연결됨")
                    else:
                        st.warning(f"{svc}: {status.get('message', '실패')}")
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
                try:
                    news = api.naver.search(keyword, display=news_count)
                except Exception:
                    try:
                        news = api.naver.search_trending_topics(keyword, news_count)
                    except Exception:
                        news = []

                news_text = ""
                if news:
                    for item in news[:news_count]:
                        title = item.get("title", "")
                        desc = item.get("description", "")
                        news_text += f"- {title}: {desc}\n"

                prompt = f"""아래 뉴스 트렌드를 분석해서 유튜브 영상 주제 10개를 추천해줘.

뉴스 트렌드:
{news_text if news_text else '(뉴스 없음 - 일반 트렌드 기반 추천)'}

키워드: {keyword}

반드시 아래 형식으로만 출력해. 다른 말 붙이지 마.

1번|제목: (주제 제목)|확률: (떡상 확률 퍼센트)|출처: (관련 뉴스 키워드)|대안: (비슷한 대안 주제)|태그: (관련 태그 3개 쉼표 구분)
2번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ...
...
10번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ..."""

                try:
                    raw = api.generate(prompt)
                except Exception as e:
                    raw = ""
                    st.error(f"AI 생성 실패: {e}")

                with st.expander("AI 원본 응답 (디버그)"):
                    st.code(raw)

                # 파싱
                topics = []
                if raw:
                    lines = raw.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        # 다양한 패턴 매칭
                        m = re.search(r'제목:\s*(.+?)[\|]', line)
                        if m:
                            title_val = m.group(1).strip().strip("*").strip()
                            prob_m = re.search(r'확률:\s*(.+?)[\|]', line)
                            source_m = re.search(r'출처:\s*(.+?)[\|]', line)
                            alt_m = re.search(r'대안:\s*(.+?)[\|]', line)
                            tag_m = re.search(r'태그:\s*(.+)', line)
                            topics.append({
                                "title": title_val,
                                "probability": prob_m.group(1).strip() if prob_m else "",
                                "source": source_m.group(1).strip() if source_m else "",
                                "alternative": alt_m.group(1).strip() if alt_m else "",
                                "tags": tag_m.group(1).strip() if tag_m else "",
                            })

                    st.session_state.topics_list = topics

    # 추천 주제 목록 표시 & 선택
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

                    # 메타데이터 추출
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

    # 결과 표시
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
            "대본 다운로드 (TXT)",
            data=st.session_state.longform_script,
            file_name=f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
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
관점1 몰락 원인 분석
관점2 전성기 실태
관점3 내부 폭로
관점4 비교 분석
관점5 수익 구조
관점6 피해자 시점
관점7 현재 상황
관점8 미래 전망

대본 핵심 원칙:
- 인사 자기소개 구독 좋아요 언급 금지
- 첫 문장은 현장 한가운데에 시청자를 던져 넣는 문장
- 첫 세 문장 안에 열린 고리(질문은 던졌는데 답은 아직 안 준 상태) 설치
- 접속사는 근데 그래서 결국 알고보니 문제는 사용. 그리고 또한 뿐만아니라 한편 금지
- 한 문장 15~40자. 50자 넘으면 두 개로 쪼갬
- 번호 매기기 금지. 하나의 이야기 흐름
- 습니다체 기본 + 까요체 질문 혼합
- 충격→공감→분노/안타까움→반전→여운 감정곡선
- 5초마다 새 미끼 (근데 여기서 더 충격적인건요 / 알고보면 이게 끝이 아닙니다 등)
- 마무리는 묵직한 여운 또는 다음 편 유도
- 마지막 문장 끝이 첫 문장 시작과 자연스럽게 이어지게
- 각 편 8~12문장 (40초 이내 분량)
- 모든 영어/외래어는 한글로, 모든 숫자는 한글로
- 특수기호는 마침표만 사용

이미지 프롬프트 규칙:
- 모든 프롬프트는 9:16 세로 비율
- 장면 수 = 대사 문장 수 (1:1 매칭)
- 모든 프롬프트 맨 앞에 반드시 SD 2D anime style, 붙임
- 주인공 등장 장면은 맨 뒤에 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 9:16 vertical aspect ratio
- 주인공 미등장 장면은 맨 뒤에 9:16 vertical aspect ratio
- 대상설명/실제인물 장면 = 주인공 없음
- 나레이션/리액션/질문/감상 장면 = 주인공 등장
- 주인공 복장은 상황에 맞게 (한 편 안 복장 변경 최대 1번)
- 한글 간판 자연스럽게 배치
- 유흥업소 여성은 실루엣 처리

상단제목 규칙:
- 한 줄당 최대 15자 이내, 두 줄 구성
- 첫째 줄은 궁금증 유발 또는 충격적 사실
- 둘째 줄은 핵심 키워드 또는 반전 포인트
- 숫자는 아라비아 숫자

반드시 아래 형식으로만 출력해. 다른 말 일절 붙이지 마.

=001=
제목: (50자 이내)
상단제목첫째줄: (15자 이내)
상단제목둘째줄: (15자 이내)
설명글: (약 200자. 해시태그 3~5개 포함)
태그: (쉼표 구분 15~20개)
순수대본: (문장만 마침표로 나열. 번호 없이.)
=장면001=
대사: (첫번째 문장)
프롬프트: SD 2D anime style, (영어 장면묘사), (접미어)
=장면002=
대사: (두번째 문장)
프롬프트: SD 2D anime style, (영어 장면묘사), (접미어)
(대사 문장 수만큼 반복)

=002=
(위와 동일 형식)

=003=
(위와 동일 형식)"""

                try:
                    raw = api.generate(prompt)
                    st.session_state.shorts_raw = raw

                    # 파싱
                    episodes = []
                    ep_blocks = re.split(r'=00(\d)=', raw)
                    # ep_blocks: ['', '1', '내용1', '2', '내용2', '3', '내용3']

                    i = 1
                    while i < len(ep_blocks) - 1:
                        ep_num = ep_blocks[i].strip()
                        ep_content = ep_blocks[i + 1].strip()
                        ep = {"num": ep_num, "raw": ep_content}

                        # 제목
                        m = re.search(r'제목:\s*(.+)', ep_content)
                        ep["title"] = m.group(1).strip() if m else f"쇼츠 {ep_num}편"

                        # 상단제목
                        m1 = re.search(r'상단제목첫째줄:\s*(.+)', ep_content)
                        m2 = re.search(r'상단제목둘째줄:\s*(.+)', ep_content)
                        ep["top_line1"] = m1.group(1).strip() if m1 else ""
                        ep["top_line2"] = m2.group(1).strip() if m2 else ""

                        # 설명글
                        m = re.search(r'설명글:\s*(.+?)(?=\n태그:|\n=장면)', ep_content, re.DOTALL)
                        ep["description"] = m.group(1).strip() if m else ""

                        # 태그
                        m = re.search(r'태그:\s*(.+)', ep_content)
                        ep["tags"] = m.group(1).strip() if m else ""

                        # 순수대본
                        m = re.search(r'순수대본:\s*(.+?)(?=\n=장면)', ep_content, re.DOTALL)
                        ep["script"] = m.group(1).strip() if m else ""

                        # 장면들
                        scenes = []
                        scene_blocks = re.findall(
                            r'=장면\d+=\s*대사:\s*(.+?)\s*프롬프트:\s*(.+?)(?=\n=장면|\n=00|$)',
                            ep_content, re.DOTALL
                        )
                        for dialogue, prompt_text in scene_blocks:
                            scenes.append({
                                "dialogue": dialogue.strip(),
                                "prompt": prompt_text.strip()
                            })
                        ep["scenes"] = scenes

                        episodes.append(ep)
                        i += 2

                    st.session_state.shorts_data = episodes

                except Exception as e:
                    st.error(f"생성 실패: {e}")

    # ── 쇼츠 결과 표시 (1편/2편/3편 칸 분리) ──
    if st.session_state.shorts_data:
        with st.expander("AI 원본 응답 (디버그)"):
            st.code(st.session_state.shorts_raw)

        for ep in st.session_state.shorts_data:
            st.divider()
            with st.container(border=True):
                # 제목 + 상단제목
                title_col, tag_col = st.columns([3, 2])
                with title_col:
                    st.subheader(f"편 {ep['num']}. {ep['title']}")
                    if ep.get("top_line1") or ep.get("top_line2"):
                        st.caption(f"상단: {ep.get('top_line1', '')} / {ep.get('top_line2', '')}")
                with tag_col:
                    if ep.get("tags"):
                        st.text_area("태그", value=ep["tags"], height=80,
                                     key=f"tags_ep{ep['num']}", disabled=True)

                # 설명글
                if ep.get("description"):
                    with st.container(border=True):
                        st.markdown("**설명글**")
                        st.write(ep["description"])

                # 태그 (설명 아래 다시 한번 보기 좋게)
                if ep.get("tags"):
                    tags_list = [t.strip() for t in ep["tags"].split(",")]
                    tag_html = " ".join([f"`{t}`" for t in tags_list[:10]])
                    st.caption(f"주요 태그: {tag_html}")

                # 대본
                with st.container(border=True):
                    st.markdown("**대본 (40초 이내)**")
                    st.write(ep.get("script", "(대본 없음)"))
                    if ep.get("script"):
                        char_count = len(ep["script"])
                        st.caption(f"글자 수: {char_count}자 | 예상: 약 {max(1, char_count // 250 * 10)}초")

                # 장면 프롬프트 (접이식)
                if ep.get("scenes"):
                    with st.expander(f"장면 프롬프트 ({len(ep['scenes'])}개)"):
                        for j, scene in enumerate(ep["scenes"]):
                            st.markdown(f"**장면 {j+1}**")
                            st.write(f"대사: {scene['dialogue']}")
                            st.code(scene["prompt"], language="text")

        # 전체 다운로드
        st.divider()
        st.download_button(
            "쇼츠 3편 전체 다운로드 (TXT)",
            data=st.session_state.shorts_raw,
            file_name=f"shorts_3set_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )


# ════════════════════════════════════════════
# 탭4: 이미지 생성 (롱폼 / 쇼츠 분리)
# ════════════════════════════════════════════
with tab4:
    st.header("이미지 생성")

    img_tab_long, img_tab_shorts = st.tabs(["롱폼 이미지", "쇼츠 이미지"])

    # ── 롱폼 이미지 ──
    with img_tab_long:
        st.subheader("롱폼 대본 기반 이미지 생성")

        if st.session_state.longform_metadata and st.session_state.longform_metadata.get("body"):
            body = st.session_state.longform_metadata["body"]
            # 문단 단위로 장면 분리
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [p.strip() for p in body.split("\n") if p.strip()]

            st.info(f"총 {len(paragraphs)}개 문단 감지됨")

            # 프롬프트 생성
            if st.button("롱폼 이미지 프롬프트 생성", key="gen_long_prompts"):
                with st.spinner("프롬프트 생성 중..."):
                    prompt_req = f"""아래 대본의 각 문단에 대해 이미지 프롬프트를 생성해줘.

규칙:
- 모든 프롬프트는 SD 2D anime style, 로 시작
- 16:9 가로 비율
- 주인공 등장 장면은 맨 뒤에 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 16:9 horizontal aspect ratio
- 주인공 미등장 장면은 맨 뒤에 16:9 horizontal aspect ratio
- 한글 간판 자연스럽게 배치

형식 (문단 수만큼 반복):
[장면1]
내용요약: (한글 한줄)
프롬프트: SD 2D anime style, (영어 장면묘사), (접미어)
[장면2]
...

대본:
{body[:3000]}"""
                    try:
                        result = api.generate(prompt_req)
                        st.session_state["longform_prompts_raw"] = result
                    except Exception as e:
                        st.error(f"프롬프트 생성 실패: {e}")

            # 프롬프트 결과 표시
            if st.session_state.get("longform_prompts_raw"):
                st.text_area("생성된 프롬프트", value=st.session_state["longform_prompts_raw"],
                             height=400, key="long_prompts_display")

                # 개별 프롬프트 파싱 및 이미지 생성
                prompts = re.findall(r'프롬프트:\s*(SD 2D anime style,.+?)(?=\n\[장면|\n$|$)',
                                     st.session_state["longform_prompts_raw"], re.DOTALL)
                if prompts:
                    st.info(f"총 {len(prompts)}개 프롬프트 감지")

                    if st.button("전체 이미지 생성 (롱폼)", key="gen_long_images"):
                        progress = st.progress(0)
                        generated = []
                        for idx, p in enumerate(prompts):
                            p = p.strip()
                            try:
                                img_url = api.generate_image(p, aspect_ratio="16:9")
                                generated.append({"prompt": p, "url": img_url, "index": idx + 1})
                            except Exception as e:
                                generated.append({"prompt": p, "url": None, "error": str(e), "index": idx + 1})
                            progress.progress((idx + 1) / len(prompts))
                        st.session_state.generated_images_longform = generated

            # 생성된 이미지 표시
            if st.session_state.generated_images_longform:
                st.subheader("생성된 롱폼 이미지")
                cols = st.columns(3)
                for idx, img in enumerate(st.session_state.generated_images_longform):
                    with cols[idx % 3]:
                        st.caption(f"장면 {img['index']}")
                        if img.get("url"):
                            st.image(img["url"], use_container_width=True)
                        else:
                            st.error(f"실패: {img.get('error', '알 수 없는 오류')}")
                        with st.expander("프롬프트"):
                            st.code(img["prompt"], language="text")
        else:
            st.warning("먼저 탭2에서 롱폼 대본을 생성하세요.")

    # ── 쇼츠 이미지 ──
    with img_tab_shorts:
        st.subheader("쇼츠 대본 기반 이미지 생성 (9:16 세로)")

        if st.session_state.shorts_data:
            for ep in st.session_state.shorts_data:
                with st.container(border=True):
                    st.markdown(f"**편 {ep['num']}. {ep['title']}**")

                    if ep.get("scenes"):
                        # 프롬프트 목록 표시
                        for j, scene in enumerate(ep["scenes"]):
                            st.caption(f"장면{j+1}: {scene['dialogue'][:30]}...")
                            st.code(scene["prompt"], language="text")

                        # 편별 이미지 생성
                        if st.button(f"편 {ep['num']} 이미지 생성", key=f"gen_shorts_img_{ep['num']}"):
                            progress = st.progress(0)
                            ep_images = []
                            for j, scene in enumerate(ep["scenes"]):
                                try:
                                    img_url = api.generate_image(scene["prompt"], aspect_ratio="9:16")
                                    ep_images.append({"url": img_url, "scene": j + 1, "dialogue": scene["dialogue"]})
                                except Exception as e:
                                    ep_images.append({"url": None, "scene": j + 1, "error": str(e),
                                                      "dialogue": scene["dialogue"]})
                                progress.progress((j + 1) / len(ep["scenes"]))

                            # 저장
                            key = f"shorts_images_ep{ep['num']}"
                            st.session_state[key] = ep_images

                        # 생성된 이미지 표시
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
                    else:
                        st.info("장면 프롬프트가 없습니다")

            # 전체 쇼츠 이미지 일괄 생성
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
                                ep_images.append({"url": img_url, "scene": j + 1,
                                                  "dialogue": scene["dialogue"]})
                            except Exception as e:
                                ep_images.append({"url": None, "scene": j + 1, "error": str(e),
                                                  "dialogue": scene["dialogue"]})
                            progress.progress((j + 1) / len(ep["scenes"]))
                        st.session_state[f"shorts_images_ep{ep['num']}"] = ep_images
                st.success("전체 쇼츠 이미지 생성 완료")
                st.rerun()
        else:
            st.warning("먼저 탭3에서 쇼츠 대본을 생성하세요.")


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
        text = st.session_state.longform_metadata.get("body", "")
    else:
        # 쇼츠 전체 대본 합치기
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
                        else:
                            audio, timestamps = result
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
# 탭7: 자막 설정
# ════════════════════════════════════════════
with tab7:
    st.header("자막 설정")

    col1, col2 = st.columns(2)
    with col1:
        font_name = st.selectbox("폰트", ["NanumGothicBold", "NanumMyeongjo", "MalgunGothic"],
                                 key="sub_font")
        font_size = st.slider("폰트 크기", 20, 80, 48, key="sub_size")
        font_color = st.color_picker("글자 색상", "#FFFFFF", key="sub_color")
        outline_color = st.color_picker("외곽선 색상", "#000000", key="sub_outline")
        outline_width = st.slider("외곽선 두께", 0, 10, 3, key="sub_outline_w")
    with col2:
        position = st.selectbox("위치", ["하단", "중앙", "상단"], key="sub_pos")
        margin_v = st.slider("세로 여백", 0, 200, 30, key="sub_margin")
        st.divider()
        st.subheader("미리보기")
        preview_style = f"font-family:{font_name}; font-size:{font_size//2}px; color:{font_color}; " \
                        f"-webkit-text-stroke: {outline_width//2}px {outline_color};"
        st.markdown(
            f'<div style="background:black; padding:40px; text-align:center; border-radius:10px;">'
            f'<p style="{preview_style}">자막 미리보기 샘플</p></div>',
            unsafe_allow_html=True
        )


# ════════════════════════════════════════════
# 탭8: 최종 합치기
# ════════════════════════════════════════════
with tab8:
    st.header("최종 합치기")
    st.info("Streamlit Cloud에서는 FFmpeg를 직접 실행할 수 없습니다. 아래에서 상태를 확인하고 로컬에서 합성하세요.")

    st.subheader("현재 상태")
    status_items = {
        "선택된 주제": st.session_state.selected_topic or "없음",
        "롱폼 대본": "생성됨" if st.session_state.longform_metadata else "없음",
        "쇼츠 대본": f"{len(st.session_state.shorts_data)}편" if st.session_state.shorts_data else "없음",
        "롱폼 이미지": f"{len(st.session_state.generated_images_longform)}장" if st.session_state.generated_images_longform else "없음",
        "레퍼런스 이미지": "업로드됨" if st.session_state.reference_image else "없음",
    }
    for k, v in status_items.items():
        if v == "없음":
            st.warning(f"{k}: {v}")
        else:
            st.success(f"{k}: {v}")
