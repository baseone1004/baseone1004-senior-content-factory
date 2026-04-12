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


# ── 네이버 뉴스 안전 호출 헬퍼 ──
def safe_naver_search(keyword, count):
    """네이버 뉴스 핸들러의 다양한 메서드 시그니처에 대응"""
    news_items = []
    raw_result = None

    # 방법1: search(keyword, display=count)
    try:
        raw_result = api.naver.search(keyword, display=count)
    except TypeError:
        pass
    except AttributeError:
        pass
    except Exception:
        pass

    # 방법2: search_trending_topics([keyword], count)
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

    # 방법3: search_news(keyword, count)
    if raw_result is None:
        try:
            raw_result = api.naver.search_news(keyword, count)
        except Exception:
            pass

    if raw_result is None:
        return []

    # 결과 정규화: 어떤 형태든 딕셔너리 리스트로 변환
    if isinstance(raw_result, dict):
        # {"items": [...]} 형태
        if "items" in raw_result:
            news_items = raw_result["items"]
        # {"news": [...]} 형태
        elif "news" in raw_result:
            news_items = raw_result["news"]
        # {"results": [...]} 형태
        elif "results" in raw_result:
            news_items = raw_result["results"]
        else:
            # 딕셔너리 자체가 하나의 뉴스 항목
            news_items = [raw_result]
    elif isinstance(raw_result, list):
        news_items = raw_result
    elif isinstance(raw_result, str):
        # 문자열이면 줄 단위로 분리
        lines = [l.strip() for l in raw_result.split("\n") if l.strip()]
        news_items = [{"title": l, "description": ""} for l in lines]
    else:
        return []

    # 각 item을 안전하게 딕셔너리로 변환
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
                # 안전한 뉴스 검색
                news = safe_naver_search(keyword, news_count)

                news_text = ""
                if news:
                    for item in news[:news_count]:
                        title = item.get("title", "") if isinstance(item, dict) else str(item)
                        desc = item.get("description", "") if isinstance(item, dict) else ""
                        # HTML 태그 제거
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
...
10번|제목: ...|확률: ...|출처: ...|대안: ...|태그: ..."""

                try:
                    raw = api.generate(prompt)
                except Exception as e:
                    raw = ""
                    st.error(f"AI 생성 실패: {e}")

                with st.expander("AI 원본 응답 (디버그)"):
                    st.code(raw if raw else "(응답 없음)")

                # 파싱
                topics = []
                if raw:
                    lines = raw.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        # 다양한 패턴 매칭
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
                    st.warning("주제 파싱에 실패했습니다. 위 디버그 창에서 AI 응답을 확인하세요.")

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
- 첫 세 문장 안에 열린 고리 설치
- 접속사는 근데 그래서 결국 알고보니 문제는 사용
- 한 문장 15자에서 40자
- 번호 매기기 금지
- 습니다체 기본에 까요체 질문 혼합
- 충격에서 공감에서 분노에서 반전에서 여운 감정곡선
- 각 편 8문장에서 12문장 (40초 이내 분량)
- 모든 영어와 숫자는 한글로
- 특수기호는 마침표만 사용

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

                    # 파싱
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

                        m = re.search(r'설명글:\s*(.+?)(?=\n태그:|\n=장면|\nTag)', ep_content, re.DOTALL)
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
                # ── 제목 영역 ──
                title_col, top_col = st.columns([3, 2])
                with title_col:
                    st.subheader(f"편 {ep['num']}. {ep['title']}")
                with top_col:
                    if ep.get("top_line1") or ep.get("top_line2"):
                        st.markdown(f"**상단제목**")
                        st.write(f"{ep.get('top_line1', '')}")
                        st.write(f"{ep.get('top_line2', '')}")

                # ── 태그 영역 (제목 옆) ──
                if ep.get("tags"):
                    with st.container(border=True):
                        st.markdown("**태그**")
                        st.write(ep["tags"])

                # ── 설명글 영역 ──
                if ep.get("description"):
                    with st.container(border=True):
                        st.markdown("**설명글**")
                        st.write(ep["description"])

                # ── 대본 영역 ──
                with st.container(border=True):
                    st.markdown("**대본 (40초 이내)**")
                    script_text = ep.get("script", "(대본 없음)")
                    st.write(script_text)
                    if script_text and script_text != "(대본 없음)":
                        char_count = len(script_text)
                        est_sec = min(40, max(10, char_count // 7))
                        st.caption(f"글자 수: {char_count}자 | 예상: 약 {est_sec}초")

                # ── 장면 프롬프트 (접이식) ──
                if ep.get("scenes"):
                    with st.expander(f"장면 프롬프트 ({len(ep['scenes'])}개)"):
                        for j, scene in enumerate(ep["scenes"]):
                            st.markdown(f"**장면 {j+1}**")
                            st.write(f"대사: {scene['dialogue']}")
                            st.code(scene["prompt"], language="text")

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

    img_tab_long, img_tab_shorts = st.tabs(["롱폼 이미지 (16:9)", "쇼츠 이미지 (9:16)"])

    # ── 롱폼 이미지 ──
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
- 한글 간판 자연스럽게 배치

형식:
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
                            p = p.strip()
                            try:
                                img_url = api.generate_image(p, aspect_ratio="16:9")
                                generated.append({"prompt": p, "url": img_url, "index": idx + 1})
                            except Exception as e:
                                generated.append({"prompt": p, "url": None, "error": str(e), "index": idx + 1})
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
                            st.error(f"실패: {img.get('error', '알 수 없는 오류')}")
                        with st.expander("프롬프트"):
                            st.code(img["prompt"], language="text")
        else:
            st.warning("먼저 [롱폼 대본] 탭에서 대본을 생성하세요.")

    # ── 쇼츠 이미지 ──
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
                                    ep_images.append({"url": img_url, "scene": j + 1, "dialogue": scene["dialogue"]})
                                except Exception as e:
                                    ep_images.append({"url": None, "scene": j + 1, "error": str(e),
                                                      "dialogue": scene["dialogue"]})
                                progress.progress((j + 1) / len(ep["scenes"]))
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
                    else:
                        st.info("장면 프롬프트가 없습니다")

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
    checks = {
        "선택된 주제": st.session_state.selected_topic or "없음",
        "롱폼 대본": "생성됨" if st.session_state.longform_metadata else "없음",
        "쇼츠 대본": f"{len(st.session_state.shorts_data)}편" if st.session_state.shorts_data else "없음",
        "롱폼 이미지": f"{len(st.session_state.generated_images_longform)}장" if st.session_state.generated_images_longform else "없음",
        "레퍼런스 이미지": "업로드됨" if st.session_state.reference_image else "없음",
    }
    for k, v in checks.items():
        if v == "없음":
            st.warning(f"{k}: {v}")
        else:
            st.success(f"{k}: {v}")
