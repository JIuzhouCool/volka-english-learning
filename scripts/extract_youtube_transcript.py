#!/usr/bin/env python3
"""Extract English transcripts from YouTube videos with Supadata.

SUPADATA_API_KEY is required. By default this script uses Supadata mode
``auto``: fetch existing captions first, then generate a transcript with AI
when captions are unavailable.

This script intentionally does not use yt-dlp, download audio, run local ASR,
or fall back to local transcript libraries.
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
    transcript_source: str = "Supadata API"


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
    return str(payload.get("message") or payload.get("msg") or "Unknown Supadata error.")


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
        raise TranscriptError(
            "Supadata returned a response, but no transcript text was found. "
            "Retry later or paste the transcript directly."
        )

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
            "SUPADATA_API_KEY is required.\n\n"
            "Get a key at https://dash.supadata.ai and configure it, for example:\n"
            '  $env:SUPADATA_API_KEY="your_supadata_key"'
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


def extract(url: str, output_format: str, supadata_mode: str) -> str:
    result = fetch_with_supadata(url, supadata_mode)
    if output_format == "text":
        return to_text(result.lines)
    return to_markdown(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract English YouTube transcripts with Supadata.")
    parser.add_argument("url", help="YouTube video URL or video ID")
    parser.add_argument("--output", "-o", help="Write transcript to this file instead of stdout")
    parser.add_argument(
        "--format",
        choices=("markdown", "text"),
        default="markdown",
        help="Output format. Default: markdown",
    )
    parser.add_argument(
        "--supadata-mode",
        choices=("native", "auto", "generate"),
        default="auto",
        help="Supadata mode. Default: auto fetches existing captions, then generates with AI if needed.",
    )
    args = parser.parse_args()

    try:
        transcript = extract(args.url, args.format, args.supadata_mode)
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
