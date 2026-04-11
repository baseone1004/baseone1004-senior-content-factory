import streamlit as st
import re
import os
import time
import tempfile
from utils.api_handler import APIHandler
from prompts.topic_recommend import TOPIC_RECOMMEND_ECONOMY, TOPIC_RECOMMEND_SENIOR
from prompts.economy_script import ECONOMY_SCRIPT_PROMPT
from prompts.senior_longform import SENIOR_LONGFORM_META, SENIOR_LONGFORM_PART
from prompts.shorts_prompt import SHORTS_PROMPT
from prompts.script_polish import SCRIPT_POLISH_PROMPT

st.set_page_config(page_title="시니어 콘텐츠 팩토리 올인원", page_icon="🎬", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = APIHandler()
for key in ["topics","selected_topic_data","longform_result","polished_result","shorts_result","scenes","image_urls","image_paths","video_urls","audio_data"]:
    if key not in st.session_state:
        st.session_state[key] = None
if "step" not in st.session_state:
    st.session_state.step = "home"
if "content_mode" not in st.session_state:
    st.session_state.content_mode = "economy"
if "language" not in st.session_state:
    st.session_state.language = "한국어"

# ===== 기존 파싱 함수들 (그대로 유지) =====

def parse_topics(raw_text):
    topics = []
    pattern = r"주제\d+:\s*(.+?)\s*\|\s*떡상확률:\s*(\d+)%"
    lines = raw_text.strip().split("\n")
    current = None
    for line in lines:
        line = line.strip()
        if not line or line == "---":
            continue
        match = re.match(pattern, line)
        if match:
            if current and current["title"]:
                topics.append(current)
            current = {"title": match.group(1).strip(), "prob": match.group(2).strip(), "alt_a": "", "alt_b": "", "tags": "", "source": ""}
        elif current:
            if line.startswith("출처:"):
                current["source"] = line.split(":", 1)[1].strip()
            elif "대안A" in line or "대안 A" in line:
                current["alt_a"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif "대안B" in line or "대안 B" in line:
                current["alt_b"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("태그:"):
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
        if stripped.startswith("제목:"):
            result["title"] = stripped.replace("제목:", "").strip()
        elif stripped.startswith("설명글:"):
            result["desc"] = stripped.replace("설명글:", "").strip()
        elif stripped.startswith("태그:") and not result["tags"]:
            result["tags"] = stripped.replace("태그:", "").strip()
        elif stripped in ["=대본 시작=", "=대본시작="]:
            in_script = True
        elif stripped in ["=대본 끝=", "=대본끝="]:
            in_script = False
        elif in_script:
            script_lines.append(line)
    result["script"] = "\n".join(script_lines).strip()
    if not result["script"]:
        result["script"] = raw_text
    return result

def parse_shorts(raw_text):
    shorts = []
    parts = re.split(r'=\s*0{0,2}[1-9]\s*=', raw_text)
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
            if any(stripped.startswith(k) for k in ["제목:", "タイトル:"]):
                s["title"] = stripped.split(":", 1)[1].strip()
            elif any(k in stripped for k in ["상단제목첫째줄:", "상단제목 첫째줄:", "상단제목 첫째 줄:"]):
                s["top1"] = stripped.split(":", 1)[1].strip()
            elif any(k in stripped for k in ["상단제목둘째줄:", "상단제목 둘째줄:", "상단제목 둘째 줄:"]):
                s["top2"] = stripped.split(":", 1)[1].strip()
            elif any(stripped.startswith(k) for k in ["설명글:", "説明文:"]):
                s["desc"] = stripped.split(":", 1)[1].strip()
            elif any(stripped.startswith(k) for k in ["태그:", "タグ:"]):
                s["tags"] = stripped.split(":", 1)[1].strip()
            elif any(stripped.startswith(k) for k in ["고정댓글:", "固定コメント:"]):
                s["pinned"] = stripped.split(":", 1)[1].strip()
            elif any(k in stripped for k in ["순수대본:", "純粋台本:", "台本:"]):
                rest = stripped.split(":", 1)[1].strip()
                if rest:
                    script_lines.append(rest)
                in_script = True
            elif in_script:
                if stripped.startswith("="):
                    in_script = False
                else:
                    script_lines.append(stripped)
        s["script"] = "\n".join([l for l in script_lines if l.strip()]).strip()
        if s["title"]:
            shorts.append(s)
    return shorts

def render_shorts_card(num, s):
    st.markdown(f"""<div style="background:linear-gradient(135deg,#1A1F2E,#2A2F3E);border:2px solid #FF6B6B;border-radius:16px;padding:1.5rem;margin-bottom:1.5rem;">
<div style="background:linear-gradient(90deg,#FF6B6B,#FF8E53);color:#fff;font-size:1.2rem;font-weight:800;padding:.5rem 1.5rem;border-radius:25px;display:inline-block;margin-bottom:1rem;">쇼츠 {num}편</div></div>""", unsafe_allow_html=True)
    if s["title"]:
        st.markdown(f'**제목:** {s["title"]}')
    if s["top1"] or s["top2"]:
        st.markdown(f'**상단제목:** {s["top1"]} / {s["top2"]}')
    if s["desc"]:
        st.markdown(f'**설명글:** {s["desc"]}')
    if s["tags"]:
        st.markdown(f'**태그:** {s["tags"]}')
    if s["script"]:
        st.text_area(f"대본 {num}편", s["script"], height=150, key=f"shorts_script_{num}")
    if s["pinned"]:
        st.markdown(f'**고정댓글:** {s["pinned"]}')

PART_NAMES = ["파트1: 도입부와 일상", "파트2: 갈등의 시작", "파트3: 위기와 절정", "파트4: 반전과 전환", "파트5: 결말과 여운"]

# ===== CSS =====
st.markdown("""<style>
.main-title{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#FF6B6B,#FFE66D);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:.5rem}
.sub-title{font-size:1.1rem;color:#888;text-align:center;margin-bottom:2rem}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="main-title">시니어 콘텐츠 팩토리 올인원</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">스카이워크 + Kie AI + 인월드 TTS | 주제추천 → 대본 → 이미지 → 영상 → 음성 → 합성</div>', unsafe_allow_html=True)

# ===== 사이드바 =====
with st.sidebar:
    st.markdown("### 채널 설정")
    channel_type = st.selectbox("채널 유형", ["경제/사회 (한국 채널)", "시니어 (한국 채널)", "시니어 (일본 채널)"])
    if channel_type == "경제/사회 (한국 채널)":
        language, content_mode = "한국어", "economy"
    elif channel_type == "시니어 (한국 채널)":
        language, content_mode = "한국어", "senior"
    else:
        language, content_mode = "일본어", "senior"
    st.session_state.content_mode = content_mode
    st.session_state.language = language
    st.markdown("---")
    st.markdown("### API 연결")
    if st.button("연결 테스트", use_container_width=True):
        ok, msg = st.session_state.api.test_connection()
        if ok:
            st.success(msg)
        else:
            st.error(msg)
    st.markdown("---")
    if st.button("처음으로", use_container_width=True):
        for key in ["topics","selected_topic_data","longform_result","polished_result","shorts_result","scenes","image_urls","image_paths","video_urls","audio_data"]:
            st.session_state[key] = None
        st.session_state.step = "home"
        st.rerun()

content_mode = st.session_state.content_mode
language = st.session_state.language

# ===== 메인 탭 =====
main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs(["📝 대본", "🖼️ 이미지", "🎬 영상변환", "🔊 음성", "🎥 최종합성"])

# ===== 탭1: 대본 (기존 기능 유지) =====
with main_tab1:
    if st.session_state.step == "home":
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            if st.button("주제 추천 받기 (스카이워크)", use_container_width=True, type="primary"):
                with st.spinner("스카이워크로 주제 분석 중..."):
                    if content_mode == "economy":
                        prompt = TOPIC_RECOMMEND_ECONOMY
                    else:
                        prompt = TOPIC_RECOMMEND_SENIOR.format(language=language)
                    result, error = st.session_state.api.generate_long(prompt)
                    if error:
                        st.error(error)
                    else:
                        st.session_state.topics = parse_topics(result)
                        st.session_state.raw_topics = result
                        st.session_state.step = "topics"
                        st.rerun()

    elif st.session_state.step == "topics":
        st.markdown("### 추천 주제 목록")
        topics = st.session_state.topics
        if not topics:
            st.warning("주제 파싱 실패. 원본:")
            st.text(st.session_state.get("raw_topics", ""))
        else:
            for i, t in enumerate(topics):
                st.markdown(f"**{t['title']}** | 떡상확률 {t['prob']}%")
                if t["alt_a"]:
                    st.caption(f"대안A: {t['alt_a']} | 대안B: {t['alt_b']}")
                if st.button("이 주제 선택", key=f"s_{i}"):
                    st.session_state.selected_topic_data = t
                    st.session_state.step = "result"
                    st.rerun()

    elif st.session_state.step == "result":
        t = st.session_state.selected_topic_data
        if st.session_state.longform_result is None:
            st.markdown("### 대본 생성 중... (스카이워크)")
            if content_mode == "economy":
                with st.spinner("롱폼 대본 생성 중..."):
                    prompt = ECONOMY_SCRIPT_PROMPT.format(topic=t["title"])
                    result, error = st.session_state.api.generate_long(prompt)
                    if error:
                        st.error(error)
                    else:
                        st.session_state.longform_result = result
                        st.rerun()
            else:
                progress_bar = st.progress(0, text="줄거리 설계 중...")
                meta_prompt = SENIOR_LONGFORM_META.format(topic=t["title"], language=language)
                outline, error = st.session_state.api.generate_long(meta_prompt)
                if error:
                    st.error(error)
                else:
                    progress_bar.progress(15, text="줄거리 완성. 파트별 생성 시작...")
                    meta_lines = outline.strip().split("\n")
                    meta_title = meta_desc = meta_tags = ""
                    for ml in meta_lines:
                        mls = ml.strip()
                        if mls.startswith("제목:"):
                            meta_title = mls
                        elif mls.startswith("설명글:"):
                            meta_desc = mls
                        elif mls.startswith("태그:"):
                            meta_tags = mls
                    all_parts = []
                    prev_ending = "없음 (첫 파트)"
                    success = True
                    for pi, pname in enumerate(PART_NAMES):
                        pct = 15 + int((pi + 1) * 17)
                        progress_bar.progress(pct, text=f"{pname} 생성 중... ({pi+1}/5)")
                        part_prompt = SENIOR_LONGFORM_PART.format(language=language, part_name=pname, outline=outline, previous_ending=prev_ending)
                        part_result, part_error = st.session_state.api.generate_long(part_prompt)
                        if part_error:
                            st.error(part_error)
                            success = False
                            break
                        all_parts.append(part_result)
                        ending_lines = [l for l in part_result.strip().split("\n")[-10:] if l.strip()]
                        prev_ending = "\n".join(ending_lines[-5:])
                    if success:
                        progress_bar.progress(100, text="완료!")
                        header = "\n".join([x for x in [meta_title, meta_desc, meta_tags] if x])
                        full = "\n".join(all_parts)
                        st.session_state.longform_result = header + "\n\n=대본 시작=\n" + full + "\n=대본 끝="
                        st.rerun()
        else:
            parsed = parse_longform(st.session_state.longform_result)
            st.markdown(f"### {parsed['title'] or t['title']}")
            st.text_area("대본 원본", parsed["script"], height=400)
            st.download_button("대본 다운로드", st.session_state.longform_result, file_name="script.txt")

            st.markdown("---")
            st.markdown("### 쇼츠")
            if st.session_state.shorts_result is None:
                if st.button("쇼츠 3편 생성 (스카이워크)", type="primary"):
                    with st.spinner("쇼츠 생성 중..."):
                        tl = parsed["title"] or t["title"]
                        sm = parsed["script"][:2000]
                        prompt = SHORTS_PROMPT.format(language=language, longform_title=tl, longform_summary=sm, longform_url="[URL]")
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
                else:
                    st.text_area("쇼츠 원본", st.session_state.shorts_result, height=300)

# ===== 탭2: 이미지 생성 (스카이워크) =====
with main_tab2:
    st.markdown("### 이미지 생성 (스카이워크 API)")
    st.caption("대본의 각 장면에 대해 스카이워크가 이미지를 생성합니다. 장면당 약 1~2분 소요됩니다.")

    if st.button("대본에서 장면 분리", key="split_scenes"):
        script = ""
        if st.session_state.longform_result:
            parsed = parse_longform(st.session_state.longform_result)
            script = parsed["script"]
        if not script:
            st.warning("대본이 없습니다. 탭1에서 먼저 대본을 생성하세요.")
        else:
            lines = [l.strip() for l in script.split("\n") if l.strip() and len(l.strip()) > 10]
            st.session_state.scenes = lines[:50]
            st.session_state.image_urls = {}
            st.session_state.image_paths = {}
            st.success(f"총 {len(st.session_state.scenes)}개 장면 분리 완료")

    if st.session_state.scenes:
        st.markdown(f"**총 {len(st.session_state.scenes)}개 장면**")

        aspect = st.selectbox("이미지 비율", ["9:16 (쇼츠)", "16:9 (롱폼)", "1:1"], key="img_aspect")
        ar_map = {"9:16 (쇼츠)": "9:16", "16:9 (롱폼)": "16:9", "1:1": "1:1"}
        ar = ar_map[aspect]

        scene_idx = st.number_input("장면 번호 (1부터)", min_value=1, max_value=len(st.session_state.scenes), value=1, key="scene_sel")
        st.text_area("선택된 장면", st.session_state.scenes[scene_idx - 1], height=80, key="scene_preview")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("이 장면 이미지 생성", key="gen_one_img"):
                idx = scene_idx - 1
                with st.spinner(f"장면 {scene_idx} 이미지 생성 중... (약 1~2분)"):
                    prompt = f"Cinematic illustration, {st.session_state.scenes[idx][:200]}, high quality, detailed"
                    file_url, err = st.session_state.api.generate_image(prompt, aspect_ratio=ar)
                    if err:
                        st.error(err)
                    elif file_url:
                        if st.session_state.image_urls is None:
                            st.session_state.image_urls = {}
                        st.session_state.image_urls[idx] = file_url
                        st.success(f"장면 {scene_idx} 이미지 생성 완료")
                        st.image(file_url, caption=f"장면 {scene_idx}")
        with col2:
            if st.button("전체 이미지 생성 (시간 오래 걸림)", key="gen_all_img"):
                total = len(st.session_state.scenes)
                progress = st.progress(0)
                for i, scene in enumerate(st.session_state.scenes):
                    if st.session_state.image_urls and i in st.session_state.image_urls:
                        continue
                    progress.progress((i+1)/total, text=f"이미지 {i+1}/{total} 생성 중...")
                    prompt = f"Cinematic illustration, {scene[:200]}, high quality, detailed"
                    file_url, err = st.session_state.api.generate_image(prompt, aspect_ratio=ar)
                    if file_url:
                        if st.session_state.image_urls is None:
                            st.session_state.image_urls = {}
                        st.session_state.image_urls[i] = file_url
                progress.progress(1.0, text="전체 이미지 생성 완료")

        if st.session_state.image_urls:
            st.markdown("---")
            st.markdown(f"### 생성된 이미지 ({len(st.session_state.image_urls)}개)")
            for idx in sorted(st.session_state.image_urls.keys()):
                st.image(st.session_state.image_urls[idx], caption=f"장면 {idx+1}", width=300)

# ===== 탭3: 영상변환 (Kie AI) =====
with main_tab3:
    st.markdown("### 이미지 → 영상 변환 (Kie AI)")
    st.caption("생성된 이미지를 움직이는 영상으로 변환합니다. 장면당 약 3~5분 소요됩니다.")

    if st.session_state.image_urls:
        duration = st.selectbox("영상 길이", ["5초", "10초"], key="vid_duration")
        dur_val = 5 if duration == "5초" else 10

        vid_idx = st.number_input("변환할 장면 번호", min_value=1, max_value=len(st.session_state.image_urls), value=1, key="vid_sel")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("이 장면 영상변환", key="conv_one_vid"):
                idx = vid_idx - 1
                if idx not in st.session_state.image_urls:
                    st.warning("이 장면의 이미지가 없습니다")
                else:
                    with st.spinner(f"장면 {vid_idx} 영상변환 중... (약 3~5분)"):
                        task_id, err = st.session_state.api.kie.image_to_video(st.session_state.image_urls[idx], duration=dur_val)
                        if err:
                            st.error(err)
                        else:
                            st.info(f"태스크 생성 완료 (ID: {task_id}). 완료 대기 중...")
                            video_url, err2 = st.session_state.api.kie.wait_for_task(task_id)
                            if err2:
                                st.error(err2)
                            else:
                                if st.session_state.video_urls is None:
                                    st.session_state.video_urls = {}
                                st.session_state.video_urls[idx] = video_url
                                st.success(f"장면 {vid_idx} 영상변환 완료")
                                st.video(video_url)
        with col2:
            if st.button("전체 영상변환", key="conv_all_vid"):
                total = len(st.session_state.image_urls)
                progress = st.progress(0)
                for ci, idx in enumerate(sorted(st.session_state.image_urls.keys())):
                    if st.session_state.video_urls and idx in st.session_state.video_urls:
                        continue
                    progress.progress((ci+1)/total, text=f"영상 {ci+1}/{total} 변환 중...")
                    task_id, err = st.session_state.api.kie.image_to_video(st.session_state.image_urls[idx], duration=dur_val)
                    if err:
                        continue
                    video_url, err2 = st.session_state.api.kie.wait_for_task(task_id)
                    if video_url:
                        if st.session_state.video_urls is None:
                            st.session_state.video_urls = {}
                        st.session_state.video_urls[idx] = video_url
                progress.progress(1.0, text="전체 영상변환 완료")

        if st.session_state.video_urls:
            st.markdown(f"### 변환된 영상 ({len(st.session_state.video_urls)}개)")
            for idx in sorted(st.session_state.video_urls.keys()):
                st.video(st.session_state.video_urls[idx])
    else:
        st.info("먼저 탭2에서 이미지를 생성하세요.")

# ===== 탭4: 음성 (인월드 TTS) =====
with main_tab4:
    st.markdown("### 음성 생성 (인월드 TTS)")
    st.caption("각 장면의 대사를 인월드 TTS로 음성 변환합니다.")

    voice_id = st.text_input("음성 ID (기본: Sarah)", value="Sarah", key="voice_id_input")

    if st.button("음성 목록 조회", key="list_voices"):
        with st.spinner("조회 중..."):
            voices, err = st.session_state.api.inworld.list_voices()
            if err:
                st.error(err)
            else:
                for v in voices:
                    st.markdown(f"**{v.get('voiceId','?')}** | {v.get('langCode','?')} | {v.get('description','')[:60]}")

    if st.session_state.scenes:
        if st.button("전체 음성 생성", type="primary", key="gen_all_tts"):
            total = len(st.session_state.scenes)
            progress = st.progress(0)
            audio_data = {}
            for i, scene in enumerate(st.session_state.scenes):
                progress.progress((i+1)/total, text=f"음성 {i+1}/{total} 생성 중...")
                audio_bytes, ts, err = st.session_state.api.inworld.synthesize(scene, voice_id=voice_id)
                if err:
                    st.warning(f"장면 {i+1} 실패: {err}")
                    continue
                audio_data[i] = audio_bytes
            st.session_state.audio_data = audio_data
            progress.progress(1.0, text=f"음성 생성 완료 ({len(audio_data)}개)")

        if st.session_state.audio_data:
            st.markdown(f"### 생성된 음성 ({len(st.session_state.audio_data)}개)")
            for idx in sorted(st.session_state.audio_data.keys()):
                st.audio(st.session_state.audio_data[idx], format="audio/mp3")
                st.caption(f"장면 {idx+1}")
    else:
        st.info("먼저 탭2에서 장면을 분리하세요.")

# ===== 탭5: 최종합성 =====
with main_tab5:
    st.markdown("### 최종 영상 합성")
    st.caption("영상 + 음성 + 자막을 합쳐서 최종 MP4를 생성합니다.")
    st.warning("이 기능은 로컬 PC에서 FFmpeg가 설치되어 있어야 합니다. Streamlit Cloud에서는 제한적으로 동작합니다.")

    ready_count = 0
    if st.session_state.video_urls and st.session_state.audio_data:
        for idx in st.session_state.video_urls:
            if idx in st.session_state.audio_data:
                ready_count += 1

    st.markdown(f"**영상+음성 모두 준비된 장면: {ready_count}개**")

    if ready_count > 0:
        font_size = st.slider("자막 크기", 16, 48, 28, key="sub_size")
        sub_pos = st.selectbox("자막 위치", ["하단", "중앙", "상단"], key="sub_pos")
        overlay_text = st.text_input("상단 텍스트 (선택)", key="overlay_txt")

        if st.button("최종 합성 시작", type="primary", key="final_merge"):
            st.info("Streamlit Cloud에서는 FFmpeg 사용이 제한됩니다. 로컬 환경에서 실행하시거나, 개별 영상과 음성을 다운로드해서 편집 소프트웨어로 합성하세요.")
            st.markdown("### 다운로드 링크")
            for idx in sorted(st.session_state.video_urls.keys()):
                if idx in st.session_state.audio_data:
                    st.markdown(f"**장면 {idx+1}**")
                    st.video(st.session_state.video_urls[idx])
                    st.audio(st.session_state.audio_data[idx], format="audio/mp3")
                    st.text(f"대사: {st.session_state.scenes[idx][:80]}")
                    st.markdown("---")
    else:
        st.info("영상(탭3)과 음성(탭4)을 먼저 생성하세요.")

st.markdown('---')
st.markdown('<div style="text-align:center;color:#555;font-size:.8rem;">시니어 콘텐츠 팩토리 올인원 | 스카이워크 + Kie AI + 인월드 TTS</div>', unsafe_allow_html=True)
