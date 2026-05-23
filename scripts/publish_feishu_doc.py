#!/usr/bin/env python3
"""Publish Markdown to Feishu Docx."""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

FEISHU_BASE = "https://open.feishu.cn/open-apis"
NOT_CONFIGURED = "FEISHU_NOT_CONFIGURED"


class FeishuError(RuntimeError):
    pass


def get_config() -> tuple[str, str]:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise FeishuError(NOT_CONFIGURED)
    return app_id, app_secret


def request(method: str, path: str, token: str | None = None, payload: dict | None = None) -> dict:
    url = f"{FEISHU_BASE}{path}"
    data = json.dumps(payload or {}, ensure_ascii=False).encode() if payload else None
    headers = {"accept": "application/json", "content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        resp = json.loads(e.read().decode())

    if resp.get("code", 0) not in (0, None):
        raise FeishuError(resp.get("msg", "API error"))
    return resp


def get_token(app_id: str, app_secret: str) -> str:
    resp = request("POST", "/auth/v3/tenant_access_token/internal",
                   payload={"app_id": app_id, "app_secret": app_secret})
    return resp["data"]["tenant_access_token"]


def create_doc(token: str, title: str) -> tuple[str, str]:
    resp = request("POST", "/docx/v1/documents", token, {"title": title})
    doc = resp["data"]["document"]
    return doc["document_id"], doc.get("url") or f"https://feishu.cn/docx/{doc['document_id']}"


def append_md(token: str, doc_id: str, content: str) -> None:
    blocks = request("POST", f"/docx/v1/documents/blocks/convert", token,
                     {"content_type": "markdown", "content": content})
    request("POST", f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/descendant", token,
            {"children_id": blocks["data"]["first_level_block_ids"],
             "descendants": blocks["data"]["blocks"], "index": -1})


def publish(content: str, title: str) -> str:
    app_id, app_secret = get_config()
    token = get_token(app_id, app_secret)
    doc_id, url = create_doc(token, title)
    append_md(token, doc_id, content)
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Markdown to Feishu")
    parser.add_argument("-i", "--input", help="Input file (default: stdin)")
    parser.add_argument("-t", "--title", required=True, help="Document title")
    args = parser.parse_args()

    content = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()

    try:
        url = publish(content, args.title)
        print(url)
        if args.input:
            Path(args.input).unlink()
    except FeishuError as e:
        if str(e) == NOT_CONFIGURED:
            print(NOT_CONFIGURED, file=sys.stderr)
            return 2
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
