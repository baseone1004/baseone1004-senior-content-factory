import tempfile
import zipfile
import os
import shutil
import subprocess
import streamlit as st

# ─── 페이지 설정 ───
st.set_page_config(page_title="쇼츠 제작 도구", layout="wide")
st.title("쇼츠 제작 도구")

# ─── 상수 ───
MAX_VIDEO_COUNT = 500

# ─── 임시 디렉토리 초기화 ───
if "video_save_dir" not in st.session_state:
    st.session_state["video_save_dir"] = tempfile.mkdtemp()
if "video_list" not in st.session_state:
    st.session_state["video_list"] = []
if "audio_save_dir" not in st.session_state:
    st.session_state["audio_save_dir"] = tempfile.mkdtemp()
if "audio_list" not in st.session_state:
    st.session_state["audio_list"] = []


# ============================================================
#  탭1: 대본 작성
# ============================================================
def render_script_tab():
    st.subheader("대본 작성")

    if "script_text" not in st.session_state:
        st.session_state["script_text"] = ""

    script_input = st.text_area(
        "대본을 입력하세요",
        value=st.session_state["script_text"],
        height=400,
        key="script_input_area",
        placeholder="여기에 쇼츠 대본을 붙여넣거나 작성하세요..."
    )

    if script_input != st.session_state["script_text"]:
        st.session_state["script_text"] = script_input

    if st.session_state["script_text"].strip():
        sentences = [s.strip() for s in st.session_state["script_text"].replace("?", "?.").replace("!", "!.").split(".") if s.strip()]
        st.info(f"문장 수: {len(sentences)}개")

        with st.expander("문장 미리보기"):
            for i, s in enumerate(sentences):
                clean = s.rstrip(".").strip()
                if clean:
                    st.text(f"{i+1:03d}. {clean}")


# ============================================================
#  탭2: 자막 편집
# ============================================================
def render_subtitle_tab():
    st.subheader("자막 편집")

    if not st.session_state.get("script_text", "").strip():
        st.warning("대본 탭에서 먼저 대본을 입력하세요.")
        return

    # 대본에서 자막 라인 추출
    raw = st.session_state["script_text"]
    lines = [s.strip() for s in raw.replace("?", "?.").replace("!", "!.").split(".") if s.strip()]
    lines = [l.rstrip(".").strip() for l in lines if l.rstrip(".").strip()]

    if not st.session_state.get("edited_sub_lines"):
        st.session_state["edited_sub_lines"] = list(lines)

    max_chars = st.slider("자막 최대 글자 수", min_value=10, max_value=60, value=25, key="max_chars_slider")

    # ─── 긴 자막 자동 분할 ───
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
                # 띄어쓰기가 있는 경우
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

                    # 청크가 여전히 긴 경우 강제 분할
                    final_chunks = []
                    for chunk in chunks:
                        if len(chunk) <= max_chars:
                            final_chunks.append(chunk)
                        else:
                            # 강제 분할
                            pos = 0
                            while pos < len(chunk):
                                end = min(pos + max_chars, len(chunk))
                                if end < len(chunk):
                                    # 자연스러운 끊김 찾기
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
                        split_count -= 1  # 원본 1개 기준 보정
                else:
                    # 띄어쓰기 없는 긴 문장 강제 분할
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
        st.warning("SRT 재생성 시 싱크가 맞도록 확인하세요.")
        st.rerun()

    # ─── 자막 편집 영역 ───
    st.write(f"자막 라인 수: {len(st.session_state['edited_sub_lines'])}개")

    edited_lines = []
    for i, line in enumerate(st.session_state["edited_sub_lines"]):
        edited = st.text_input(
            f"{i+1:03d}",
            value=line,
            key=f"sub_line_{i}"
        )
        edited_lines.append(edited)

    if st.button("자막 변경 저장", key="btn_save_subs"):
        st.session_state["edited_sub_lines"] = edited_lines
        st.success("자막 저장 완료!")

    # ─── SRT 다운로드 ───
    if st.button("SRT 파일 생성", key="btn_gen_srt"):
        srt_content = ""
        duration_per_line = 3.0  # 초
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
#  탭3: 이미지 영상 업로드 (ZIP 방식, 최대 500개)
# ============================================================
def render_video_upload_tab():
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

    # ─── 등록된 영상 목록 ───
    if st.session_state["video_list"]:
        total_size_mb = sum(v["size"] for v in st.session_state["video_list"]) / (1024 * 1024)
        st.write(f"등록된 영상: {len(st.session_state['video_list'])}개 / 총 {total_size_mb:.1f}MB")

        with st.expander("영상 목록 보기"):
            for i, v in enumerate(st.session_state["video_list"]):
                size_kb = v["size"] / 1024
                st.text(f"{i+1:03d}. {v['name']} ({size_kb:.0f}KB)")

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
#  탭4: 음성 파일 업로드 (개별 또는 ZIP)
# ============================================================
def render_audio_upload_tab():
    st.subheader("TTS 음성 파일 업로드")
    st.caption("WAV, MP3 음성 파일을 개별 또는 ZIP으로 업로드하세요.")

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

    # ─── 등록된 음성 목록 ───
    if st.session_state["audio_list"]:
        total_size_mb = sum(a["size"] for a in st.session_state["audio_list"]) / (1024 * 1024)
        st.write(f"등록된 음성: {len(st.session_state['audio_list'])}개 / 총 {total_size_mb:.1f}MB")

        with st.expander("음성 목록 보기"):
            for i, a in enumerate(st.session_state["audio_list"]):
                size_kb = a["size"] / 1024
                st.text(f"{i+1:03d}. {a['name']} ({size_kb:.0f}KB)")

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
#  탭5: 영상 + 음성 최종 병합
# ============================================================
def render_merge_tab():
    st.subheader("영상 + 음성 최종 병합")

    v_count = len(st.session_state.get("video_list", []))
    a_count = len(st.session_state.get("audio_list", []))

    st.info(f"등록 영상: {v_count}개 / 등록 음성: {a_count}개")

    if v_count == 0:
        st.warning("영상을 먼저 업로드하세요.")
        return
    if a_count == 0:
        st.warning("음성 파일을 먼저 업로드하세요.")
        return

    merge_mode = st.radio(
        "병합 방식",
        [
            "음성 1개 + 영상 전체 이어붙이기 (음성 길이에 맞춤)",
            "음성 N개 + 영상 N개 일대일 매칭"
        ],
        key="merge_mode"
    )

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
                    return

            with st.spinner("음성 합치는 중..."):
                final_path = os.path.join(output_dir, "final_output.mp4")
                cmd_merge = [
                    "ffmpeg", "-y",
                    "-i", concat_video_path,
                    "-i", audio_path,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    final_path
                ]
                result = subprocess.run(cmd_merge, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"음성 병합 실패:\n{result.stderr[:500]}")
                    return

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
                concat_list_path = os.path.join(output_dir, "final_concat.txt")
                with open(concat_list_path, "w") as cl:
                    for mp in merged_paths:
                        safe_path = mp.replace("'", "'\\''")
                        cl.write(f"file '{safe_path}'\n")

                final_path = os.path.join(output_dir, "final_matched.mp4")
                cmd_final = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    final_path
                ]
                result = subprocess.run(cmd_final, capture_output=True, text=True)

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


# ============================================================
#  메인: 탭 구성 및 렌더링
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "대본 작성",
    "자막 편집",
    "이미지 영상",
    "음성 업로드",
    "최종 병합"
])

with tab1:
    render_script_tab()

with tab2:
    render_subtitle_tab()

with tab3:
    render_video_upload_tab()

with tab4:
    render_audio_upload_tab()

with tab5:
    render_merge_tab()
