import streamlit as st
import re
import json
import time
import base64

# ─── 초기화 ───
if "api" not in st.session_state:
    from utils.api_handler import APIHandler
    st.session_state.api = APIHandler()

DEFAULT_KEYS = {
    "news_results": None,
    "topic_analysis": None,
    "selected_topic": "",
    "longform_script": "",
    "longform_meta": None,
    "shorts_scripts": None,
    "shorts_raw": "",
    "scenes": [],
    "image_urls": [],
    "video_urls": [],
    "audio_data": None,
    "reference_image": None,
    "generated_images": {},
    "subtitle_settings": {
        "font_family": "NanumGothicBold",
        "font_size": 48,
        "font_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "position": "bottom",
        "margin_bottom": 60,
        "margin_top": 60,
    },
}

for k, v in DEFAULT_KEYS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── 페이지 설정 ───
st.set_page_config(page_title="시니어 콘텐츠 팩토리", page_icon="🎬", layout="wide")

st.markdown("""
<style>
.copy-box {
    background: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    font-size: 14px;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 400px;
    overflow-y: auto;
}
.section-header {
    background: linear-gradient(90deg, #f38ba8, #fab387);
    color: #1e1e2e;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: bold;
    margin: 16px 0 8px 0;
}
.topic-card {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 10px;
    padding: 16px;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)

# ─── 사이드바 ───
with st.sidebar:
    st.title("🎬 시니어 콘텐츠 팩토리")
    st.markdown("---")

    if st.button("🔌 API 연결 테스트"):
        try:
            results = st.session_state.api.test_all()
            for name, (ok, msg) in results.items():
                icon = "✅" if ok else "❌"
                st.write(f"{icon} {name}: {msg}")
        except Exception as e:
            st.error(f"테스트 실패: {e}")

    st.markdown("---")
    st.subheader("🖼️ 레퍼런스 이미지")
    ref_url = st.text_input("이미지 URL", value=st.session_state.get("ref_url", ""))
    if ref_url:
        st.session_state.ref_url = ref_url
        st.session_state.reference_image = ref_url
        try:
            st.image(ref_url, width=200)
        except Exception:
            st.warning("이미지를 불러올 수 없습니다.")

    ref_file = st.file_uploader("또는 파일 업로드", type=["png", "jpg", "jpeg", "webp"])
    if ref_file:
        st.session_state.reference_image = ref_file
        st.image(ref_file, width=200)

    st.markdown("---")
    if st.button("🔄 전체 초기화"):
        for k, v in DEFAULT_KEYS.items():
            st.session_state[k] = v
        st.rerun()

# ─── 탭 구성 ───
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "1.주제추천", "2.롱폼대본", "3.쇼츠대본", "4.이미지생성",
    "5.영상변환", "6.음성합성", "7.자막설정", "8.최종합성"
])

# === 탭1: 주제 추천 (네이버 뉴스) ===
with tab1:
    st.header("📰 실시간 뉴스 기반 주제 추천")

    col_kw, col_cnt = st.columns([3, 1])
    with col_kw:
        keyword = st.text_input("검색 키워드", value="경제", placeholder="예: AI, 부동산, 주식, 건강")
    with col_cnt:
        news_count = st.selectbox("뉴스 수", [10, 15, 20, 30], index=1)

    if st.button("🔥 떡상 주제 추천 받기", use_container_width=True):
        with st.spinner("네이버 뉴스 수집 중..."):
            # naver_news_handler의 search 메서드 직접 사용
            news_items, err = st.session_state.api.naver.search(keyword, display=news_count)

        if err:
            st.error(f"뉴스 수집 실패: {err}")
        elif not news_items:
            st.warning("수집된 뉴스가 없습니다.")
        else:
            st.session_state.news_results = news_items
            summary = ""
            for i, item in enumerate(news_items):
                summary += f"{i+1}. {item['title']}\n   {item['description'][:100]}\n\n"

            analysis_prompt = (
                "아래는 최신 뉴스 목록입니다.\n\n"
                f"{summary}\n\n"
                "이 뉴스들을 분석해서 유튜브 영상으로 만들면 조회수가 높을 주제 10개를 추천해주세요.\n"
                "각 주제마다 아래 형식으로 작성하세요.\n\n"
                "주제1: (제목)\n"
                "떡상확률: (숫자)%\n"
                "근거: (한 줄 설명)\n"
                "출처뉴스: (참고한 뉴스 제목)\n"
                "대체제목1: (다른 제목 후보)\n"
                "대체제목2: (다른 제목 후보)\n"
                "태그: (관련 태그 5개, 쉼표 구분)\n\n"
                "주제2: ...\n"
                "(같은 형식으로 10개)\n\n"
                "떡상확률은 50%에서 99% 사이로 현실적으로 매겨주세요.\n"
                "조회수 폭발 가능성이 높은 순서대로 정렬해주세요."
            )

            with st.spinner("AI가 떡상 주제를 분석 중..."):
                result, gen_err = st.session_state.api.generate_long(analysis_prompt)

            if gen_err:
                st.error(f"분석 실패: {gen_err}")
            else:
                st.session_state.topic_analysis = result

    # 결과 표시
    if st.session_state.topic_analysis:
        st.subheader("🎯 떡상 주제 TOP 10")
        raw = st.session_state.topic_analysis

        topics = []
        current = {}
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            m_topic = re.match(r"주제\s*(\d+)\s*[:：]\s*(.+)", line)
            if m_topic:
                if current:
                    topics.append(current)
                current = {"num": m_topic.group(1), "title": m_topic.group(2).strip(), "prob": 70,
                           "source": "", "alts": [], "tags": "", "reason": ""}
                continue
            m_prob = re.match(r"떡상\s*확률\s*[:：]\s*(\d+)", line)
            if m_prob and current:
                current["prob"] = int(m_prob.group(1))
                continue
            m_src = re.match(r"출처\s*뉴스\s*[:：]\s*(.+)", line)
            if m_src and current:
                current["source"] = m_src.group(1).strip()
                continue
            m_alt = re.match(r"대체\s*제목\s*\d*\s*[:：]\s*(.+)", line)
            if m_alt and current:
                current["alts"].append(m_alt.group(1).strip())
                continue
            m_tag = re.match(r"태그\s*[:：]\s*(.+)", line)
            if m_tag and current:
                current["tags"] = m_tag.group(1).strip()
                continue
            m_reason = re.match(r"근거\s*[:：]\s*(.+)", line)
            if m_reason and current:
                current["reason"] = m_reason.group(1).strip()
                continue
        if current:
            topics.append(current)

        for i, t in enumerate(topics[:10]):
            prob = t.get("prob", 70)
            if prob >= 90:
                bar_color = "🔴"
            elif prob >= 70:
                bar_color = "🟠"
            elif prob >= 50:
                bar_color = "🟡"
            else:
                bar_color = "⚪"

            st.markdown(f"""<div class="topic-card">
<b>{bar_color} {i+1}. {t.get('title','')}</b><br>
떡상 확률: <b>{prob}%</b><br>
근거: {t.get('reason','')}<br>
출처: {t.get('source','')}<br>
태그: {t.get('tags','')}<br>
대체 제목: {', '.join(t.get('alts',[]))}
</div>""", unsafe_allow_html=True)
            st.progress(min(prob, 100) / 100)

            if st.button(f"이 주제로 선택 → {t.get('title','')[:30]}", key=f"pick_{i}"):
                st.session_state.selected_topic = t.get("title", "")
                st.success(f"선택됨: {t.get('title','')}")

    st.markdown("---")
    manual_topic = st.text_input("✏️ 직접 주제 입력", value=st.session_state.selected_topic)
    if st.button("이 주제로 진행 →"):
        st.session_state.selected_topic = manual_topic
        st.success(f"주제 설정 완료: {manual_topic}")


# === 탭2: 롱폼 대본 ===
with tab2:
    st.header("📝 롱폼 대본 생성 (약 30분 분량)")

    topic = st.text_input("영상 주제", value=st.session_state.selected_topic, key="longform_topic")
    target_minutes = st.slider("목표 분량 (분)", min_value=10, max_value=45, value=30)
    target_chars = target_minutes * 350

    disclaimer = (
        "\n\n본 영상은 일반적인 정보 전달 및 개인적인 의견이며 투자 권유가 아닙니다.\n"
        "이 영상은 AI로 제작된 영상입니다."
    )

    if st.button("🎬 롱폼 대본 생성", use_container_width=True):
        if not topic:
            st.warning("주제를 입력하세요.")
        else:
            longform_prompt = (
                f"주제: {topic}\n\n"
                f"아래 형식에 맞춰 유튜브 롱폼 영상 대본을 작성하세요.\n"
                f"대본 분량은 반드시 {target_chars}자 이상으로 작성하세요. "
                f"이것은 약 {target_minutes}분 분량입니다.\n\n"
                "출력 형식:\n"
                "=제목=\n(영상 제목)\n\n"
                "=태그=\n(쉼표로 구분된 태그 15~20개)\n\n"
                "=설명=\n(영상 설명 200자 내외. 마지막에 반드시 다음 두 줄을 포함)\n"
                "본 영상은 일반적인 정보 전달 및 개인적인 의견이며 투자 권유가 아닙니다.\n"
                "이 영상은 AI로 제작된 영상입니다.\n\n"
                "=설명태그=\n(설명용 해시태그 5~10개, #붙여서)\n\n"
                "=대본=\n(본문 대본. 구어체. 습니다/까요 혼합체. "
                "인사 금지. 자기소개 금지. 구독좋아요 금지. "
                f"반드시 {target_chars}자 이상 작성)\n\n"
                "중요: 대본은 충분히 길게, 상세하게, 사례와 수치를 풍부하게 포함하여 작성하세요.\n"
                "짧게 끝내지 마세요. 최소 30분은 읽을 수 있는 분량이어야 합니다."
            )

            with st.spinner(f"약 {target_minutes}분 분량 대본 생성 중... (시간이 걸릴 수 있습니다)"):
                result, err = st.session_state.api.generate_long(longform_prompt)

            if err:
                st.error(f"생성 실패: {err}")
            elif result:
                st.session_state.longform_script = result

                meta = {"title": "", "tags": "", "desc": "", "desc_tags": "", "script": ""}
                section_map = {
                    "제목": "title", "타이틀": "title",
                    "태그": "tags", "해시태그": "tags",
                    "설명": "desc", "설명글": "desc",
                    "설명태그": "desc_tags", "설명 태그": "desc_tags",
                    "대본": "script", "본문": "script", "스크립트": "script",
                }

                current_section = None
                current_lines = []
                for line in result.split("\n"):
                    stripped = line.strip()
                    m = re.match(r"^=\s*(.+?)\s*=$", stripped)
                    if m:
                        if current_section and current_section in meta:
                            meta[current_section] = "\n".join(current_lines).strip()
                        label = m.group(1)
                        current_section = section_map.get(label)
                        current_lines = []
                        continue
                    if current_section:
                        current_lines.append(line)

                if current_section and current_section in meta:
                    meta[current_section] = "\n".join(current_lines).strip()

                if not meta["title"]:
                    for line in result.split("\n"):
                        s = line.strip()
                        if s.startswith("제목:") or s.startswith("제목 :"):
                            meta["title"] = s.split(":", 1)[1].strip()
                            break
                        elif s.startswith("#") and not s.startswith("##"):
                            meta["title"] = s.lstrip("#").strip()
                            break

                if meta["desc"] and "투자 권유가 아닙니다" not in meta["desc"]:
                    meta["desc"] += disclaimer
                elif not meta["desc"]:
                    meta["desc"] = f"{topic}에 대한 심층 분석 영상입니다.{disclaimer}"

                if not meta["script"]:
                    meta["script"] = result

                st.session_state.longform_meta = meta
                st.success("대본 생성 완료!")

    if st.session_state.longform_meta:
        meta = st.session_state.longform_meta

        st.markdown('<div class="section-header">📌 제목</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="copy-box">{meta.get("title","")}</div>', unsafe_allow_html=True)
        st.download_button("📋 제목 복사", meta.get("title", ""), file_name="title.txt", key="dl_title")

        st.markdown('<div class="section-header">🏷️ 태그</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="copy-box">{meta.get("tags","")}</div>', unsafe_allow_html=True)
        st.download_button("📋 태그 복사", meta.get("tags", ""), file_name="tags.txt", key="dl_tags")

        st.markdown('<div class="section-header">📄 설명</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="copy-box">{meta.get("desc","")}</div>', unsafe_allow_html=True)
        st.download_button("📋 설명 복사", meta.get("desc", ""), file_name="desc.txt", key="dl_desc")

        st.markdown('<div class="section-header">🔖 설명 태그</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="copy-box">{meta.get("desc_tags","")}</div>', unsafe_allow_html=True)
        st.download_button("📋 설명태그 복사", meta.get("desc_tags", ""), file_name="desc_tags.txt", key="dl_dtags")

        script_text = meta.get("script", "")
        char_count = len(script_text)
        est_minutes = round(char_count / 350, 1)
        st.markdown(f'<div class="section-header">📜 대본 ({char_count}자 / 약 {est_minutes}분)</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="copy-box">{script_text}</div>', unsafe_allow_html=True)
        st.download_button("📋 대본 복사", script_text, file_name="script.txt", key="dl_script")

        full_text = (
            f"=제목=\n{meta.get('title','')}\n\n"
            f"=태그=\n{meta.get('tags','')}\n\n"
            f"=설명=\n{meta.get('desc','')}\n\n"
            f"=설명태그=\n{meta.get('desc_tags','')}\n\n"
            f"=대본=\n{script_text}"
        )
        st.download_button("💾 전체 저장", full_text, file_name="longform_full.txt", key="dl_full")


# === 탭3: 쇼츠 대본 ===
with tab3:
    st.header("🎬 유튜브 쇼츠 10편 세트 생성")

    shorts_topic = st.text_input("쇼츠 대주제", value=st.session_state.selected_topic, key="shorts_topic")

    if st.button("⚡ 쇼츠 10편 세트 생성", use_container_width=True):
        if not shorts_topic:
            st.warning("대주제를 입력하세요.")
        else:
            ref_img_note = ""
            if st.session_state.reference_image:
                ref_img_note = (
                    "주인공이 등장하는 장면의 프롬프트 끝에 반드시 "
                    "main character exactly matching the uploaded reference image, "
                    "same face, same hairstyle, same features, consistent character design, "
                    "9:16 vertical aspect ratio 를 붙여라. "
                    "주인공이 안 나오는 장면은 9:16 vertical aspect ratio 로만 끝내라.\n\n"
                )

            shorts_prompt = (
                "너는 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가야.\n\n"
                + "대주제: " + shorts_topic + "\n\n"
                + "이 대주제에서 파생되는 연관성 높고 중복 없는 쇼츠 10편을 세트로 기획해.\n\n"
                + "10개 소주제 도출 관점 (최소 각 1개씩, 나머지 2개는 가장 흥미로운 관점에서 추가):\n"
                + "1.몰락원인분석 2.전성기실태 3.내부폭로 4.비교분석 "
                + "5.수익구조 6.피해자시점 7.현재상황 8.미래전망\n\n"
                + "대본 규칙:\n"
                + "- 각 편 8~15문장, 1분 이내 분량\n"
                + "- 첫 문장은 현장 투척/통념 파괴/공감 소환/충격 수치/질문 관통 중 하나\n"
                + "- 인사,자기소개,구독좋아요 절대 금지\n"
                + "- 습니다+까요 혼합체, 구어체\n"
                + "- 한 문장 15~40자, 50자 넘으면 쪼개기\n"
                + "- 번호매기기 금지, 소제목 금지\n"
                + "- 모든 숫자 한글 표기, 영어 한글 순화\n"
                + "- 특수기호는 마침표만\n"
                + "- 마지막 문장은 여운 또는 다음편 유도\n\n"
                + "이미지 프롬프트 규칙:\n"
                + "- 모든 프롬프트 앞에 SD 2D anime style, 을 붙여라\n"
                + "- 대사 문장 수 = 장면 수 (1:1 매칭)\n"
                + ref_img_note
                + "- 유흥업소 여성은 반드시 silhouette 처리\n"
                + "- 한글 간판은 내용과 연관된 것만\n\n"
                + "출력 형식 (정확히 따를 것):\n\n"
                + "[편1 시작]\n"
                + "제목: (50자 이내)\n"
                + "상단제목 첫째 줄: (15자 이내)\n"
                + "상단제목 둘째 줄: (15자 이내)\n"
                + "설명글: (약 200자, 해시태그 3~5개 포함)\n"
                + "태그: (쉼표 구분, 15~20개)\n\n"
                + "순수 대본:\n"
                + "(문장만 마침표로 나열. 번호 없음)\n\n"
                + "[장면1]\n"
                + "대사: (첫 번째 문장)\n"
                + "프롬프트: SD 2D anime style, (영어 장면 묘사), (접미어)\n\n"
                + "[장면2]\n"
                + "대사: (두 번째 문장)\n"
                + "프롬프트: SD 2D anime style, (영어 장면 묘사), (접미어)\n\n"
                + "(대사 문장 수만큼 장면 반복)\n"
                + "[편1 끝]\n\n"
                + "[편2 시작]\n"
                + "(동일 형식)\n"
                + "[편2 끝]\n\n"
                + "(편3~편10까지 동일)\n\n"
                + "반드시 10편 전부 빠짐없이 완성해라."
            )

            with st.spinner("쇼츠 10편 세트 생성 중... (시간이 걸립니다)"):
                result, err = st.session_state.api.generate_long(shorts_prompt)

            if err:
                st.error(f"생성 실패: {err}")
            elif result:
                st.session_state.shorts_raw = result
                st.success("쇼츠 10편 세트 생성 완료!")

    if st.session_state.shorts_raw:
        raw = st.session_state.shorts_raw

        episodes = []
        pattern = re.compile(r"\[편(\d+)\s*시작\](.*?)\[편\1\s*끝\]", re.DOTALL)
        matches = pattern.findall(raw)

        if matches:
            for num, content in matches:
                ep = {"num": int(num), "raw": content.strip()}

                m_title = re.search(r"제목\s*[:：]\s*(.+)", content)
                ep["title"] = m_title.group(1).strip() if m_title else f"편 {num}"

                m_top1 = re.search(r"상단제목\s*첫째\s*줄\s*[:：]\s*(.+)", content)
                m_top2 = re.search(r"상단제목\s*둘째\s*줄\s*[:：]\s*(.+)", content)
                ep["top1"] = m_top1.group(1).strip() if m_top1 else ""
                ep["top2"] = m_top2.group(1).strip() if m_top2 else ""

                m_desc = re.search(r"설명글\s*[:：]\s*(.+?)(?=태그\s*[:：]|\n\n)", content, re.DOTALL)
                ep["desc"] = m_desc.group(1).strip() if m_desc else ""

                m_tags = re.search(r"태그\s*[:：]\s*(.+?)(?=\n\n|순수)", content, re.DOTALL)
                ep["tags"] = m_tags.group(1).strip() if m_tags else ""

                m_script = re.search(r"순수\s*대본\s*[:：]?\s*\n(.*?)(?=\[장면|\Z)", content, re.DOTALL)
                ep["script"] = m_script.group(1).strip() if m_script else ""

                scenes = []
                scene_pattern = re.compile(
                    r"\[장면(\d+)\]\s*\n대사\s*[:：]\s*(.+?)\n프롬프트\s*[:：]\s*(.+?)(?=\[장면|\[편|\Z)",
                    re.DOTALL
                )
                for s_num, s_line, s_prompt in scene_pattern.findall(content):
                    scenes.append({
                        "num": int(s_num),
                        "line": s_line.strip(),
                        "prompt": s_prompt.strip()
                    })
                ep["scenes"] = scenes
                episodes.append(ep)
        else:
            episodes = [{"num": 0, "raw": raw, "title": "전체 결과", "script": raw, "scenes": [],
                         "top1": "", "top2": "", "desc": "", "tags": ""}]

        st.session_state.shorts_scripts = episodes

        for ep in episodes:
            with st.expander(f"📹 편 {ep['num']}: {ep.get('title', '')}", expanded=False):
                if ep.get("top1") or ep.get("top2"):
                    st.markdown(f"상단제목: {ep.get('top1','')} / {ep.get('top2','')}")

                st.markdown('<div class="section-header">제목</div>', unsafe_allow_html=True)
                st.code(ep.get("title", ""), language=None)

                if ep.get("desc"):
                    st.markdown('<div class="section-header">설명글</div>', unsafe_allow_html=True)
                    st.code(ep["desc"], language=None)

                if ep.get("tags"):
                    st.markdown('<div class="section-header">태그</div>', unsafe_allow_html=True)
                    st.code(ep["tags"], language=None)

                if ep.get("script"):
                    st.markdown('<div class="section-header">순수 대본</div>', unsafe_allow_html=True)
                    st.code(ep["script"], language=None)

                if ep.get("scenes"):
                    st.markdown('<div class="section-header">장면 목록</div>', unsafe_allow_html=True)
                    for sc in ep["scenes"]:
                        st.markdown(f"장면 {sc['num']}")
                        st.markdown(f"대사: {sc['line']}")
                        st.code(sc["prompt"], language=None)

                ep_text = (
                    f"제목: {ep.get('title','')}\n"
                    f"상단제목: {ep.get('top1','')} / {ep.get('top2','')}\n"
                    f"설명글: {ep.get('desc','')}\n"
                    f"태그: {ep.get('tags','')}\n\n"
                    f"순수 대본:\n{ep.get('script','')}\n\n"
                )
                for sc in ep.get("scenes", []):
                    ep_text += f"[장면{sc['num']}]\n대사: {sc['line']}\n프롬프트: {sc['prompt']}\n\n"

                st.download_button(
                    f"💾 편 {ep['num']} 저장",
                    ep_text,
                    file_name=f"shorts_ep{ep['num']}.txt",
                    key=f"dl_ep_{ep['num']}"
                )

        st.download_button("💾 전체 쇼츠 저장", raw, file_name="shorts_all.txt", key="dl_shorts_all")


# === 탭4: 이미지 생성 ===
with tab4:
    st.header("🖼️ 이미지 생성")

    if st.session_state.shorts_scripts:
        episodes = st.session_state.shorts_scripts
        ep_options = [f"편 {ep['num']}: {ep.get('title','')[:30]}" for ep in episodes]
        selected_ep_idx = st.selectbox("편 선택", range(len(ep_options)), format_func=lambda x: ep_options[x])
        ep = episodes[selected_ep_idx]

        if ep.get("scenes"):
            st.write(f"총 {len(ep['scenes'])}개 장면")

            if st.button("🎨 전체 장면 이미지 생성"):
                progress = st.progress(0)
                for i, sc in enumerate(ep["scenes"]):
                    with st.spinner(f"장면 {sc['num']} 이미지 생성 중..."):
                        img_url, img_err = st.session_state.api.generate_image(sc["prompt"])
                        if img_url:
                            st.image(img_url, caption=f"장면 {sc['num']}: {sc['line'][:30]}")
                            st.session_state.generated_images[f"ep{ep['num']}_sc{sc['num']}"] = img_url
                        else:
                            st.error(f"장면 {sc['num']} 실패: {img_err}")
                    progress.progress((i + 1) / len(ep["scenes"]))
                st.success("이미지 생성 완료!")

            for sc in ep["scenes"]:
                with st.expander(f"장면 {sc['num']}: {sc['line'][:40]}"):
                    st.code(sc["prompt"], language=None)
                    if st.button(f"이 장면 생성", key=f"gen_img_{ep['num']}_{sc['num']}"):
                        with st.spinner("생성 중..."):
                            img_url, img_err = st.session_state.api.generate_image(sc["prompt"])
                            if img_url:
                                st.image(img_url)
                                st.session_state.generated_images[f"ep{ep['num']}_sc{sc['num']}"] = img_url
                            else:
                                st.error(img_err)
        else:
            st.info("이 편에 장면 데이터가 없습니다.")
    else:
        st.info("먼저 탭3에서 쇼츠 대본을 생성하세요.")

    st.markdown("---")
    st.subheader("직접 프롬프트 입력")
    custom_prompt = st.text_area("이미지 프롬프트", height=100)
    if st.button("🎨 직접 생성"):
        if custom_prompt:
            with st.spinner("생성 중..."):
                img_url, img_err = st.session_state.api.generate_image(custom_prompt)
                if img_url:
                    st.image(img_url)
                else:
                    st.error(img_err)


# === 탭5: 영상 변환 ===
with tab5:
    st.header("🎥 이미지 → 영상 변환 (Kie AI)")

    img_url_input = st.text_input("이미지 URL")
    vid_duration = st.selectbox("영상 길이 (초)", [3, 5, 7, 10], index=1)

    if st.button("🎬 영상 변환 시작"):
        if img_url_input:
            with st.spinner("영상 변환 태스크 생성 중..."):
                task_id, vid_err = st.session_state.api.kie.image_to_video(img_url_input, duration=vid_duration)
                if task_id:
                    st.info(f"태스크 ID: {task_id}")
                    with st.spinner("영상 변환 중... (최대 10분 소요)"):
                        video_url, wait_err = st.session_state.api.kie.wait_for_task(task_id)
                        if video_url:
                            st.video(video_url)
                            st.success(f"영상 URL: {video_url}")
                        else:
                            st.error(f"변환 실패: {wait_err}")
                else:
                    st.error(f"태스크 생성 실패: {vid_err}")
        else:
            st.warning("이미지 URL을 입력하세요.")

    if st.session_state.generated_images:
        st.markdown("---")
        st.subheader("생성된 이미지에서 변환")
        for key, url in st.session_state.generated_images.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{key}: {url[:60]}...")
            with col2:
                if st.button(f"변환", key=f"vid_{key}"):
                    with st.spinner("변환 중..."):
                        tid, terr = st.session_state.api.kie.image_to_video(url, duration=5)
                        if tid:
                            v_url, v_err = st.session_state.api.kie.wait_for_task(tid)
                            if v_url:
                                st.video(v_url)
                            else:
                                st.error(v_err)
                        else:
                            st.error(terr)


# === 탭6: 음성 합성 ===
with tab6:
    st.header("🔊 음성 합성 (Inworld TTS)")

    # 음성 목록 가져오기
    voice_options = ["Sarah", "James", "Emily", "Michael"]
    try:
        voices, v_err = st.session_state.api.inworld.list_voices()
        if voices:
            voice_options = [v.get("voiceId", v.get("name", "unknown")) for v in voices]
    except Exception:
        pass

    tts_text = st.text_area("음성으로 변환할 텍스트", height=200)
    voice_id = st.selectbox("음성", voice_options)

    if st.button("🔊 음성 합성"):
        if tts_text:
            with st.spinner("음성 합성 중..."):
                audio_data, timestamps, tts_err = st.session_state.api.inworld.synthesize(tts_text, voice_id)
                if audio_data:
                    st.audio(audio_data, format="audio/mp3")
                    st.session_state.audio_data = audio_data
                    st.download_button("💾 음성 다운로드", audio_data, file_name="tts_output.mp3")
                else:
                    st.error(f"합성 실패: {tts_err}")
        else:
            st.warning("텍스트를 입력하세요.")

    if st.session_state.shorts_scripts:
        st.markdown("---")
        st.subheader("쇼츠 대본에서 음성 합성")
        for ep in st.session_state.shorts_scripts:
            if ep.get("script"):
                if st.button(f"편 {ep['num']} 대본 합성", key=f"tts_ep_{ep['num']}"):
                    with st.spinner(f"편 {ep['num']} 음성 합성 중..."):
                        audio, ts, terr = st.session_state.api.inworld.synthesize(ep["script"], voice_id)
                        if audio:
                            st.audio(audio, format="audio/mp3")
                            st.download_button(
                                f"💾 편 {ep['num']} 음성",
                                audio,
                                file_name=f"tts_ep{ep['num']}.mp3",
                                key=f"dl_tts_{ep['num']}"
                            )
                        else:
                            st.error(terr)


# === 탭7: 자막 설정 ===
with tab7:
    st.header("📝 자막 스타일 설정")

    ss = st.session_state.subtitle_settings

    col1, col2 = st.columns(2)
    with col1:
        ss["font_family"] = st.selectbox("글꼴", [
            "NanumGothicBold", "NanumGothic", "NanumMyeongjo",
            "NanumBarunGothic", "MalgunGothic", "Dotum", "Gulim"
        ], index=0)
        ss["font_size"] = st.slider("글자 크기", 20, 100, ss["font_size"])
        ss["font_color"] = st.color_picker("글자 색상", ss["font_color"])

    with col2:
        ss["outline_color"] = st.color_picker("테두리 색상", ss["outline_color"])
        ss["outline_width"] = st.slider("테두리 두께", 0, 10, ss["outline_width"])
        ss["position"] = st.selectbox("자막 위치", ["top", "center", "bottom"], index=2)

    ss["margin_top"] = st.slider("상단 여백", 0, 200, ss["margin_top"])
    ss["margin_bottom"] = st.slider("하단 여백", 0, 200, ss["margin_bottom"])

    st.session_state.subtitle_settings = ss

    st.markdown("---")
    st.subheader("미리보기")
    preview_text = st.text_input("미리보기 텍스트", "자막 미리보기 테스트")

    align_items_val = "flex-end"
    if ss["position"] == "top":
        align_items_val = "flex-start"
    elif ss["position"] == "center":
        align_items_val = "center"

    st.markdown(f"""
    <div style="
        background: #000;
        width: 270px;
        height: 480px;
        position: relative;
        border-radius: 12px;
        display: flex;
        align-items: {align_items_val};
        justify-content: center;
        padding: {ss['margin_top']}px 10px {ss['margin_bottom']}px 10px;
    ">
        <p style="
            font-family: {ss['font_family']}, sans-serif;
            font-size: {ss['font_size']//2}px;
            color: {ss['font_color']};
            text-shadow: -{ss['outline_width']}px -{ss['outline_width']}px 0 {ss['outline_color']},
                         {ss['outline_width']}px -{ss['outline_width']}px 0 {ss['outline_color']},
                         -{ss['outline_width']}px {ss['outline_width']}px 0 {ss['outline_color']},
                         {ss['outline_width']}px {ss['outline_width']}px 0 {ss['outline_color']};
            text-align: center;
            margin: 0;
        ">{preview_text}</p>
    </div>
    """, unsafe_allow_html=True)

    st.json(ss)


# === 탭8: 최종 합성 ===
with tab8:
    st.header("🎬 최종 합성")

    st.info(
        "최종 영상 합성(영상 + 음성 + 자막 합치기)은 FFmpeg가 필요합니다.\n"
        "Streamlit Cloud에서는 FFmpeg 실행이 제한되므로 로컬 환경 또는 "
        "CapCut/DaVinci Resolve 같은 편집 도구를 활용하세요."
    )

    st.markdown("---")
    st.subheader("작업 현황 요약")

    status_items = {
        "주제 선택": bool(st.session_state.selected_topic),
        "롱폼 대본": bool(st.session_state.longform_meta),
        "쇼츠 대본": bool(st.session_state.shorts_scripts),
        "이미지 생성": bool(st.session_state.generated_images),
        "음성 합성": bool(st.session_state.audio_data),
        "자막 설정": True,
    }

    for name, done in status_items.items():
        icon = "✅" if done else "⬜"
        st.write(f"{icon} {name}")

    st.markdown("---")
    st.subheader("FFmpeg 명령어 생성기 (로컬용)")

    video_path = st.text_input("영상 파일 경로", "input_video.mp4")
    audio_path = st.text_input("음성 파일 경로", "tts_output.mp3")
    output_path = st.text_input("출력 파일 경로", "final_output.mp4")

    ss = st.session_state.subtitle_settings
    font_color_hex = ss["font_color"].replace("#", "")
    outline_hex = ss["outline_color"].replace("#", "")

    alignment = "2" if ss["position"] == "bottom" else ("6" if ss["position"] == "top" else "5")

    ffmpeg_cmd = (
        f'ffmpeg -i "{video_path}" -i "{audio_path}" '
        f'-vf "subtitles=sub.srt:force_style=\''
        f'FontName={ss["font_family"]},'
        f'FontSize={ss["font_size"]},'
        f'PrimaryColour=&H00{font_color_hex}&,'
        f'OutlineColour=&H00{outline_hex}&,'
        f'OutLine={ss["outline_width"]},'
        f'Alignment={alignment},'
        f'MarginV={ss["margin_bottom"]}'
        f'\'" '
        f'-c:v libx264 -c:a aac "{output_path}"'
    )

    st.code(ffmpeg_cmd, language="bash")
    st.download_button("📋 FFmpeg 명령어 복사", ffmpeg_cmd, file_name="ffmpeg_cmd.txt")
