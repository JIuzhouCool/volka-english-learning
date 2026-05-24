#!/usr/bin/env python3
"""Extract transcripts from YouTube or Bilibili videos."""

from __future__ import annotations

import html
import argparse
import re
import subprocess
import sys
import tempfile
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class TranscriptError(RuntimeError):
    pass


@dataclass
class TranscriptResult:
    lines: list[str]
    source_url: str
    title: str = "Video"
    creator: str = "Unknown"
    language: str = "en"
    transcript_source: str = "local ASR"


PLATFORMS = ("auto", "youtube", "bilibili")


DownloadAudio = Callable[[str, Path], Path]
TranscribeAudio = Callable[[Path, str, str], list[str]]
FetchBilibiliSubtitles = Callable[[str, str], TranscriptResult | None]
LocalAsr = Callable[..., TranscriptResult]
YoutubeExtract = Callable[[str, str, str], str]
RunCommand = Callable[..., object]


def detect_platform(source: str) -> str:
    value = source.strip()
    parsed = urllib.parse.urlparse(value)
    host = parsed.netloc.lower()

    if "youtu.be" in host or "youtube.com" in host:
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"

    raise TranscriptError(f"Unsupported video source: {source}")


def clean_text(text: str) -> str:
    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    previous = ""
    for line in lines:
        value = clean_text(line)
        if value and value != previous:
            cleaned.append(value)
        previous = value
    return cleaned


def parse_subtitle_text(subtitle_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in subtitle_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper() == "WEBVTT":
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if "-->" in line:
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        lines.append(line)
    return clean_lines(lines)


def to_markdown(
    *,
    lines: list[str],
    source_url: str,
    title: str,
    creator: str,
    language: str,
    transcript_source: str,
) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return (
        f"# Transcript: {title}\n\n"
        f"- Source: {source_url}\n"
        f"- Creator: {creator}\n"
        f"- Subtitle language: {language}\n"
        f"- Subtitle source: {transcript_source}\n\n"
        "## Transcript\n\n"
        f"{body}\n"
    )


def to_text(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def format_result(result: TranscriptResult, output_format: str) -> str:
    if output_format == "text":
        return to_text(result.lines)
    return to_markdown(
        lines=result.lines,
        source_url=result.source_url,
        title=result.title,
        creator=result.creator,
        language=result.language,
        transcript_source=result.transcript_source,
    )


def _missing_download_audio(_source: str, _temp_dir: Path) -> Path:
    raise TranscriptError("Audio download is not configured.")


def _missing_transcribe_audio(_path: Path, _language: str, _model_size: str) -> list[str]:
    raise TranscriptError("Local ASR is not configured.")


def extract_with_local_asr(
    source: str,
    *,
    language: str,
    model_size: str,
    download_audio: DownloadAudio = _missing_download_audio,
    transcribe_audio: TranscribeAudio = _missing_transcribe_audio,
    temp_dir: Path | None = None,
) -> TranscriptResult:
    created_temp_dir: tempfile.TemporaryDirectory[str] | None = None
    audio_path: Path | None = None

    try:
        if temp_dir is None:
            created_temp_dir = tempfile.TemporaryDirectory(prefix="volka-transcript-")
            temp_dir = Path(created_temp_dir.name)
        audio_path = download_audio(source, temp_dir)

        lines = clean_lines(transcribe_audio(audio_path, language, model_size))
        if not lines:
            raise TranscriptError("Local ASR produced no transcript text.")

        return TranscriptResult(
            lines=lines,
            source_url=source,
            language=language,
            transcript_source="Bilibili audio + local ASR",
        )
    finally:
        if audio_path is not None and audio_path.exists():
            audio_path.unlink()
        if created_temp_dir is not None:
            created_temp_dir.cleanup()


def _newest_media_file(directory: Path) -> Path | None:
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def download_audio_with_ytdlp(
    source: str,
    temp_dir: Path,
    *,
    run_command: RunCommand = subprocess.run,
) -> Path:
    output_template = temp_dir / "audio.%(ext)s"
    command = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "bestaudio/best",
        "-o",
        str(output_template),
        source,
    ]

    try:
        run_command(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise TranscriptError("yt-dlp is required to download audio for local transcription.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = str(exc.stderr or "").strip()
        raise TranscriptError(f"yt-dlp failed to download audio: {stderr or exc}") from exc

    audio_path = _newest_media_file(temp_dir)
    if audio_path is None:
        raise TranscriptError("yt-dlp finished, but no audio file was created.")
    return audio_path


def ensure_openmp_compatibility() -> None:
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def transcribe_with_faster_whisper(audio_path: Path, language: str, model_size: str) -> list[str]:
    ensure_openmp_compatibility()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptError(
            "faster-whisper is required for local ASR. Install it with: pip install faster-whisper"
        ) from exc

    model = WhisperModel(model_size, device="auto", compute_type="auto")
    asr_language = None if language == "auto" else language
    segments, _info = model.transcribe(str(audio_path), language=asr_language, vad_filter=True)
    return clean_lines([segment.text for segment in segments])


def fetch_bilibili_subtitles(
    source: str,
    language: str,
    temp_dir: Path | None = None,
    run_command: RunCommand = subprocess.run,
) -> TranscriptResult | None:
    created_temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if temp_dir is None:
        created_temp_dir = tempfile.TemporaryDirectory(prefix="volka-bilibili-subs-")
        temp_dir = Path(created_temp_dir.name)

    try:
        output_template = temp_dir / "subtitle.%(ext)s"
        command = [
            "yt-dlp",
            "--no-playlist",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            language,
            "--sub-format",
            "vtt/srt/best",
            "-o",
            str(output_template),
            source,
        ]

        try:
            run_command(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

        for path in sorted(temp_dir.iterdir()):
            if path.suffix.lower() not in {".vtt", ".srt", ".ass"}:
                continue
            lines = parse_subtitle_text(path.read_text(encoding="utf-8", errors="replace"))
            if lines:
                return TranscriptResult(
                    lines=lines,
                    source_url=source,
                    title="Bilibili video",
                    creator="Unknown",
                    language=language,
                    transcript_source="Bilibili subtitles",
                )
        return None
    finally:
        if created_temp_dir is not None:
            created_temp_dir.cleanup()


def _default_local_asr(**kwargs: object) -> TranscriptResult:
    kwargs.setdefault("download_audio", download_audio_with_ytdlp)
    kwargs.setdefault("transcribe_audio", transcribe_with_faster_whisper)
    return extract_with_local_asr(**kwargs)  # type: ignore[arg-type]


def _default_youtube_extract(source: str, output_format: str, supadata_mode: str) -> str:
    try:
        from scripts.extract_youtube_transcript import extract as youtube_extract
    except ModuleNotFoundError:
        from extract_youtube_transcript import extract as youtube_extract

    return youtube_extract(source, output_format, supadata_mode)


def extract(
    source: str,
    *,
    output_format: str,
    platform: str,
    language: str,
    model_size: str,
    supadata_mode: str = "auto",
    youtube_extract: YoutubeExtract = _default_youtube_extract,
    fetch_bilibili_subtitles: FetchBilibiliSubtitles = fetch_bilibili_subtitles,
    local_asr: LocalAsr = _default_local_asr,
) -> str:
    resolved_platform = detect_platform(source) if platform == "auto" else platform

    if resolved_platform == "youtube":
        return youtube_extract(source, output_format, supadata_mode)

    if resolved_platform == "bilibili":
        subtitle_result = fetch_bilibili_subtitles(source, language)
        if subtitle_result is not None:
            return format_result(subtitle_result, output_format)
        result = local_asr(
            source=source,
            language=language,
            model_size=model_size,
        )
        return format_result(result, output_format)

    raise TranscriptError(f"Unsupported platform: {resolved_platform}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract transcripts from YouTube or Bilibili videos."
    )
    parser.add_argument("source", help="Video URL")
    parser.add_argument("--output", "-o", help="Write transcript to this file instead of stdout")
    parser.add_argument(
        "--format",
        choices=("markdown", "text"),
        default="markdown",
        help="Output format. Default: markdown",
    )
    parser.add_argument(
        "--platform",
        choices=PLATFORMS,
        default="auto",
        help="Platform override. Default: auto",
    )
    parser.add_argument(
        "--language",
        default="en",
        help='Transcript language hint. Use "auto" for local ASR language detection. Default: en',
    )
    parser.add_argument(
        "--model-size",
        default="base",
        help="faster-whisper model size for local ASR. Default: base",
    )
    parser.add_argument(
        "--supadata-mode",
        choices=("native", "auto", "generate"),
        default="auto",
        help="YouTube Supadata mode. Default: auto",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        transcript = extract(
            args.source,
            output_format=args.format,
            platform=args.platform,
            language=args.language,
            model_size=args.model_size,
            supadata_mode=args.supadata_mode,
        )
    except TranscriptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(transcript, encoding="utf-8")
    else:
        sys.stdout.buffer.write(transcript.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
