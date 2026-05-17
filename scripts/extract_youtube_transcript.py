#!/usr/bin/env python3
"""Extract English transcripts from YouTube videos.

Default strategy:
1. Use Supadata first when SUPADATA_API_KEY is configured.
2. Fall back to youtube-transcript-api for local, no-key extraction.
3. If both fail, ask the user to paste the transcript.

This script intentionally does not use yt-dlp, download audio, or run local ASR.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LANGUAGE_PRIORITY = ("en", "en-US", "en-GB")
SUPADATA_TRANSCRIPT_URL = "https://api.supadata.ai/v1/transcript"
SUPADATA_MAX_POLL_ATTEMPTS = 12
SUPADATA_POLL_INTERVAL_SECONDS = 5


class TranscriptError(RuntimeError):
    pass


@dataclass
class TranscriptResult:
    lines: list[str]
    source_url: str
    title: str = "YouTube video"
    creator: str = "Unknown"
    language: str = "en"
    transcript_source: str = "unknown"


def extract_video_id(url_or_id: str) -> str:
    value = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    parsed = urllib.parse.urlparse(value)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if "youtu.be" in host and path_parts:
        return path_parts[0]

    if "youtube.com" in host:
        query_id = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            return path_parts[1]

    raise TranscriptError(
        "Could not determine the YouTube video ID from the URL.\n\n"
        "Pass a normal YouTube URL or an 11-character video ID."
    )


def canonical_youtube_url(url_or_id: str) -> str:
    return f"https://www.youtube.com/watch?v={extract_video_id(url_or_id)}"


def clean_text(text: str) -> str:
    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe_adjacent(lines: list[str]) -> list[str]:
    deduped: list[str] = []
    previous = ""
    for line in lines:
        cleaned = clean_text(line)
        if cleaned and cleaned != previous:
            deduped.append(cleaned)
        previous = cleaned
    return deduped


def english_language_codes(candidates: list[Any]) -> list[str]:
    found: list[str] = []
    for candidate in candidates:
        lang = getattr(candidate, "language_code", "")
        if lang.startswith("en") and lang not in found:
            found.append(lang)
    prioritized = [lang for lang in LANGUAGE_PRIORITY if lang in found]
    prioritized.extend(sorted(lang for lang in found if lang not in prioritized))
    return prioritized


def extract_lines_from_supadata_payload(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return dedupe_adjacent(payload.splitlines())

    if not isinstance(payload, dict):
        return []

    for key in ("text", "transcript", "content"):
        value = payload.get(key)
        if isinstance(value, str):
            return dedupe_adjacent(value.splitlines())

    for key in ("content", "segments", "items", "captions", "chunks"):
        value = payload.get(key)
        if isinstance(value, list):
            lines: list[str] = []
            for item in value:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or item.get("caption")
                    if text:
                        lines.append(str(text))
            if lines:
                return dedupe_adjacent(lines)

    nested = payload.get("data")
    if nested is not None:
        return extract_lines_from_supadata_payload(nested)

    return []


def supadata_payload_error(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Unknown Supadata error."

    error = payload.get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        message = error.get("message") or error.get("error") or error.get("details")
        if message:
            return str(message)
    return "Unknown Supadata error."


def supadata_error_message(status: int, body: str) -> str:
    body_hint = body.strip()
    if len(body_hint) > 500:
        body_hint = body_hint[:500] + "..."

    if status == 401:
        return "Supadata rejected the request with 401. Check SUPADATA_API_KEY."
    if status == 402:
        return "Supadata rejected the request with 402. Check account credits or billing."
    if status == 429:
        return "Supadata rejected the request with 429. Rate limit reached; retry later."
    return f"Supadata returned HTTP {status}. Response: {body_hint}"


def request_supadata_json(url: str, api_key: str) -> tuple[int, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "x-api-key": api_key,
            "accept": "application/json",
            "user-agent": "youtube-english-learning-skill/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TranscriptError(supadata_error_message(exc.code, body)) from exc
    except urllib.error.URLError as exc:
        raise TranscriptError(f"Supadata request failed: {exc}") from exc

    try:
        payload: Any = json.loads(body)
    except json.JSONDecodeError:
        payload = body

    return status, payload


def supadata_result_from_payload(payload: Any, source_url: str, transcript_source: str) -> TranscriptResult:
    lines = extract_lines_from_supadata_payload(payload)
    if not lines:
        raise TranscriptError("Supadata returned a response, but no transcript text was found.")

    title = "YouTube video"
    creator = "Unknown"
    language = "en"
    if isinstance(payload, dict):
        title = str(payload.get("title") or payload.get("videoTitle") or title)
        creator = str(payload.get("author") or payload.get("channel") or payload.get("creator") or creator)
        language = str(payload.get("language") or payload.get("lang") or language)

    return TranscriptResult(
        lines=lines,
        source_url=source_url,
        title=title,
        creator=creator,
        language=language,
        transcript_source=transcript_source,
    )


def fetch_supadata_job_result(api_key: str, job_id: str, source_url: str, mode: str) -> TranscriptResult:
    job_url = f"{SUPADATA_TRANSCRIPT_URL}/{urllib.parse.quote(job_id, safe='')}"

    for attempt in range(1, SUPADATA_MAX_POLL_ATTEMPTS + 1):
        _, payload = request_supadata_json(job_url, api_key)

        if isinstance(payload, dict):
            status = str(payload.get("status") or "").lower()
            if status == "failed":
                raise TranscriptError(f"Supadata transcript job failed: {supadata_payload_error(payload)}")
            if status == "completed":
                return supadata_result_from_payload(
                    payload,
                    source_url,
                    f"Supadata API ({mode}, async job)",
                )

            lines = extract_lines_from_supadata_payload(payload)
            if lines:
                return supadata_result_from_payload(
                    payload,
                    source_url,
                    f"Supadata API ({mode}, async job)",
                )

        if attempt < SUPADATA_MAX_POLL_ATTEMPTS:
            time.sleep(SUPADATA_POLL_INTERVAL_SECONDS)

    raise TranscriptError(
        "Supadata returned a transcript job ID, but the job did not complete within "
        f"{SUPADATA_MAX_POLL_ATTEMPTS * SUPADATA_POLL_INTERVAL_SECONDS} seconds. Retry later."
    )


def fetch_with_supadata(url_or_id: str, mode: str) -> TranscriptResult:
    api_key = os.environ.get("SUPADATA_API_KEY", "").strip()
    if not api_key:
        raise TranscriptError(
            "SUPADATA_API_KEY is not set.\n\n"
            "Configure it in PowerShell with:\n"
            '  $env:SUPADATA_API_KEY="your_key"'
        )

    source_url = canonical_youtube_url(url_or_id)
    params = urllib.parse.urlencode(
        {
            "url": source_url,
            "lang": "en",
            "text": "true",
            "mode": mode,
        }
    )
    status, payload = request_supadata_json(f"{SUPADATA_TRANSCRIPT_URL}?{params}", api_key)

    if isinstance(payload, dict):
        job_id = payload.get("jobId") or payload.get("job_id") or payload.get("id")
        if status == 202 or job_id:
            if not job_id:
                raise TranscriptError("Supadata returned HTTP 202, but no job ID was found.")
            return fetch_supadata_job_result(api_key, str(job_id), source_url, mode)

    return supadata_result_from_payload(payload, source_url, f"Supadata API ({mode})")


def fetch_with_transcript_api(url_or_id: str) -> TranscriptResult:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise TranscriptError(
            "youtube-transcript-api is not installed.\n\n"
            "Install it with:\n"
            "  python -m pip install youtube-transcript-api"
        ) from exc

    video_id = extract_video_id(url_or_id)
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
        transcripts = list(transcript_list)
        languages = english_language_codes(transcripts)
        if not languages:
            available = ", ".join(getattr(item, "language_code", "?") for item in transcripts) or "none"
            raise TranscriptError(
                "youtube-transcript-api found transcripts, but none were English.\n\n"
                f"Available transcript languages: {available}"
            )

        try:
            transcript = transcript_list.find_manually_created_transcript(languages)
        except Exception:
            transcript = transcript_list.find_generated_transcript(languages)

        fetched = transcript.fetch()
        raw_items = fetched.to_raw_data()
    except TranscriptError:
        raise
    except Exception as exc:
        raise TranscriptError(f"youtube-transcript-api could not fetch this transcript: {exc}") from exc

    lines = dedupe_adjacent([item.get("text", "") for item in raw_items])
    if not lines:
        raise TranscriptError("youtube-transcript-api returned an empty transcript.")

    language = getattr(transcript, "language_code", languages[0])
    is_generated = bool(getattr(transcript, "is_generated", False))
    source = "youtube-transcript-api automatic captions" if is_generated else "youtube-transcript-api manual subtitles"
    return TranscriptResult(
        lines=lines,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        language=language,
        transcript_source=source,
    )


def to_markdown(result: TranscriptResult) -> str:
    body = "\n".join(f"- {line}" for line in result.lines)
    return (
        f"# Transcript: {result.title}\n\n"
        f"- Source: {result.source_url}\n"
        f"- Creator: {result.creator}\n"
        f"- Subtitle language: {result.language}\n"
        f"- Subtitle source: {result.transcript_source}\n\n"
        "## Transcript\n\n"
        f"{body}\n"
    )


def to_text(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def extract(url: str, output_format: str, provider: str, supadata_mode: str) -> str:
    errors: list[str] = []
    result: TranscriptResult | None = None

    if provider in {"auto", "supadata"}:
        try:
            result = fetch_with_supadata(url, supadata_mode)
        except TranscriptError as exc:
            errors.append(f"Supadata: {exc}")
            if provider == "supadata":
                raise

    if result is None and provider in {"auto", "local-api"}:
        try:
            result = fetch_with_transcript_api(url)
        except TranscriptError as exc:
            errors.append(f"youtube-transcript-api: {exc}")
            if provider == "local-api":
                raise

    if result is None:
        raise TranscriptError(
            "Could not extract an English transcript with the available providers.\n\n"
            + "\n\n".join(errors)
            + "\n\nNext steps:\n"
            "  1. Set SUPADATA_API_KEY and retry.\n"
            "  2. Or install youtube-transcript-api: python -m pip install youtube-transcript-api\n"
            "  3. Or paste the transcript directly."
        )

    if output_format == "text":
        return to_text(result.lines)
    return to_markdown(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract English YouTube transcripts.")
    parser.add_argument("url", help="YouTube video URL or video ID")
    parser.add_argument("--output", "-o", help="Write transcript to this file instead of stdout")
    parser.add_argument(
        "--format",
        choices=("markdown", "text"),
        default="markdown",
        help="Output format. Default: markdown",
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "supadata", "local-api"),
        default="auto",
        help="Transcript provider. Default: auto uses Supadata, then youtube-transcript-api.",
    )
    parser.add_argument(
        "--supadata-mode",
        choices=("native", "auto", "generate"),
        default="native",
        help="Supadata mode. Default: native uses existing captions only.",
    )
    args = parser.parse_args()

    try:
        transcript = extract(args.url, args.format, args.provider, args.supadata_mode)
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
