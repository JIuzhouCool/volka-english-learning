#!/usr/bin/env python3
"""Publish a Markdown study note to a Feishu/Lark Docx document.

Configuration:
- FEISHU_APP_ID and FEISHU_APP_SECRET are required for OAuth.
- Run --auth-url and --auth-code once to save a user token.
- FEISHU_FOLDER_TOKEN is optional; omit it to create in the user's default space.

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
FEISHU_AUTH_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
NOT_CONFIGURED_MESSAGE = "FEISHU_NOT_CONFIGURED"
DEFAULT_OAUTH_SCOPE = "docx:document offline_access"
TOKEN_EXPIRY_SKEW_SECONDS = 300


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


def state_file_path() -> Path:
    configured = os.environ.get("YOUTUBE_ENGLISH_FEISHU_STATE_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()

    codex_home = os.environ.get("CODEX_HOME", "").strip()
    base_dir = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return base_dir / "youtube-english-learning" / "feishu_state.json"


def load_state() -> dict[str, Any]:
    path = state_file_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(data: dict[str, Any]) -> None:
    path = state_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_state() -> None:
    try:
        state_file_path().unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


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


def feishu_config() -> tuple[str, str, str]:
    app_id = config_value("FEISHU_APP_ID")
    app_secret = config_value("FEISHU_APP_SECRET")
    folder_token = config_value("FEISHU_FOLDER_TOKEN")
    if not app_id or not app_secret:
        raise FeishuError(NOT_CONFIGURED_MESSAGE)
    return app_id, app_secret, folder_token


def authorization_url(redirect_uri: str, state: str = "") -> str:
    app_id, _, _ = feishu_config()
    scope = config_value("FEISHU_OAUTH_SCOPE") or DEFAULT_OAUTH_SCOPE
    query = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
    }
    if state:
        query["state"] = state
    return f"{FEISHU_AUTH_URL}?{urllib.parse.urlencode(query)}"


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


def oauth_payload(app_id: str, app_secret: str, grant_type: str, **values: str) -> dict[str, str]:
    payload = {
        "grant_type": grant_type,
        "client_id": app_id,
        "client_secret": app_secret,
    }
    payload.update({key: value for key, value in values.items() if value})
    return payload


def save_user_tokens(data: dict[str, Any]) -> dict[str, Any]:
    token_data = data.get("data", data)
    access_token = token_data.get("access_token") or token_data.get("user_access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token or not refresh_token:
        raise FeishuError(f"Feishu OAuth response did not include user tokens: {data}")

    now = int(time.time())
    state = load_state()
    state.update(
        {
            "user_access_token": str(access_token),
            "refresh_token": str(refresh_token),
            "expires_at": now + int(token_data.get("expires_in") or 0),
            "refresh_expires_at": now + int(token_data.get("refresh_expires_in") or 0),
        }
    )
    save_state(state)
    return state


def exchange_auth_code(code: str) -> dict[str, Any]:
    app_id, app_secret, _ = feishu_config()
    data = request_json(
        "POST",
        "/authen/v2/oauth/token",
        payload=oauth_payload(app_id, app_secret, "authorization_code", code=code),
    )
    return save_user_tokens(data)


def refresh_user_token(refresh_token: str) -> dict[str, Any]:
    app_id, app_secret, _ = feishu_config()
    data = request_json(
        "POST",
        "/authen/v2/oauth/token",
        payload=oauth_payload(app_id, app_secret, "refresh_token", refresh_token=refresh_token),
    )
    return save_user_tokens(data)


def user_access_token() -> str:
    state = load_state()
    access_token = str(state.get("user_access_token") or "").strip()
    refresh_token = str(state.get("refresh_token") or "").strip()
    expires_at = int(state.get("expires_at") or 0)
    if not access_token or not refresh_token:
        raise FeishuError(NOT_CONFIGURED_MESSAGE)
    if expires_at and expires_at - TOKEN_EXPIRY_SKEW_SECONDS <= int(time.time()):
        access_token = str(refresh_user_token(refresh_token).get("user_access_token") or "").strip()
    if not access_token:
        raise FeishuError(NOT_CONFIGURED_MESSAGE)
    return access_token


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
    _, _, folder_token = feishu_config()
    token = user_access_token()
    document_id, document_url = create_document(token, title, folder_token)

    try:
        append_markdown(token, document_id, markdown)
    except FeishuError:
        blocks = markdown_to_basic_blocks(markdown)
        append_blocks(token, document_id, blocks)

    return document_url


def current_feishu_location() -> dict[str, str]:
    _, _, folder_token = feishu_config()
    return {
        "space": "user",
        "folder_token": folder_token or "",
        "folder_url": f"https://feishu.cn/drive/folder/{folder_token}" if folder_token else "",
        "state_file": str(state_file_path()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a Markdown study note to Feishu Docx.")
    parser.add_argument("--input", "-i", help="Markdown input file. Omit or pass '-' to read stdin.")
    parser.add_argument("--title", "-t", help="Feishu document title.")
    parser.add_argument("--auth-url", metavar="REDIRECT_URI", help="Print the Feishu OAuth URL and exit.")
    parser.add_argument("--auth-state", default="", help="Optional OAuth state value for --auth-url.")
    parser.add_argument("--auth-code", metavar="CODE", help="Exchange a Feishu OAuth code and save user tokens.")
    parser.add_argument("--clear-auth", action="store_true", help="Delete saved Feishu user tokens and exit.")
    parser.add_argument("--print-location", action="store_true", help="Print the Feishu user-space target and exit.")
    args = parser.parse_args(argv)

    try:
        if args.clear_auth:
            clear_state()
            print("FEISHU_AUTH_CLEARED")
            return 0
        if args.auth_url:
            print(authorization_url(args.auth_url, args.auth_state))
            return 0
        if args.auth_code:
            exchange_auth_code(args.auth_code)
            print("FEISHU_AUTH_SAVED")
            return 0
        if args.print_location:
            print(json.dumps(current_feishu_location(), ensure_ascii=False, indent=2))
            return 0
        if not args.title:
            parser.error("--title is required unless --print-location is used")
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
