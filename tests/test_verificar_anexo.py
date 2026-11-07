"""Synthetic tests for read-only verification of the selected browser attachment."""

import hashlib
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bot" / "verificar_anexo.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verificar_anexo", SCRIPT)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(VERIFIER)

URL = "https://jobs.example.invalid/application/123"
SELECTOR = "input[type=file][name=resume]"
EXPECTED = hashlib.sha256(b"synthetic approved PDF").hexdigest()


class FakeSocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeChrome:
    def __init__(self, frame_results=None, pages=None, failure=None):
        self.frame_results = frame_results or {}
        self._pages = pages if pages is not None else {"target-1": {"url": URL}}
        self.failure = failure
        self.calls = []
        self.socket = FakeSocket()
        self.ws = self.socket

    def pages(self):
        return self._pages

    def anexar(self, target_id):
        assert target_id == "target-1"
        return "session-1"

    def call(self, method, params=None, session_id=None):
        self.calls.append((method, params or {}, session_id))
        if method == "Page.getFrameTree":
            return {
                "frameTree": {
                    "frame": {"id": "main"},
                    "childFrames": [{"frame": {"id": "iframe"}, "childFrames": []}],
                }
            }
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": f"context-{params['frameId']}"}
        if method == "Runtime.evaluate":
            if self.failure == "evaluate":
                return {"exceptionDetails": {"text": "synthetic error"}}
            frame_id = params["contextId"].removeprefix("context-")
            value = self.frame_results.get(frame_id, {"status": "NO_INPUT", "input_count": 0, "selected_file_count": 0, "files": []})
            return {"result": {"value": value}}
        return {}


def _observe(sha256=EXPECTED, *, input_count=1, selected_count=1):
    return {
        "status": "OBSERVED",
        "input_count": input_count,
        "selected_file_count": selected_count,
        "files": [{"sha256": sha256, "size": 128}],
    }


def test_approved_pdf_hash_is_found_in_an_iframe_without_mutating_the_page():
    chrome = FakeChrome(frame_results={"main": {"status": "NO_INPUT"}, "iframe": _observe()})

    result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: chrome)

    assert result["status"] == "APPROVED"
    assert result["input_count"] == 1
    assert result["selected_file_count"] == 1
    assert result["matching_file_count"] == 1
    assert result["selected_sha256"] == EXPECTED
    methods = [method for method, _params, _session in chrome.calls]
    assert "Target.detachFromTarget" in methods
    assert "Target.closeTarget" not in methods
    assert all(method in {
        "Target.getTargets", "Target.attachToTarget", "Page.enable", "Page.getFrameTree",
        "Page.createIsolatedWorld", "Runtime.evaluate", "Target.detachFromTarget",
    } for method in methods)
    assert chrome.socket.closed


def test_wrong_file_hash_is_rejected():
    wrong = hashlib.sha256(b"different synthetic PDF").hexdigest()
    chrome = FakeChrome(frame_results={"main": _observe(wrong), "iframe": {"status": "NO_INPUT"}})

    result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: chrome)

    assert result["status"] == "REJECTED"
    assert result["error_code"] == "SELECTED_FILE_HASH_MISMATCH"
    assert result["matching_file_count"] == 0


def test_multiple_file_inputs_or_selected_files_require_review():
    chrome = FakeChrome(frame_results={"main": _observe(input_count=2), "iframe": {"status": "NO_INPUT"}})

    result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: chrome)

    assert result["status"] == "NEEDS_REVIEW"
    assert result["error_code"] == "MULTIPLE_INPUTS_OR_FILES"


def test_no_selected_file_and_ambiguous_tabs_never_approve():
    empty = FakeChrome(frame_results={"main": {"status": "NO_FILE_SELECTED", "input_count": 1}})
    empty_result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: empty)
    assert empty_result["status"] == "NEEDS_REVIEW"

    ambiguous = FakeChrome(pages={"one": {"url": URL}, "two": {"url": URL + "?step=2"}})
    ambiguous_result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: ambiguous)
    assert ambiguous_result["status"] == "NEEDS_REVIEW"
    assert ambiguous_result["error_code"] == "BROWSER_TAB_AMBIGUOUS"


def test_unavailable_frame_or_browser_exception_is_unverifiable():
    broken = FakeChrome(failure="evaluate")
    result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: broken)
    assert result["status"] == "UNVERIFIABLE"
    assert result["error_code"] == "BROWSER_EVALUATION_FAILED"


def test_bad_request_is_rejected_before_connecting_to_chrome():
    connected = False

    def factory():
        nonlocal connected
        connected = True
        raise AssertionError("browser should not be opened for invalid input")

    result = VERIFIER.verify_selected_attachment(URL, SELECTOR, "not-a-hash", chrome_factory=factory)

    assert result == {"status": "UNVERIFIABLE", "error_code": "INVALID_EXPECTED_HASH"}
    assert not connected


def test_url_prefix_matches_origin_and_path_boundaries_without_query_parameters():
    assert VERIFIER._url_matches(URL + "/step?flow=2", URL)
    assert not VERIFIER._url_matches(URL + "-other", URL)
    assert not VERIFIER._url_matches("https://jobs.example.invalid.evil/application/123", URL)
    assert VERIFIER._validate_request(URL + "?token=synthetic", SELECTOR, EXPECTED) == "INVALID_URL_PREFIX"


def test_selector_is_encoded_as_data_and_result_contains_no_file_name_or_content():
    selector = 'input[type=file][data-test="x]; fetch(\'https://example.invalid\')"]'
    expression = VERIFIER._expression(selector)
    selector_declaration = f"const selector = {json.dumps(selector, ensure_ascii=False)};\n  let inputs;"
    assert selector_declaration in expression
    assert "file.arrayBuffer()" in expression
    assert 'crypto.subtle.digest("SHA-256"' in expression
    assert expression.count("fetch(") == selector.count("fetch(")

    chrome = FakeChrome(frame_results={"main": _observe(), "iframe": {"status": "NO_INPUT"}})
    result = VERIFIER.verify_selected_attachment(URL, SELECTOR, EXPECTED, chrome_factory=lambda: chrome)
    encoded = json.dumps(result)
    assert "synthetic approved PDF" not in encoded
    assert "resume.pdf" not in encoded
