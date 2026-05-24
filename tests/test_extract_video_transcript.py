import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts.extract_video_transcript import (
    TranscriptError,
    build_parser,
    detect_platform,
    download_audio_with_ytdlp,
    ensure_openmp_compatibility,
    extract,
    extract_with_local_asr,
    fetch_bilibili_subtitles,
    parse_subtitle_text,
    transcribe_with_faster_whisper,
    to_markdown,
    TranscriptResult,
)


class ExtractVideoTranscriptTests(unittest.TestCase):
    def test_detect_platform_from_urls(self):
        self.assertEqual(detect_platform("https://www.youtube.com/watch?v=abc12345678"), "youtube")
        self.assertEqual(detect_platform("https://youtu.be/abc12345678"), "youtube")
        self.assertEqual(detect_platform("https://www.bilibili.com/video/BV1xx411c7mD"), "bilibili")
        self.assertEqual(detect_platform("https://b23.tv/abcdef"), "bilibili")

    def test_detect_platform_rejects_unknown_sources(self):
        with self.assertRaisesRegex(TranscriptError, "Unsupported video source"):
            detect_platform("https://example.com/video/123")

    def test_downloaded_audio_is_deleted_after_successful_asr(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_audio = Path(tmp_dir) / "downloaded.m4a"

            def download_audio(_source, _temp_dir):
                temp_audio.write_text("audio", encoding="utf-8")
                return temp_audio

            def transcribe_audio(path, language, model_size):
                self.assertTrue(path.exists())
                self.assertEqual(language, "en")
                self.assertEqual(model_size, "base")
                return ["hello world"]

            result = extract_with_local_asr(
                "https://www.bilibili.com/video/BV123",
                language="en",
                model_size="base",
                download_audio=download_audio,
                transcribe_audio=transcribe_audio,
                temp_dir=Path(tmp_dir),
            )

            self.assertEqual(result.lines, ["hello world"])
            self.assertFalse(temp_audio.exists())

    def test_downloaded_audio_is_deleted_when_asr_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_audio = Path(tmp_dir) / "downloaded.m4a"

            def download_audio(_source, _temp_dir):
                temp_audio.write_text("audio", encoding="utf-8")
                return temp_audio

            def transcribe_audio(_path, _language, _model_size):
                raise TranscriptError("ASR failed")

            with self.assertRaisesRegex(TranscriptError, "ASR failed"):
                extract_with_local_asr(
                    "https://www.bilibili.com/video/BV123",
                    language="en",
                    model_size="base",
                    download_audio=download_audio,
                    transcribe_audio=transcribe_audio,
                    temp_dir=Path(tmp_dir),
                )

            self.assertFalse(temp_audio.exists())

    def test_created_temp_directory_is_deleted_after_success(self):
        captured_temp_dir = None

        def download_audio(_source, temp_dir):
            nonlocal captured_temp_dir
            captured_temp_dir = temp_dir
            audio = temp_dir / "downloaded.m4a"
            audio.write_text("audio", encoding="utf-8")
            return audio

        def transcribe_audio(_path, _language, _model_size):
            return ["temporary transcript"]

        result = extract_with_local_asr(
            "https://www.bilibili.com/video/BV123",
            language="en",
            model_size="base",
            download_audio=download_audio,
            transcribe_audio=transcribe_audio,
        )

        self.assertEqual(result.lines, ["temporary transcript"])
        self.assertIsNotNone(captured_temp_dir)
        self.assertFalse(captured_temp_dir.exists())

    def test_parse_vtt_and_srt_subtitles_into_clean_lines(self):
        subtitle_text = """WEBVTT

00:00:00.000 --> 00:00:02.000
<v Speaker>Hello &amp; welcome</v>

2
00:00:02,500 --> 00:00:04,000
Today we learn English.

00:00:04.000 --> 00:00:05.000
Today we learn English.
"""

        self.assertEqual(
            parse_subtitle_text(subtitle_text),
            ["Hello & welcome", "Today we learn English."],
        )

    def test_to_markdown_uses_common_transcript_format(self):
        markdown = to_markdown(
            lines=["Hello world"],
            source_url="https://example.com/video",
            title="Example Lesson",
            creator="Teacher",
            language="en",
            transcript_source="local ASR",
        )

        self.assertIn("# Transcript: Example Lesson", markdown)
        self.assertIn("- Source: https://example.com/video", markdown)
        self.assertIn("- Creator: Teacher", markdown)
        self.assertIn("- Subtitle source: local ASR", markdown)
        self.assertIn("- Hello world", markdown)

    def test_bilibili_prefers_existing_subtitles_over_local_asr(self):
        def fetch_bilibili_subtitles(_source, _language):
            return TranscriptResult(
                lines=["caption line"],
                source_url="https://www.bilibili.com/video/BV123",
                title="Bilibili Lesson",
                creator="Teacher",
                language="en",
                transcript_source="Bilibili subtitles",
            )

        def local_asr(**_kwargs):
            raise AssertionError("local ASR should not run when subtitles exist")

        transcript = extract(
            "https://www.bilibili.com/video/BV123",
            output_format="text",
            platform="auto",
            language="en",
            model_size="base",
            fetch_bilibili_subtitles=fetch_bilibili_subtitles,
            local_asr=local_asr,
        )

        self.assertEqual(transcript, "caption line\n")

    def test_bilibili_falls_back_to_local_asr_when_subtitles_are_missing(self):
        def fetch_bilibili_subtitles(_source, _language):
            return None

        def local_asr(**kwargs):
            self.assertEqual(kwargs["source"], "https://www.bilibili.com/video/BV123")
            return TranscriptResult(
                lines=["asr line"],
                source_url=kwargs["source"],
                title="Video",
                language="en",
                transcript_source="Bilibili audio + local ASR",
            )

        transcript = extract(
            "https://www.bilibili.com/video/BV123",
            output_format="text",
            platform="auto",
            language="en",
            model_size="base",
            fetch_bilibili_subtitles=fetch_bilibili_subtitles,
            local_asr=local_asr,
        )

        self.assertEqual(transcript, "asr line\n")

    def test_youtube_still_delegates_to_existing_supadata_extractor(self):
        def youtube_extract(source, output_format, supadata_mode):
            self.assertEqual(source, "https://www.youtube.com/watch?v=abc12345678")
            self.assertEqual(output_format, "markdown")
            self.assertEqual(supadata_mode, "auto")
            return "youtube transcript"

        transcript = extract(
            "https://www.youtube.com/watch?v=abc12345678",
            output_format="markdown",
            platform="auto",
            language="en",
            model_size="base",
            youtube_extract=youtube_extract,
        )

        self.assertEqual(transcript, "youtube transcript")

    def test_download_audio_with_ytdlp_writes_to_temp_directory(self):
        captured_command = None

        def run_command(command, **_kwargs):
            nonlocal captured_command
            captured_command = command
            output_template = Path(command[command.index("-o") + 1])
            output_file = output_template.parent / "audio.m4a"
            output_file.write_text("audio", encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio = download_audio_with_ytdlp(
                "https://www.bilibili.com/video/BV123",
                Path(tmp_dir),
                run_command=run_command,
            )

            self.assertEqual(audio.name, "audio.m4a")
            self.assertTrue(audio.exists())

        self.assertIsNotNone(captured_command)
        self.assertIn("yt-dlp", captured_command[0])
        self.assertNotIn("--extract-audio", captured_command)
        self.assertIn("-f", captured_command)
        self.assertIn("bestaudio/best", captured_command)

    def test_fetch_bilibili_subtitles_downloads_and_parses_subtitle_file(self):
        def run_command(command, **_kwargs):
            output_template = Path(command[command.index("-o") + 1])
            subtitle_file = output_template.parent / "subtitle.en.vtt"
            subtitle_file.write_text(
                "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello from Bilibili\n",
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_bilibili_subtitles(
                "https://www.bilibili.com/video/BV123",
                "en",
                temp_dir=Path(tmp_dir),
                run_command=run_command,
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.lines, ["Hello from Bilibili"])
        self.assertEqual(result.transcript_source, "Bilibili subtitles")

    def test_cli_parser_accepts_unified_options(self):
        args = build_parser().parse_args(
            [
                "https://www.bilibili.com/video/BV123",
                "--output",
                "transcript.md",
                "--format",
                "markdown",
                "--platform",
                "bilibili",
                "--language",
                "auto",
                "--model-size",
                "small",
            ]
        )

        self.assertEqual(args.source, "https://www.bilibili.com/video/BV123")
        self.assertEqual(args.output, "transcript.md")
        self.assertEqual(args.format, "markdown")
        self.assertEqual(args.platform, "bilibili")
        self.assertEqual(args.language, "auto")
        self.assertEqual(args.model_size, "small")

    def test_openmp_compatibility_sets_environment_default(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            ensure_openmp_compatibility()

            import os

            self.assertEqual(os.environ.get("KMP_DUPLICATE_LIB_OK"), "TRUE")


if __name__ == "__main__":
    unittest.main()
