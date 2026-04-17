import tempfile
import zipfile
import os
import shutil
import subprocess
import streamlit as st
import re
import io
import base64

# ─── 페이지 설정 ───
st.set_page_config(page_title="시니어 콘텐츠 공장 v5.0", layout="wide")
st.title("시니어 콘텐츠 공장 v5.0")
st.caption("대본 → 영상업로드 → 음성업로드 → 자막편집 → 최종합치기")

# ─── 상수 ───
MAX_VIDEO_COUNT = 500

# ─── 세션 초기화 ───
if "video_save_dir" not in st.session_state:
    st.session_state["video_save_dir"] = tempfile.mkdtemp()
if "video_list" not in st.session_state:
    st.session_state["video_list"] = []
if "audio_save_dir" not in st.session_state:
    st.session_state["audio_save_dir"] = tempfile.mkdtemp()
if "audio_list" not in st.session_state:
    st.session_state["audio_list"] = []
if "script_text" not in st.session_state:
    st.session_state["script_text"] = ""
if "edited_sub_lines" not in st.session_state:
    st.session_state["edited_sub_lines"] = []


# ============================================================
#  사이드바
# ============================================================
with st.sidebar:
    st.header("설정")
    st.subheader("영상 등록 현황")
    v_cnt = len(st.session_state["video_list"])
    a_cnt = len(st.session_state["audio_list"])
    st.write(f"영상: {v_cnt}개 / {MAX_VIDEO_COUNT}개")
    st.write(f"음성: {a_cnt}개")

    if st.session_state.get("script_text", "").strip():
        raw = st.session_state["script_text"]
        sents = [s.strip() for s in raw.replace("?", "?.").replace("!", "!.").split(".") if s.strip()]
        sents = [s.rstrip(".").strip() for s in sents if s.rstrip(".").strip()]
        st.write(f"대본 문장 수: {len(sents)}개")

    sub_cnt = len(st.session_state.get("edited_sub_lines", []))
    if sub_cnt > 0:
        st.write(f"자막 라인 수: {sub_cnt}개")


# ============================================================
#  탭 구성
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. 대본 입력",
    "2. 영상 업로드",
    "3. 음성 업로드",
    "4. 자막 편집",
    "5. 최종 합치기"
])


# ============================================================
#  탭1: 대본 입력
# ============================================================
with tab1:
    st.subheader("대본 입력")
    st.caption("쇼츠 대본을 붙여넣거나 직접 작성하세요.")

    script_input = st.text_area(
        "대본",
        value=st.session_state["script_text"],
        height=500,
        key="script_input_area",
        placeholder="여기에 대본을 붙여넣으세요..."
    )

    if script_input != st.session_state["script_text"]:
        st.session_state["script_text"] = script_input

    if st.session_state["script_text"].strip():
        sentences = [s.strip() for s in st.session_state["script_text"].replace("?", "?.").replace("!", "!.").split(".") if s.strip()]
        sentences = [s.rstrip(".").strip() for s in sentences if s.rstrip(".").strip()]
        st.info(f"총 {len(sentences)}개 문장 감지됨")

        with st.expander("문장 미리보기", expanded=False):
            for i, s in enumerate(sentences):
                st.text(f"{i+1:03d}. {s}")

        # 감정태그 제거 버전 생성
        if st.button("감정태그 제거한 순수 대본 보기", key="btn_clean_script"):
            clean_lines = []
            for s in sentences:
                clean = re.sub(r'\[.*?\]\s*', '', s).strip()
                if clean:
                    clean_lines.append(clean)
            st.text_area("순수 대본 (감정태그 제거)", value="\n".join(clean_lines), height=300)


# ============================================================
#  탭2: 영상 업로드 (ZIP 방식, 최대 500개)
# ============================================================
with tab2:
    st.subheader("이미지 영상 업로드 (ZIP)")
    st.caption(f"MP4 영상을 ZIP으로 묶어서 업로드하세요. 최대 {MAX_VIDEO_COUNT}개까지 가능합니다.")

    current_count = len(st.session_state["video_list"])
    remain = MAX_VIDEO_COUNT - current_count
    st.info(f"현재 {current_count}개 등록 / 남은 슬롯 {remain}개")

    zip_file = st.file_uploader(
        "ZIP 파일 선택",
        type=["zip"],
        key="video_zip_uploader"
    )

    if zip_file is not None and st.button("ZIP 압축 해제 및 등록", key="btn_unzip_video"):
        if remain <= 0:
            st.error(f"이미 {MAX_VIDEO_COUNT}개가 등록되어 있습니다. 초기화 후 다시 업로드하세요.")
        else:
            with st.spinner("ZIP 압축 해제 중..."):
                tmp_zip_path = os.path.join(st.session_state["video_save_dir"], "temp_upload.zip")
                with open(tmp_zip_path, "wb") as f:
                    f.write(zip_file.getbuffer())

                added = 0
                skipped = 0
                existing_names = set(v["name"] for v in st.session_state["video_list"])

                try:
                    with zipfile.ZipFile(tmp_zip_path, "r") as zf:
                        entries = sorted([
                            e for e in zf.namelist()
                            if e.lower().endswith(".mp4")
                            and not e.startswith("__MACOSX")
                            and not os.path.basename(e).startswith(".")
                        ])

                        for entry in entries:
                            if added + current_count >= MAX_VIDEO_COUNT:
                                st.warning(f"{MAX_VIDEO_COUNT}개 한도 도달. 나머지는 건너뜁니다.")
                                break

                            fname = os.path.basename(entry)
                            if not fname:
                                continue
                            if fname in existing_names:
                                skipped += 1
                                continue

                            save_path = os.path.join(
                                st.session_state["video_save_dir"],
                                f"{current_count + added:04d}_{fname}"
                            )
                            with zf.open(entry) as src, open(save_path, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                            fsize = os.path.getsize(save_path)
                            st.session_state["video_list"].append({
                                "name": fname,
                                "path": save_path,
                                "size": fsize
                            })
                            existing_names.add(fname)
                            added += 1

                except zipfile.BadZipFile:
                    st.error("ZIP 파일이 손상되었습니다. 다시 압축해서 올려주세요.")
                finally:
                    if os.path.exists(tmp_zip_path):
                        os.remove(tmp_zip_path)

                if added > 0:
                    st.success(f"{added}개 영상 등록 완료! (중복 건너뜀: {skipped}개)")
                elif skipped > 0:
                    st.warning(f"모두 중복이라 새로 등록된 영상이 없습니다. ({skipped}개 건너뜀)")
                st.rerun()

    # 등록된 영상 목록
    if st.session_state["video_list"]:
        total_size_mb = sum(v["size"] for v in st.session_state["video_list"]) / (1024 * 1024)
        st.write(f"등록된 영상: {len(st.session_state['video_list'])}개 / 총 {total_size_mb:.1f}MB")

        with st.expander("영상 목록 보기"):
            for i, v in enumerate(st.session_state["video_list"]):
                size_kb = v["size"] / 1024
                st.text(f"{i+1:03d}. {v['name']} ({size_kb:.0f}KB)")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("영상 전체 초기화", key="btn_reset_videos"):
                for v in st.session_state["video_list"]:
                    if os.path.exists(v["path"]):
                        try:
                            os.remove(v["path"])
                        except:
                            pass
                st.session_state["video_list"] = []
                st.success("영상 목록 초기화 완료")
                st.rerun()


# ============================================================
#  탭3: 음성 파일 업로드 (개별 또는 ZIP)
# ============================================================
with tab3:
    st.subheader("TTS 음성 파일 업로드")
    st.caption("구글 AI 스튜디오 등에서 생성한 WAV, MP3 음성 파일을 업로드하세요.")

    upload_mode = st.radio(
        "업로드 방식",
        ["개별 파일 업로드", "ZIP 일괄 업로드"],
        horizontal=True,
        key="audio_upload_mode"
    )

    if upload_mode == "개별 파일 업로드":
        audio_files = st.file_uploader(
            "음성 파일 선택 (WAV, MP3)",
            type=["wav", "mp3"],
            accept_multiple_files=True,
            key="audio_individual_uploader"
        )

        if audio_files and st.button("음성 등록", key="btn_register_audio"):
            existing_names = set(a["name"] for a in st.session_state["audio_list"])
            added = 0
            for af in audio_files:
                if af.name in existing_names:
                    continue
                save_path = os.path.join(
                    st.session_state["audio_save_dir"],
                    f"{len(st.session_state['audio_list']):04d}_{af.name}"
                )
                with open(save_path, "wb") as f:
                    f.write(af.getbuffer())
                fsize = os.path.getsize(save_path)
                st.session_state["audio_list"].append({
                    "name": af.name,
                    "path": save_path,
                    "size": fsize
                })
                existing_names.add(af.name)
                added += 1
            if added > 0:
                st.success(f"{added}개 음성 파일 등록 완료!")
                st.rerun()

    else:
        audio_zip = st.file_uploader(
            "음성 ZIP 파일 선택",
            type=["zip"],
            key="audio_zip_uploader"
        )

        if audio_zip is not None and st.button("음성 ZIP 압축 해제", key="btn_unzip_audio"):
            with st.spinner("음성 ZIP 압축 해제 중..."):
                tmp_zip_path = os.path.join(st.session_state["audio_save_dir"], "temp_audio.zip")
                with open(tmp_zip_path, "wb") as f:
                    f.write(audio_zip.getbuffer())

                added = 0
                existing_names = set(a["name"] for a in st.session_state["audio_list"])

                try:
                    with zipfile.ZipFile(tmp_zip_path, "r") as zf:
                        entries = sorted([
                            e for e in zf.namelist()
                            if (e.lower().endswith(".wav") or e.lower().endswith(".mp3"))
                            and not e.startswith("__MACOSX")
                            and not os.path.basename(e).startswith(".")
                        ])

                        for entry in entries:
                            fname = os.path.basename(entry)
                            if not fname or fname in existing_names:
                                continue

                            save_path = os.path.join(
                                st.session_state["audio_save_dir"],
                                f"{len(st.session_state['audio_list']):04d}_{fname}"
                            )
                            with zf.open(entry) as src, open(save_path, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                            fsize = os.path.getsize(save_path)
                            st.session_state["audio_list"].append({
                                "name": fname,
                                "path": save_path,
                                "size": fsize
                            })
                            existing_names.add(fname)
                            added += 1

                except zipfile.BadZipFile:
                    st.error("ZIP 파일이 손상되었습니다.")
                finally:
                    if os.path.exists(tmp_zip_path):
                        os.remove(tmp_zip_path)

                if added > 0:
                    st.success(f"{added}개 음성 파일 등록 완료!")
                    st.rerun()

    # 등록된 음성 목록
    if st.session_state["audio_list"]:
        total_size_mb = sum(a["size"] for a in st.session_state["audio_list"]) / (1024 * 1024)
        st.write(f"등록된 음성: {len(st.session_state['audio_list'])}개 / 총 {total_size_mb:.1f}MB")

        with st.expander("음성 목록 보기"):
            for i, a in enumerate(st.session_state["audio_list"]):
                size_kb = a["size"] / 1024
                st.text(f"{i+1:03d}. {a['name']} ({size_kb:.0f}KB)")

        # 음성 미리듣기
        st.write("음성 미리듣기:")
        preview_idx = st.number_input(
            "번호 선택",
            min_value=1,
            max_value=len(st.session_state["audio_list"]),
            value=1,
            key="audio_preview_idx"
        )
        audio_item = st.session_state["audio_list"][preview_idx - 1]
        if os.path.exists(audio_item["path"]):
            with open(audio_item["path"], "rb") as f:
                audio_bytes = f.read()
            fmt = "audio/wav" if audio_item["name"].lower().endswith(".wav") else "audio/mp3"
            st.audio(audio_bytes, format=fmt)
            st.caption(audio_item["name"])

        if st.button("음성 전체 초기화", key="btn_reset_audio"):
            for a in st.session_state["audio_list"]:
                if os.path.exists(a["path"]):
                    try:
                        os.remove(a["path"])
                    except:
                        pass
            st.session_state["audio_list"] = []
            st.success("음성 목록 초기화 완료")
            st.rerun()


# ============================================================
#  탭4: 자막 편집
# ============================================================
with tab4:
    st.subheader("자막 편집")

    if not st.session_state.get("script_text", "").strip():
        st.warning("대본 입력 탭에서 먼저 대본을 입력하세요.")
    else:
        # 대본에서 자막 라인 추출
        raw = st.session_state["script_text"]
        lines = [s.strip() for s in raw.replace("?", "?.").replace("!", "!.").split(".") if s.strip()]
        lines = [l.rstrip(".").strip() for l in lines if l.rstrip(".").strip()]

        # 감정태그 제거
        clean_lines = []
        for l in lines:
            clean = re.sub(r'\[.*?\]\s*', '', l).strip()
            if clean:
                clean_lines.append(clean)

        if not st.session_state.get("edited_sub_lines"):
            st.session_state["edited_sub_lines"] = list(clean_lines)

        # 대본 다시 불러오기
        if st.button("대본에서 자막 다시 불러오기", key="btn_reload_subs"):
            st.session_state["edited_sub_lines"] = list(clean_lines)
            st.success(f"{len(clean_lines)}개 자막 라인 불러옴 (감정태그 자동 제거)")
            st.rerun()

        max_chars = st.slider("자막 최대 글자 수", min_value=10, max_value=60, value=25, key="max_chars_slider")

        # 긴 자막 자동 분할
        if st.button("긴 자막 자동 분할", key="btn_auto_split"):
            original_lines = list(st.session_state["edited_sub_lines"])
            new_lines = []
            split_count = 0

            for line in original_lines:
                line = line.strip()
                if not line:
                    continue

                if len(line) <= max_chars:
                    new_lines.append(line)
                else:
                    words = line.split(" ")
                    if len(words) > 1:
                        chunks = []
                        current = ""
                        for w in words:
                            test = (current + " " + w).strip() if current else w
                            if len(test) <= max_chars:
                                current = test
                            else:
                                if current:
                                    chunks.append(current)
                                current = w
                        if current:
                            chunks.append(current)

                        final_chunks = []
                        for chunk in chunks:
                            if len(chunk) <= max_chars:
                                final_chunks.append(chunk)
                            else:
                                pos = 0
                                while pos < len(chunk):
                                    end = min(pos + max_chars, len(chunk))
                                    if end < len(chunk):
                                        best = -1
                                        for punct in [".", "?", ",", "요", "다", "는", "을", "를", "이", "가", "에", "서"]:
                                            idx = chunk.rfind(punct, pos, end)
                                            if idx > best:
                                                best = idx
                                        if best > pos:
                                            end = best + 1
                                    final_chunks.append(chunk[pos:end].strip())
                                    pos = end

                        for fc in final_chunks:
                            if fc:
                                new_lines.append(fc)
                                split_count += 1
                        if split_count > 0:
                            split_count -= 1
                    else:
                        pos = 0
                        while pos < len(line):
                            end = min(pos + max_chars, len(line))
                            if end < len(line):
                                best = -1
                                for punct in [".", "?", ",", "요", "다", "는", "을", "를", "이", "가", "에", "서"]:
                                    idx = line.rfind(punct, pos, end)
                                    if idx > best:
                                        best = idx
                                if best > pos:
                                    end = best + 1
                            segment = line[pos:end].strip()
                            if segment:
                                new_lines.append(segment)
                                split_count += 1
                            pos = end
                        if split_count > 0:
                            split_count -= 1

            st.session_state["edited_sub_lines"] = new_lines
            st.success(f"분할 완료! {len(original_lines)}줄 → {len(new_lines)}줄 (분할 {split_count}회)")
            st.rerun()

        # 자막 편집 영역
        st.write(f"자막 라인 수: {len(st.session_state['edited_sub_lines'])}개")

        edited_lines = []
        for i, line in enumerate(st.session_state["edited_sub_lines"]):
            edited = st.text_input(
                f"{i+1:03d}",
                value=line,
                key=f"sub_line_{i}"
            )
            edited_lines.append(edited)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("자막 변경 저장", key="btn_save_subs"):
                st.session_state["edited_sub_lines"] = edited_lines
                st.success("자막 저장 완료!")

        with col_s2:
            # SRT 다운로드
            if st.button("SRT 파일 생성", key="btn_gen_srt"):
                srt_content = ""
                duration_per_line = 3.0
                for i, line in enumerate(st.session_state["edited_sub_lines"]):
                    start_sec = i * duration_per_line
                    end_sec = start_sec + duration_per_line

                    start_h = int(start_sec // 3600)
                    start_m = int((start_sec % 3600) // 60)
                    start_s = int(start_sec % 60)
                    start_ms = int((start_sec % 1) * 1000)

                    end_h = int(end_sec // 3600)
                    end_m = int((end_sec % 3600) // 60)
                    end_s = int(end_sec % 60)
                    end_ms = int((end_sec % 1) * 1000)

                    srt_content += f"{i+1}\n"
                    srt_content += f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> "
                    srt_content += f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}\n"
                    srt_content += f"{line}\n\n"

                st.download_button(
                    "SRT 다운로드",
                    srt_content.encode("utf-8"),
                    file_name="subtitles.srt",
                    mime="text/plain"
                )


# ============================================================
#  탭5: 최종 합치기
# ============================================================
with tab5:
    st.subheader("영상 + 음성 최종 병합")

    v_count = len(st.session_state.get("video_list", []))
    a_count = len(st.session_state.get("audio_list", []))

    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.metric("등록 영상", f"{v_count}개")
    with col_info2:
        st.metric("등록 음성", f"{a_count}개")

    if v_count == 0:
        st.warning("영상 업로드 탭에서 영상을 먼저 등록하세요.")
    elif a_count == 0:
        st.warning("음성 업로드 탭에서 음성을 먼저 등록하세요.")
    else:
        merge_mode = st.radio(
            "병합 방식",
            [
                "음성 1개 + 영상 전체 이어붙이기 (음성 길이에 맞춤)",
                "음성 N개 + 영상 N개 일대일 매칭 후 이어붙이기"
            ],
            key="merge_mode"
        )

        # 자막 입히기 옵션
        use_subtitle = st.checkbox("자막 SRT 입히기", value=False, key="chk_subtitle")
        if use_subtitle:
            srt_upload = st.file_uploader("SRT 파일 업로드", type=["srt"], key="srt_uploader")
        else:
            srt_upload = None

        if st.button("최종 병합 시작", key="btn_final_merge"):
            output_dir = tempfile.mkdtemp()

            if "음성 1개" in merge_mode:
                audio_path = st.session_state["audio_list"][0]["path"]

                with st.spinner("영상 이어붙이기 중..."):
                    concat_list_path = os.path.join(output_dir, "concat.txt")
                    with open(concat_list_path, "w") as cl:
                        for v in st.session_state["video_list"]:
                            safe_path = v["path"].replace("'", "'\\''")
                            cl.write(f"file '{safe_path}'\n")

                    concat_video_path = os.path.join(output_dir, "concat_video.mp4")
                    cmd_concat = [
                        "ffmpeg", "-y",
                        "-f", "concat", "-safe", "0",
                        "-i", concat_list_path,
                        "-c", "copy",
                        concat_video_path
                    ]
                    result = subprocess.run(cmd_concat, capture_output=True, text=True)
                    if result.returncode != 0:
                        st.error(f"영상 이어붙이기 실패:\n{result.stderr[:500]}")
                        st.stop()

                with st.spinner("음성 합치는 중..."):
                    merged_path = os.path.join(output_dir, "merged_av.mp4")
                    cmd_merge = [
                        "ffmpeg", "-y",
                        "-i", concat_video_path,
                        "-i", audio_path,
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        merged_path
                    ]
                    result = subprocess.run(cmd_merge, capture_output=True, text=True)
                    if result.returncode != 0:
                        st.error(f"음성 병합 실패:\n{result.stderr[:500]}")
                        st.stop()

                final_path = merged_path

                # 자막 입히기
                if use_subtitle and srt_upload is not None:
                    with st.spinner("자막 입히는 중..."):
                        srt_path = os.path.join(output_dir, "subtitles.srt")
                        with open(srt_path, "wb") as f:
                            f.write(srt_upload.getbuffer())

                        subtitled_path = os.path.join(output_dir, "final_subtitled.mp4")
                        cmd_sub = [
                            "ffmpeg", "-y",
                            "-i", merged_path,
                            "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=30'",
                            "-c:a", "copy",
                            subtitled_path
                        ]
                        result = subprocess.run(cmd_sub, capture_output=True, text=True)
                        if result.returncode == 0 and os.path.exists(subtitled_path):
                            final_path = subtitled_path
                            st.success("자막 입히기 완료!")
                        else:
                            st.warning(f"자막 입히기 실패. 자막 없는 버전으로 출력합니다.\n{result.stderr[:300]}")

                if os.path.exists(final_path):
                    st.success("병합 완료!")
                    with open(final_path, "rb") as f:
                        final_bytes = f.read()
                    st.video(final_bytes)
                    st.download_button(
                        "최종 영상 다운로드",
                        final_bytes,
                        file_name="final_output.mp4",
                        mime="video/mp4"
                    )

            else:
                # 모드2: N대N 매칭
                match_count = min(v_count, a_count)
                st.write(f"{match_count}개 매칭하여 병합합니다.")

                progress = st.progress(0)
                merged_paths = []

                for i in range(match_count):
                    v_path = st.session_state["video_list"][i]["path"]
                    a_path = st.session_state["audio_list"][i]["path"]
                    out_path = os.path.join(output_dir, f"merged_{i:04d}.mp4")

                    cmd = [
                        "ffmpeg", "-y",
                        "-i", v_path,
                        "-i", a_path,
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        out_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0 and os.path.exists(out_path):
                        merged_paths.append(out_path)
                    progress.progress((i + 1) / match_count)

                if merged_paths:
                    with st.spinner("매칭 영상 이어붙이기 중..."):
                        concat_list_path = os.path.join(output_dir, "final_concat.txt")
                        with open(concat_list_path, "w") as cl:
                            for mp in merged_paths:
                                safe_path = mp.replace("'", "'\\''")
                                cl.write(f"file '{safe_path}'\n")

                        concat_matched_path = os.path.join(output_dir, "concat_matched.mp4")
                        cmd_final = [
                            "ffmpeg", "-y",
                            "-f", "concat", "-safe", "0",
                            "-i", concat_list_path,
                            "-c", "copy",
                            concat_matched_path
                        ]
                        result = subprocess.run(cmd_final, capture_output=True, text=True)

                    final_path = concat_matched_path

                    # 자막 입히기
                    if use_subtitle and srt_upload is not None:
                        with st.spinner("자막 입히는 중..."):
                            srt_path = os.path.join(output_dir, "subtitles.srt")
                            with open(srt_path, "wb") as f:
                                f.write(srt_upload.getbuffer())

                            subtitled_path = os.path.join(output_dir, "final_subtitled.mp4")
                            cmd_sub = [
                                "ffmpeg", "-y",
                                "-i", concat_matched_path,
                                "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=30'",
                                "-c:a", "copy",
                                subtitled_path
                            ]
                            result = subprocess.run(cmd_sub, capture_output=True, text=True)
                            if result.returncode == 0 and os.path.exists(subtitled_path):
                                final_path = subtitled_path
                                st.success("자막 입히기 완료!")
                            else:
                                st.warning(f"자막 입히기 실패. 자막 없는 버전으로 출력합니다.\n{result.stderr[:300]}")

                    if result.returncode == 0 and os.path.exists(final_path):
                        st.success(f"{len(merged_paths)}개 영상+음성 매칭 병합 완료!")
                        with open(final_path, "rb") as f:
                            final_bytes = f.read()
                        st.video(final_bytes)
                        st.download_button(
                            "최종 영상 다운로드",
                            final_bytes,
                            file_name="final_matched.mp4",
                            mime="video/mp4"
                        )
                    else:
                        st.error("최종 이어붙이기 실패")
                else:
                    st.error("매칭 병합된 영상이 없습니다.")
