#!/usr/bin/env python3
"""Publish a Markdown study note to a Feishu/Lark Docx document.

Configuration:
- FEISHU_APP_ID and FEISHU_APP_SECRET are required.
- FEISHU_FOLDER_TOKEN is optional.

Exit codes:
- 0: published successfully; stdout contains the document URL.
- 1: Feishu is configured but publishing failed.
- 2: Feishu is not configured; caller should fall back to Markdown output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
NOT_CONFIGURED_MESSAGE = "FEISHU_NOT_CONFIGURED"


class FeishuError(RuntimeError):
    pass


def read_markdown(input_path: str | None) -> str:
    if not input_path or input_path == "-":
        return sys.stdin.read()
    return Path(input_path).read_text(encoding="utf-8")


def feishu_config() -> tuple[str, str, str]:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    folder_token = os.environ.get("FEISHU_FOLDER_TOKEN", "").strip()
    if not app_id or not app_secret:
        raise FeishuError(NOT_CONFIGURED_MESSAGE)
    return app_id, app_secret, folder_token


def request_json(
    method: str,
    path_or_url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = path_or_url if path_or_url.startswith("http") else f"{FEISHU_BASE_URL}{path_or_url}"
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "accept": "application/json",
        "content-type": "application/json; charset=utf-8",
        "user-agent": "youtube-english-learning-skill/1.0",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise FeishuError(f"Feishu HTTP {exc.code}: {raw[:800]}") from exc
    except urllib.error.URLError as exc:
        raise FeishuError(f"Feishu request failed: {exc}") from exc

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeishuError(f"Feishu returned non-JSON response: {raw[:800]}") from exc

    code = data.get("code", 0)
    if code not in (0, None):
        message = data.get("msg") or data.get("message") or "unknown error"
        raise FeishuError(f"Feishu API error {code}: {message}")
    return data


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    data = request_json(
        "POST",
        "/auth/v3/tenant_access_token/internal",
        payload={"app_id": app_id, "app_secret": app_secret},
    )
    token = data.get("tenant_access_token") or data.get("data", {}).get("tenant_access_token")
    if not token:
        raise FeishuError("Feishu did not return tenant_access_token.")
    return str(token)


def create_document(token: str, title: str, folder_token: str = "") -> tuple[str, str]:
    payload: dict[str, Any] = {"title": title}
    if folder_token:
        payload["folder_token"] = folder_token

    data = request_json("POST", "/docx/v1/documents", token=token, payload=payload)
    document = data.get("data", {}).get("document") or data.get("data", {})
    document_id = (
        document.get("document_id")
        or document.get("documentId")
        or document.get("token")
        or document.get("obj_token")
    )
    if not document_id:
        raise FeishuError(f"Feishu create document response did not include document_id: {data}")

    url = document.get("url") or document.get("document_url") or f"https://feishu.cn/docx/{document_id}"
    return str(document_id), str(url)


def convert_markdown_with_feishu(token: str, document_id: str, markdown: str) -> list[dict[str, Any]]:
    data = request_json(
        "POST",
        f"/docx/v1/documents/{urllib.parse.quote(document_id)}/convert",
        token=token,
        payload={"content_type": "markdown", "content": markdown},
    )
    blocks = data.get("data", {}).get("blocks") or data.get("data", {}).get("children")
    if not isinstance(blocks, list) or not blocks:
        raise FeishuError("Feishu Markdown converter returned no blocks.")
    return [block for block in blocks if isinstance(block, dict)]


def text_elements(content: str) -> list[dict[str, Any]]:
    return [{"text_run": {"content": content, "text_element_style": {}}}]


def text_block(block_type: int, key: str, content: str) -> dict[str, Any]:
    return {
        "block_type": block_type,
        key: {
            "elements": text_elements(content),
            "style": {},
        },
    }


def markdown_to_basic_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    table_buffer: list[str] = []

    def flush_table() -> None:
        nonlocal table_buffer
        if table_buffer:
            blocks.append(text_block(2, "text", "\n".join(table_buffer)))
            table_buffer = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_table()
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            table_buffer.append(stripped)
            continue

        flush_table()

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = min(len(heading.group(1)), 6)
            blocks.append(text_block(2 + level, f"heading{level}", heading.group(2).strip()))
            continue

        unordered = re.match(r"^[-*+]\s+(.+)$", stripped)
        if unordered:
            blocks.append(text_block(12, "bullet", unordered.group(1).strip()))
            continue

        ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if ordered:
            blocks.append(text_block(13, "ordered", ordered.group(1).strip()))
            continue

        blocks.append(text_block(2, "text", stripped))

    flush_table()
    return blocks


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def append_blocks(token: str, document_id: str, blocks: list[dict[str, Any]]) -> None:
    if not blocks:
        return

    # Feishu's root page block ID is the document ID for newly created Docx documents.
    parent_block_id = document_id
    for group in chunked(blocks, 50):
        request_json(
            "POST",
            f"/docx/v1/documents/{urllib.parse.quote(document_id)}/blocks/"
            f"{urllib.parse.quote(parent_block_id)}/children",
            token=token,
            payload={"children": group, "index": -1},
        )


def publish(markdown: str, title: str) -> str:
    app_id, app_secret, folder_token = feishu_config()
    token = get_tenant_access_token(app_id, app_secret)
    document_id, document_url = create_document(token, title, folder_token)

    try:
        blocks = convert_markdown_with_feishu(token, document_id, markdown)
    except FeishuError:
        blocks = markdown_to_basic_blocks(markdown)

    append_blocks(token, document_id, blocks)
    return document_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a Markdown study note to Feishu Docx.")
    parser.add_argument("--input", "-i", help="Markdown input file. Omit or pass '-' to read stdin.")
    parser.add_argument("--title", "-t", required=True, help="Feishu document title.")
    args = parser.parse_args()

    try:
        markdown = read_markdown(args.input)
        url = publish(markdown, args.title)
    except FeishuError as exc:
        message = str(exc)
        if message == NOT_CONFIGURED_MESSAGE:
            print(NOT_CONFIGURED_MESSAGE, file=sys.stderr)
            return 2
        print(f"FEISHU_PUBLISH_FAILED: {message}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"FEISHU_PUBLISH_FAILED: {exc}", file=sys.stderr)
        return 1

    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
