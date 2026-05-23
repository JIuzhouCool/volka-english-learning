"""Bilibili transcript extractor using official API."""
from __future__ import annotations
import json
import re
import urllib.error
import urllib.request
from typing import Any
from . import BaseExtractor, TranscriptResult, TranscriptError, register_extractor

API_BASE = "https://api.bilibili.com"


@register_extractor
class BilibiliExtractor(BaseExtractor):
    platform_name = "Bilibili"
    supported_hosts = ["bilibili.com", "b23.tv"]

    def extract(self, url: str) -> TranscriptResult:
        bvid = self._get_bvid(url)
        info = self._get_video_info(bvid)
        cid = info.get("cid")
        title = info.get("title", "Bilibili video")
        creator = info.get("owner", {}).get("name", "Unknown")

        if not cid:
            raise TranscriptError("Could not get video CID")

        subtitles = self._get_subtitles(bvid, cid)
        if not subtitles:
            raise TranscriptError(
                "No CC subtitles available. Please paste transcript manually."
            )

        sub = subtitles[0]
        lines = self._download_subtitle(sub.get("subtitle_url", ""))

        return TranscriptResult(
            lines=lines,
            source_url=f"https://www.bilibili.com/video/{bvid}",
            title=title,
            creator=creator,
            language=sub.get("lan", "zh"),
            transcript_source="Bilibili CC"
        )

    def _get_bvid(self, url: str) -> str:
        url = url.strip()

        if "b23.tv" in url.lower():
            return self._resolve_short(url)

        if m := re.search(r"/video/(BV[\w]+)", url):
            return m.group(1)

        parsed = urllib.parse.urlparse(url)
        if bvid := urllib.parse.parse_qs(parsed.query).get("bvid", [None])[0]:
            return bvid

        raise TranscriptError("Invalid Bilibili URL")

    def _resolve_short(self, url: str) -> str:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                final = r.geturl()
                return self._get_bvid(final)
        except urllib.error.URLError as e:
            raise TranscriptError(f"Cannot resolve short URL: {e}")

    def _request(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            raise TranscriptError(f"API error: {e}")

        if data.get("code") != 0:
            raise TranscriptError(data.get("message", "API error"))
        return data.get("data", {})

    def _get_video_info(self, bvid: str) -> dict[str, Any]:
        return self._request(f"{API_BASE}/x/web-interface/view?bvid={bvid}")

    def _get_subtitles(self, bvid: str, cid: int) -> list[dict]:
        data = self._request(f"{API_BASE}/x/player/wbi/v2?cid={cid}&bvid={bvid}")
        return data.get("subtitle", {}).get("subtitles", [])

    def _download_subtitle(self, url: str) -> list[str]:
        if not url:
            return []
        if not url.startswith("http"):
            url = f"https:{url}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.bilibili.com"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            raise TranscriptError(f"Subtitle download error: {e}")

        body = data.get("body", [])
        seen = set()
        lines = []
        for item in body:
            if content := item.get("content", "").strip():
                if content not in seen:
                    lines.append(content)
                    seen.add(content)
        return lines
