# Bilibili Transcript Implementation Plan

**Goal:** Add Bilibili support to the transcript extractor while keeping YouTube support intact. Bilibili should try subtitles first, then fall back to downloading temporary audio and running local `faster-whisper` ASR.

**Architecture:** Create `scripts/extract_video_transcript.py` as the platform entry point. It delegates YouTube to the existing Supadata extractor, tries Bilibili subtitles through `yt-dlp`, and uses temporary audio plus local `faster-whisper` when subtitles are missing. Downloaded temp audio is always deleted.

**Tech Stack:** Python stdlib, `yt-dlp` CLI, optional `faster-whisper`, stdlib `unittest`. `ffmpeg` is only needed when `yt-dlp` reports it for a specific source.

---

### Task 1: Test Platform Detection and Cleanup

**Files:**
- Create: `tests/test_extract_video_transcript.py`
- Create: `scripts/extract_video_transcript.py`

- [ ] Write failing tests for platform detection, subtitle parsing, temp audio cleanup after success, and temp audio cleanup after ASR failure.
- [ ] Run `python -m unittest tests.test_extract_video_transcript -v` and verify tests fail because `scripts.extract_video_transcript` does not exist.
- [ ] Implement minimal helpers and dependency-injected extraction functions in `scripts/extract_video_transcript.py`.
- [ ] Re-run tests and verify they pass.

### Task 2: Add CLI and Documentation

**Files:**
- Modify: `scripts/extract_video_transcript.py`
- Modify: `SKILL.md`
- Modify: `README.md`

- [ ] Add CLI options: `--output`, `--format`, `--platform`, `--language`, and `--model-size`.
- [ ] Document YouTube/Supadata, Bilibili subtitles plus ASR fallback, and temp-audio cleanup rules.
- [ ] Run unit tests and `python scripts/extract_video_transcript.py --help`.

### Task 3: Verify Integration

**Files:**
- No new files.

- [ ] Run `python -m unittest tests.test_extract_video_transcript -v`.
- [ ] Run `git diff --check`.
- [ ] Confirm `git status` only includes intended tracked changes plus existing transcript artifacts.
