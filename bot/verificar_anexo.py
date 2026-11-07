#!/usr/bin/env python3
"""Read-only verification that a browser file input contains the approved CV bytes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Callable

MAX_SELECTOR_CHARS = 512
MAX_SELECTED_FILE_BYTES = 4 * 1024 * 1024
MAX_FRAME_COUNT = 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_STATUSES = {"APPROVED", "REJECTED", "NEEDS_REVIEW", "UNVERIFIABLE"}


def _validate_request(url_prefix: str, selector: str, expected_sha256: str) -> str | None:
    if not isinstance(url_prefix, str) or len(url_prefix) > 2048:
        return "INVALID_URL_PREFIX"
    try:
        parsed = urlsplit(url_prefix)
        parsed.port
    except ValueError:
        return "INVALID_URL_PREFIX"
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return "INVALID_URL_PREFIX"
    if not isinstance(selector, str) or not selector.strip() or len(selector) > MAX_SELECTOR_CHARS:
        return "INVALID_SELECTOR"
    if any(ord(char) < 32 for char in selector):
        return "INVALID_SELECTOR"
    if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
        return "INVALID_EXPECTED_HASH"
    return None


def _expression(selector: str) -> str:
    selector_literal = json.dumps(selector, ensure_ascii=False)
    return f"""(async () => {{
  const selector = {selector_literal};
  let inputs;
  try {{ inputs = Array.from(document.querySelectorAll(selector)); }}
  catch (_) {{ return {{status: "UNVERIFIABLE", error_code: "INVALID_SELECTOR"}}; }}
  if (inputs.length === 0) return {{status: "NO_INPUT", input_count: 0, selected_file_count: 0, files: []}};
  if (inputs.some(input => !(input instanceof HTMLInputElement) || input.type !== "file")) {{
    return {{status: "UNVERIFIABLE", error_code: "SELECTOR_NOT_FILE_INPUT"}};
  }}
  const files = inputs.flatMap(input => Array.from(input.files || []));
  if (files.some(file => file.size > {MAX_SELECTED_FILE_BYTES})) {{
    return {{status: "UNVERIFIABLE", error_code: "SELECTED_FILE_TOO_LARGE"}};
  }}
  if (files.length === 0) {{
    return {{status: "NO_FILE_SELECTED", input_count: inputs.length, selected_file_count: 0, files: []}};
  }}
  if (!globalThis.crypto || !crypto.subtle || typeof crypto.subtle.digest !== "function") {{
    return {{status: "UNVERIFIABLE", error_code: "WEB_CRYPTO_UNAVAILABLE"}};
  }}
  try {{
    const observed = [];
    for (const file of files) {{
      const bytes = await file.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const sha256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
      observed.push({{sha256, size: file.size}});
    }}
    return {{status: "OBSERVED", input_count: inputs.length, selected_file_count: files.length, files: observed}};
  }} catch (_) {{
    return {{status: "UNVERIFIABLE", error_code: "FILE_HASH_FAILED"}};
  }}
}})()"""


def _frame_ids(frame_tree: dict[str, Any]) -> list[str]:
    root = frame_tree.get("frameTree")
    if not isinstance(root, dict):
        return []
    result: list[str] = []
    stack = [root]
    while stack:
        node = stack.pop()
        frame = node.get("frame")
        frame_id = frame.get("id") if isinstance(frame, dict) else None
        if isinstance(frame_id, str) and frame_id not in result:
            result.append(frame_id)
        children = node.get("childFrames")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
        if len(result) > MAX_FRAME_COUNT:
            return []
    return result


def _url_matches(page_url: str, url_prefix: str) -> bool:
    try:
        page = urlsplit(page_url)
        prefix = urlsplit(url_prefix)
        page_port = page.port
        prefix_port = prefix.port
    except ValueError:
        return False
    if (
        page.scheme != prefix.scheme
        or (page.hostname or "").casefold() != (prefix.hostname or "").casefold()
        or (page_port or (443 if page.scheme == "https" else 80))
        != (prefix_port or (443 if prefix.scheme == "https" else 80))
        or page.username
        or page.password
    ):
        return False
    prefix_path = prefix.path or "/"
    page_path = page.path or "/"
    return page_path == prefix_path or page_path.startswith(
        prefix_path if prefix_path.endswith("/") else prefix_path + "/"
    )


def _evaluate_frame(chrome: Any, session_id: str, frame_id: str, expression: str) -> dict[str, Any]:
    world = chrome.call(
        "Page.createIsolatedWorld",
        {"frameId": frame_id, "worldName": "resume-attachment-verification"},
        session_id,
    )
    context_id = world.get("executionContextId") if isinstance(world, dict) else None
    if not context_id:
        return {"status": "UNVERIFIABLE", "error_code": "ISOLATED_WORLD_UNAVAILABLE"}
    response = chrome.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "contextId": context_id,
            "awaitPromise": True,
            "returnByValue": True,
        },
        session_id,
    )
    if not isinstance(response, dict) or response.get("exceptionDetails"):
        return {"status": "UNVERIFIABLE", "error_code": "BROWSER_EVALUATION_FAILED"}
    remote = response.get("result")
    value = remote.get("value") if isinstance(remote, dict) else None
    if not isinstance(value, dict) or value.get("status") not in {
        "OBSERVED", "NO_INPUT", "NO_FILE_SELECTED", "UNVERIFIABLE"
    }:
        return {"status": "UNVERIFIABLE", "error_code": "BROWSER_RESULT_INVALID"}
    return value


def _new_chrome() -> Any:
    bot_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(bot_dir))
    import cdp

    return cdp.Chrome()


def verify_selected_attachment(
    url_prefix: str,
    selector: str,
    expected_sha256: str,
    chrome_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Compare one selected browser File object's bytes with a previously approved PDF hash.

    The caller must coordinate access to the shared Chrome using the existing chrome-lock protocol.
    This function never changes file inputs, clicks, navigates, closes tabs, or submits forms.
    """
    invalid = _validate_request(url_prefix, selector, expected_sha256)
    if invalid:
        return {"status": "UNVERIFIABLE", "error_code": invalid}

    factory = chrome_factory or _new_chrome
    chrome = None
    session_id = None
    try:
        chrome = factory()
        pages = chrome.pages()
        matches = [
            (target_id, page)
            for target_id, page in pages.items()
            if isinstance(page, dict) and isinstance(page.get("url"), str) and _url_matches(page["url"], url_prefix)
        ]
        if not matches:
            return {"status": "UNVERIFIABLE", "error_code": "BROWSER_TAB_NOT_FOUND"}
        if len(matches) != 1:
            return {"status": "NEEDS_REVIEW", "error_code": "BROWSER_TAB_AMBIGUOUS"}

        target_id, _page = matches[0]
        session_id = chrome.anexar(target_id)
        chrome.call("Page.enable", {}, session_id)
        frame_tree = chrome.call("Page.getFrameTree", {}, session_id)
        frame_ids = _frame_ids(frame_tree if isinstance(frame_tree, dict) else {})
        if not frame_ids:
            return {"status": "UNVERIFIABLE", "error_code": "BROWSER_FRAMES_UNAVAILABLE"}

        expression = _expression(selector)
        observations = [_evaluate_frame(chrome, session_id, frame_id, expression) for frame_id in frame_ids]
        if any(item.get("status") == "UNVERIFIABLE" for item in observations):
            error = next(item.get("error_code") for item in observations if item.get("status") == "UNVERIFIABLE")
            return {"status": "UNVERIFIABLE", "error_code": error or "BROWSER_FRAME_UNVERIFIABLE"}

        input_count = sum(
            item.get("input_count", 0) for item in observations if item.get("status") in {"OBSERVED", "NO_FILE_SELECTED"}
        )
        files = [
            file
            for item in observations if item.get("status") == "OBSERVED"
            for file in item.get("files", []) if isinstance(file, dict)
        ]
        selected_count = sum(
            item.get("selected_file_count", 0) for item in observations if item.get("status") == "OBSERVED"
        )
        matching = [file for file in files if file.get("sha256") == expected_sha256]
        result = {
            "status": "NEEDS_REVIEW",
            "expected_sha256": expected_sha256,
            "selected_sha256": files[0].get("sha256") if len(files) == 1 else None,
            "input_count": input_count,
            "selected_file_count": selected_count,
            "matching_file_count": len(matching),
            "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if input_count == 0 or selected_count == 0:
            result.update(status="NEEDS_REVIEW", error_code="NO_SELECTED_FILE")
        elif input_count != 1 or selected_count != 1 or len(files) != 1:
            result.update(status="NEEDS_REVIEW", error_code="MULTIPLE_INPUTS_OR_FILES")
        elif len(matching) == 1:
            result.update(status="APPROVED", error_code=None)
        else:
            result.update(status="REJECTED", error_code="SELECTED_FILE_HASH_MISMATCH")
        return result
    except Exception:
        return {"status": "UNVERIFIABLE", "error_code": "BROWSER_INSPECTION_FAILED"}
    finally:
        if chrome is not None:
            if session_id:
                try:
                    chrome.call("Target.detachFromTarget", {"sessionId": session_id})
                except Exception:
                    pass
            socket = getattr(chrome, "ws", None)
            if socket is not None and callable(getattr(socket, "close", None)):
                try:
                    socket.close()
                except Exception:
                    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url-prefix", required=True, help="unique prefix of the form tab URL; never printed")
    parser.add_argument("--selector", required=True, help="CSS selector for the resume input[type=file]")
    parser.add_argument("--expected-sha256", required=True, help="pdf_sha256 from the matching APPROVED batch row")
    args = parser.parse_args(argv)
    result = verify_selected_attachment(args.url_prefix, args.selector, args.expected_sha256)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get("status") == "APPROVED":
        return 0
    if result.get("status") in {"REJECTED", "NEEDS_REVIEW"}:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
