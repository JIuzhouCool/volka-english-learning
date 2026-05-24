#!/usr/bin/env python3
"""Publish a Markdown study note to a Feishu/Lark Docx document.

Configuration:
- FEISHU_APP_ID and FEISHU_APP_SECRET are required.

Exit codes:
- 0: published successfully; stdout contains the document URL.
- 1: Feishu is configured but publishing failed.
- 2: Feishu is not configured; caller should fall back to Markdown output.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import time
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
NOT_CONFIGURED_MESSAGE = "FEISHU_NOT_CONFIGURED"


class FeishuError(RuntimeError):
    def __init__(self, message: str, *, api_code: int | None = None) -> None:
        super().__init__(message)
        self.api_code = api_code


def api_code_from_data(data: dict[str, Any]) -> int | None:
    code = data.get("code")
    if isinstance(code, int):
        return code
    if isinstance(code, str) and code.isdigit():
        return int(code)
    return None


def api_code_from_raw(raw: str) -> int | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return api_code_from_data(data)
    return None


def read_markdown(input_path: str | None) -> str:
    if not input_path or input_path == "-":
        return sys.stdin.read()
    return Path(input_path).read_text(encoding="utf-8")


def delete_published_markdown(input_path: str | None) -> None:
    if not input_path or input_path == "-":
        return
    path = Path(input_path)
    if path.exists():
        path.unlink()


def windows_environment_value(name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg
    except ImportError:
        return ""

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return ""
    return os.path.expandvars(str(value))


def config_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    return windows_environment_value(name).strip()


def feishu_config() -> tuple[str, str]:
    app_id = config_value("FEISHU_APP_ID")
    app_secret = config_value("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise FeishuError(NOT_CONFIGURED_MESSAGE)
    return app_id, app_secret


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
        "user-agent": "volka-english-learning-skill/1.0",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    last_error: urllib.error.URLError | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise FeishuError(f"Feishu HTTP {exc.code}: {raw[:800]}", api_code=api_code_from_raw(raw)) from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == 2:
                raise FeishuError(f"Feishu request failed: {exc}") from exc
            time.sleep(1 + attempt)
    else:
        raise FeishuError(f"Feishu request failed: {last_error}")

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeishuError(f"Feishu returned non-JSON response: {raw[:800]}") from exc

    code = data.get("code", 0)
    if code not in (0, None):
        message = data.get("msg") or data.get("message") or "unknown error"
        raise FeishuError(f"Feishu API error {code}: {message}", api_code=api_code_from_data(data))
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


def create_document(token: str, title: str) -> tuple[str, str]:
    payload: dict[str, Any] = {"title": title}

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


def converted_blocks_payload(token: str, markdown: str) -> tuple[list[dict[str, Any]], list[str]]:
    data = request_json(
        "POST",
        "/docx/v1/documents/blocks/convert",
        token=token,
        payload={"content_type": "markdown", "content": markdown},
    )
    blocks = data.get("data", {}).get("blocks") or data.get("data", {}).get("children")
    first_level_block_ids = data.get("data", {}).get("first_level_block_ids") or []
    if not isinstance(blocks, list) or not blocks:
        raise FeishuError("Feishu Markdown converter returned no blocks.")
    if not isinstance(first_level_block_ids, list) or not first_level_block_ids:
        raise FeishuError("Feishu Markdown converter returned no first-level block IDs.")
    return [block for block in blocks if isinstance(block, dict)], [str(block_id) for block_id in first_level_block_ids]


def clean_converted_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = copy.deepcopy(blocks)
    for block in cleaned:
        block.pop("parent_id", None)
        if block.get("block_type") == 31 and isinstance(block.get("table"), dict):
            property_data = block["table"].get("property")
            if isinstance(property_data, dict):
                property_data.pop("merge_info", None)
    return cleaned


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


def append_markdown(token: str, document_id: str, markdown: str) -> None:
    blocks, first_level_block_ids = converted_blocks_payload(token, markdown)
    request_json(
        "POST",
        f"/docx/v1/documents/{urllib.parse.quote(document_id)}/blocks/"
        f"{urllib.parse.quote(document_id)}/descendant",
        token=token,
        payload={
            "children_id": first_level_block_ids,
            "descendants": clean_converted_blocks(blocks),
            "index": -1,
        },
    )


def publish(markdown: str, title: str) -> str:
    app_id, app_secret = feishu_config()
    token = get_tenant_access_token(app_id, app_secret)
    document_id, document_url = create_document(token, title)

    try:
        append_markdown(token, document_id, markdown)
    except FeishuError:
        blocks = markdown_to_basic_blocks(markdown)
        append_blocks(token, document_id, blocks)

    return document_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a Markdown study note to Feishu Docx.")
    parser.add_argument("--input", "-i", help="Markdown input file. Omit or pass '-' to read stdin.")
    parser.add_argument("--title", "-t", help="Feishu document title.")
    args = parser.parse_args()

    try:
        if not args.title:
            parser.error("--title is required")
        markdown = read_markdown(args.input)
        url = publish(markdown, args.title)
        delete_published_markdown(args.input)
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
