"""YouTube transcript extractor using Supadata API."""
from __future__ import annotations
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any
from . import BaseExtractor, TranscriptResult, TranscriptError, register_extractor

SUPADATA_URL = "https://api.supadata.ai/v1/transcript"
MAX_POLL = 12
POLL_INTERVAL = 5


@register_extractor
class YouTubeExtractor(BaseExtractor):
    platform_name = "YouTube"
    supported_hosts = ["youtube.com", "youtu.be"]

    def __init__(self, mode: str = "auto"):
        self.mode = mode

    def extract(self, url: str) -> TranscriptResult:
        api_key = os.environ.get("SUPADATA_API_KEY", "").strip()
        if not api_key:
            raise TranscriptError(
                "SUPADATA_API_KEY required. Get key at https://dash.supadata.ai"
            )

        vid = self._get_video_id(url)
        source_url = f"https://www.youtube.com/watch?v={vid}"
        params = urllib.parse.urlencode({"url": source_url, "lang": "en", "text": "true", "mode": self.mode})

        status, payload = self._request(f"{SUPADATA_URL}?{params}", api_key)

        if isinstance(payload, dict) and (job_id := payload.get("jobId") or payload.get("job_id")):
            if status == 202:
                payload = self._poll_job(api_key, job_id)

        return self._parse_result(payload, source_url)

    def _get_video_id(self, url: str) -> str:
        url = url.strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
            return url

        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        path = [p for p in parsed.path.split("/") if p]

        if "youtu.be" in host and path:
            return path[0]
        if "youtube.com" in host:
            if qid := urllib.parse.parse_qs(parsed.query).get("v", [None])[0]:
                return qid
            if len(path) >= 2 and path[0] in {"shorts", "embed", "live"}:
                return path[1]

        raise TranscriptError("Invalid YouTube URL")

    def _request(self, url: str, api_key: str) -> tuple[int, Any]:
        req = urllib.request.Request(
            url,
            headers={"x-api-key": api_key, "accept": "application/json"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            raise TranscriptError(f"Supadata HTTP {e.code}: {body[:200]}")

    def _poll_job(self, api_key: str, job_id: str) -> dict:
        url = f"{SUPADATA_URL}/{urllib.parse.quote(job_id, safe='')}"
        for _ in range(MAX_POLL):
            _, payload = self._request(url, api_key)
            if isinstance(payload, dict):
                status = str(payload.get("status", "")).lower()
                if status == "completed":
                    return payload
                if status == "failed":
                    raise TranscriptError("Transcript job failed")
            time.sleep(POLL_INTERVAL)
        raise TranscriptError("Transcript job timeout")

    def _parse_result(self, payload: Any, source_url: str) -> TranscriptResult:
        lines = self._extract_lines(payload)
        if not lines:
            raise TranscriptError("No transcript found")

        data = payload if isinstance(payload, dict) else {}
        return TranscriptResult(
            lines=lines,
            source_url=source_url,
            title=data.get("title") or data.get("videoTitle") or "YouTube video",
            creator=data.get("author") or data.get("channel") or "Unknown",
            language=data.get("language") or data.get("lang") or "en",
            transcript_source=f"Supadata ({self.mode})"
        )

    def _extract_lines(self, payload: Any) -> list[str]:
        if isinstance(payload, str):
            return self._clean(payload.splitlines())

        if not isinstance(payload, dict):
            return []

        # Try common keys
        for key in ("text", "transcript", "content"):
            if isinstance(val := payload.get(key), str):
                return self._clean(val.splitlines())

        # Try array formats
        for key in ("content", "segments", "items", "captions", "chunks"):
            if isinstance(arr := payload.get(key), list):
                lines = []
                for item in arr:
                    if isinstance(item, str):
                        lines.append(item)
                    elif isinstance(item, dict):
                        if txt := item.get("text") or item.get("content") or item.get("caption"):
                            lines.append(str(txt))
                return self._clean(lines)

        # Try nested data
        if nested := payload.get("data"):
            return self._extract_lines(nested)

        return []

    def _clean(self, lines: list[str]) -> list[str]:
        result = []
        prev = ""
        for line in lines:
            text = html.unescape(str(line))
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            if text and text != prev:
                result.append(text)
                prev = text
        return result
