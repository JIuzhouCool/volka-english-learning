#!/usr/bin/env python3
"""Extract video transcripts from YouTube or Bilibili."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from extractors import get_extractor, TranscriptError
from extractors.youtube import YouTubeExtractor  # noqa: F401
from extractors.bilibili import BilibiliExtractor  # noqa: F401


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract video transcripts")
    parser.add_argument("url", help="Video URL (YouTube or Bilibili)")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--format", choices=["markdown", "text"], default="markdown")
    parser.add_argument("--supadata-mode", choices=["native", "auto", "generate"], default="auto")
    args = parser.parse_args()

    extractor = get_extractor(args.url)
    if not extractor:
        print("Error: Unsupported platform. Use YouTube or Bilibili URLs.", file=sys.stderr)
        return 1

    if isinstance(extractor, YouTubeExtractor):
        extractor.mode = args.supadata_mode

    try:
        result = extractor.extract(args.url)
    except TranscriptError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    body = "\n".join(f"- {line}" for line in result.lines)
    output = (
        f"# {result.title}\n\n"
        f"- Source: {result.source_url}\n"
        f"- Creator: {result.creator}\n"
        f"- Language: {result.language}\n"
        f"- Platform: {result.transcript_source}\n\n"
        f"## Transcript\n\n{body}\n"
    ) if args.format == "markdown" else "\n".join(result.lines) + "\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved: {args.output}")
    else:
        sys.stdout.buffer.write(output.encode("utf-8"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
