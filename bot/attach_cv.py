#!/usr/bin/env python3
"""Select one freshly approved CV in the unique application tab, without submitting."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

import cv_intent_gate
import verificar_anexo

MAX_PDF_BYTES = cv_intent_gate.MAX_PDF_BYTES
MAX_ANNOUNCEMENT_BYTES = cv_intent_gate.MAX_ANNOUNCEMENT_BYTES
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class AttachCvError(ValueError):
    def __init__(self, status: str, error_code: str):
        super().__init__(error_code)
        self.status = status
        self.error_code = error_code


def _json_records(stdout: str) -> list[dict[str, Any]]:
    records = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "status" in value:
            records.append(value)
    return records


def _safe_env() -> dict[str, str]:
    allowed = {
        "PATH", "HOME", "LANG", "LC_ALL", "CV_BASE_FILE", "DADOS_CANDIDATO_FILE", "BOT_ROOT",
        "OV_ATS_LOG", "OV_RESUME_MATCHER_BRIDGE", "OV_RESUME_MATCHER_CLI",
        "OV_RESUME_MATCHER_REVISION", "OV_RESUME_MATCHER_BACKEND_DIR",
        "OV_RESUME_MATCHER_DATA_DIR", "OV_RESUME_MATCHER_MANIFEST_DIR", "OV_RESUME_MATCHER_LOG",
        "CDP_URL",
    }
    return cv_intent_gate._safe_environment(allowed)


def run_cv_approval_gate(
    announcement: Path,
    attachment: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Run the existing ATS and Resume-Matcher gate with matching input hashes."""
    gate = Path(__file__).resolve().with_name("cv-pronto.sh")
    if not gate.is_file() or not os.access(gate, os.X_OK):
        raise AttachCvError("UNVERIFIABLE", "CV_APPROVAL_GATE_UNAVAILABLE")

    try:
        _resolved_job, job_sha = cv_intent_gate._hash_regular_file(
            str(announcement), "Job description", MAX_ANNOUNCEMENT_BYTES
        )
        _resolved_pdf, pdf_sha = cv_intent_gate._hash_regular_file(
            str(attachment), "CV attachment", MAX_PDF_BYTES
        )
        with attachment.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise AttachCvError("REJECTED", "ATTACHMENT_NOT_PDF")
    except AttachCvError:
        raise
    except OSError as exc:
        raise AttachCvError("UNVERIFIABLE", "APPROVED_ARTIFACT_UNAVAILABLE") from exc
    except ValueError as exc:
        raise AttachCvError("UNVERIFIABLE", "APPROVED_ARTIFACT_UNAVAILABLE") from exc

    env = _safe_env()
    env["OV_RESUME_MATCHER_REQUIRED"] = "1"
    try:
        result = runner(
            [str(gate), str(announcement), str(attachment)],
            cwd=str(Path(__file__).resolve().parent),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=cv_intent_gate.GATE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise AttachCvError("UNVERIFIABLE", "CV_APPROVAL_GATE_TIMEOUT") from None
    except OSError:
        raise AttachCvError("UNVERIFIABLE", "CV_APPROVAL_GATE_FAILED_TO_START") from None

    records = _json_records(result.stdout or "")
    attach_lines = [line[7:] for line in (result.stdout or "").splitlines() if line.startswith("ANEXAR ")]
    if result.returncode != 0 or len(records) != 1 or attach_lines != [str(attachment)]:
        status = records[0].get("status") if len(records) == 1 else "UNVERIFIABLE"
        if status not in {"REJECTED", "NEEDS_REVIEW", "UNVERIFIABLE"}:
            status = "UNVERIFIABLE"
        raise AttachCvError(status, "CV_APPROVAL_GATE_DID_NOT_APPROVE")

    record = records[0]
    if (
        record.get("status") != "APPROVED"
        or record.get("manifest_verified") is not True
        or record.get("job_description_sha256") != job_sha
        or record.get("pdf_sha256") != pdf_sha
        or record.get("sha256") != pdf_sha
        or record.get("manifest_id") != f"{job_sha}-{pdf_sha}"
        or not isinstance(record.get("resume_matcher_revision"), str)
        or REVISION_RE.fullmatch(record.get("resume_matcher_revision", "")) is None
        or isinstance(record.get("verifier_policy_version"), bool)
        or not isinstance(record.get("verifier_policy_version"), int)
        or record.get("verifier_policy_version") < 1
        or not isinstance(record.get("verified_at"), str)
        or not record.get("verified_at")
    ):
        raise AttachCvError("UNVERIFIABLE", "CV_APPROVAL_GATE_RESULT_INVALID")

    try:
        _resolved_job_after, job_sha_after = cv_intent_gate._hash_regular_file(
            str(announcement), "Job description", MAX_ANNOUNCEMENT_BYTES
        )
        _resolved_pdf_after, pdf_sha_after = cv_intent_gate._hash_regular_file(
            str(attachment), "CV attachment", MAX_PDF_BYTES
        )
    except ValueError as exc:
        raise AttachCvError("UNVERIFIABLE", "APPROVED_ARTIFACT_CHANGED") from exc
    if job_sha_after != job_sha or pdf_sha_after != pdf_sha:
        raise AttachCvError("UNVERIFIABLE", "APPROVED_ARTIFACT_CHANGED")
    return record


def _collect_documents(node: Any, output: list[int]) -> None:
    if not isinstance(node, dict):
        return
    if node.get("nodeType") == 9 and isinstance(node.get("nodeId"), int):
        if node["nodeId"] not in output:
            output.append(node["nodeId"])
    content_document = node.get("contentDocument")
    if isinstance(content_document, dict):
        _collect_documents(content_document, output)
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            _collect_documents(child, output)


def _find_unique_input(chrome: Any, session_id: str, selector: str) -> int:
    document = chrome.call("DOM.getDocument", {"depth": -1, "pierce": True}, session_id)
    root = document.get("root") if isinstance(document, dict) else None
    document_ids: list[int] = []
    _collect_documents(root, document_ids)
    if not document_ids or len(document_ids) > verificar_anexo.MAX_FRAME_COUNT:
        raise AttachCvError("UNVERIFIABLE", "BROWSER_DOCUMENTS_UNAVAILABLE")

    matches: list[int] = []
    for document_id in document_ids:
        result = chrome.call(
            "DOM.querySelectorAll", {"nodeId": document_id, "selector": selector}, session_id
        )
        node_ids = result.get("nodeIds") if isinstance(result, dict) else None
        if not isinstance(node_ids, list):
            raise AttachCvError("UNVERIFIABLE", "SELECTOR_QUERY_FAILED")
        for node_id in node_ids:
            if not isinstance(node_id, int) or node_id <= 0:
                raise AttachCvError("UNVERIFIABLE", "SELECTOR_RESULT_INVALID")
            description = chrome.call("DOM.describeNode", {"nodeId": node_id}, session_id)
            node = description.get("node") if isinstance(description, dict) else None
            attributes = node.get("attributes") if isinstance(node, dict) else None
            values = dict(zip(attributes[::2], attributes[1::2])) if isinstance(attributes, list) else {}
            if (
                not isinstance(node, dict)
                or node.get("nodeName", "").casefold() != "input"
                or values.get("type", "text").casefold() != "file"
            ):
                raise AttachCvError("NEEDS_REVIEW", "SELECTOR_NOT_FILE_INPUT")
            if "disabled" in values:
                raise AttachCvError("NEEDS_REVIEW", "FILE_INPUT_DISABLED")
            matches.append(node_id)
    if not matches:
        raise AttachCvError("NEEDS_REVIEW", "FILE_INPUT_NOT_FOUND")
    if len(matches) != 1:
        raise AttachCvError("NEEDS_REVIEW", "FILE_INPUT_AMBIGUOUS")
    return matches[0]


def _select_in_browser(
    *,
    url_prefix: str,
    selector: str,
    attachment: Path,
    expected_sha256: str,
    chrome_factory: Callable[[], Any],
    verify_func: Callable[[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    invalid = verificar_anexo._validate_request(url_prefix, selector, expected_sha256)
    if invalid:
        raise AttachCvError("UNVERIFIABLE", invalid)

    before = verify_func(url_prefix, selector, expected_sha256)
    if before.get("status") == "APPROVED" and before.get("selected_sha256") == expected_sha256:
        return {"selection": "ALREADY_SELECTED", "browser_check": before}
    if before.get("status") != "NEEDS_REVIEW" or before.get("error_code") != "NO_SELECTED_FILE":
        status = before.get("status")
        if status not in {"REJECTED", "NEEDS_REVIEW", "UNVERIFIABLE"}:
            status = "UNVERIFIABLE"
        raise AttachCvError(status, before.get("error_code", "ATTACHMENT_PREFLIGHT_FAILED"))

    chrome = None
    session_id = None
    try:
        chrome = chrome_factory()
        pages = chrome.pages()
        matching = [
            (target_id, page)
            for target_id, page in pages.items()
            if isinstance(page, dict)
            and isinstance(page.get("url"), str)
            and verificar_anexo._url_matches(page["url"], url_prefix)
        ]
        if not matching:
            raise AttachCvError("UNVERIFIABLE", "BROWSER_TAB_NOT_FOUND")
        if len(matching) != 1:
            raise AttachCvError("NEEDS_REVIEW", "BROWSER_TAB_AMBIGUOUS")

        target_id, _page = matching[0]
        session_id = chrome.anexar(target_id)
        chrome.call("DOM.enable", {}, session_id)
        node_id = _find_unique_input(chrome, session_id, selector)
        chrome.call(
            "DOM.setFileInputFiles",
            {"files": [str(attachment)], "nodeId": node_id},
            session_id,
        )
    except AttachCvError:
        raise
    except Exception:
        raise AttachCvError("UNVERIFIABLE", "BROWSER_SELECTION_FAILED") from None
    finally:
        if chrome is not None:
            if session_id:
                try:
                    chrome.call("Target.detachFromTarget", {"sessionId": session_id})
                except Exception:
                    pass
            socket = getattr(chrome, "ws", None)
            close = getattr(socket, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    after = verify_func(url_prefix, selector, expected_sha256)
    if after.get("status") != "APPROVED" or after.get("selected_sha256") != expected_sha256:
        status = after.get("status")
        if status not in {"REJECTED", "NEEDS_REVIEW", "UNVERIFIABLE"}:
            status = "UNVERIFIABLE"
        raise AttachCvError(status, after.get("error_code", "ATTACHMENT_POSTCHECK_FAILED"))
    return {"selection": "SELECTED_AND_HASH_VERIFIED", "browser_check": after}


def _load_chrome() -> Any:
    try:
        import cdp
    except ImportError as exc:
        raise AttachCvError("UNVERIFIABLE", "CDP_CLIENT_UNAVAILABLE") from exc
    return cdp.Chrome()


def _validate_identity(application_key: str, company: str, title: str) -> None:
    if not isinstance(application_key, str) or cv_intent_gate.JOB_KEY_RE.fullmatch(application_key) is None:
        raise AttachCvError("NEEDS_REVIEW", "INVALID_APPLICATION_KEY")
    for value, error_code in ((company, "INVALID_COMPANY"), (title, "INVALID_TITLE")):
        if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value):
            raise AttachCvError("NEEDS_REVIEW", error_code)


def attach_cv(
    *,
    announcement_path: str,
    attachment_path: str,
    application_key: str,
    company: str,
    title: str,
    url_prefix: str,
    selector: str,
    requirements_profile_path: str,
    requirements_assessment_path: str,
    requirements_receipt_path: str,
    content_cv_base_path: str,
    content_candidate_data_path: str,
    content_proposal_path: str,
    content_assessment_path: str,
    content_receipt_path: str,
    approval_runner: Callable[..., Any] = subprocess.run,
    chrome_factory: Callable[[], Any] | None = None,
    verify_func: Callable[[str, str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _validate_identity(application_key, company, title)

    try:
        announcement, _job_sha = cv_intent_gate._hash_regular_file(
            announcement_path, "Job description", MAX_ANNOUNCEMENT_BYTES
        )
        attachment, pdf_sha = cv_intent_gate._hash_regular_file(
            attachment_path, "CV attachment", MAX_PDF_BYTES
        )
        with attachment.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise AttachCvError("REJECTED", "ATTACHMENT_NOT_PDF")
    except AttachCvError:
        raise
    except ValueError as exc:
        raise AttachCvError("UNVERIFIABLE", "APPROVED_ARTIFACT_UNAVAILABLE") from exc
    requirement_info = {
        cv_intent_gate.REQUIREMENT_REVIEW_PATH_FIELDS[0]: requirements_profile_path,
        cv_intent_gate.REQUIREMENT_REVIEW_PATH_FIELDS[1]: requirements_assessment_path,
        cv_intent_gate.REQUIREMENT_REVIEW_PATH_FIELDS[2]: requirements_receipt_path,
    }
    requirement_audit, requirement_error = cv_intent_gate._verify_requirement_review(
        requirement_info, announcement, title, _job_sha,
    )
    if requirement_audit is None:
        status = "UNVERIFIABLE"
        if "returned REJECTED" in requirement_error:
            status = "REJECTED"
        elif "returned NEEDS_REVIEW" in requirement_error or "are required" in requirement_error:
            status = "NEEDS_REVIEW"
        raise AttachCvError(status, "JOB_REQUIREMENT_REVIEW_BLOCKED")
    content_info = {
        field: value
        for field, value in zip(
            cv_intent_gate.CONTENT_REVIEW_PATH_FIELDS,
            (
                content_cv_base_path,
                content_candidate_data_path,
                content_proposal_path,
                content_assessment_path,
                content_receipt_path,
            ),
        )
    }
    content_audit, content_error = cv_intent_gate._verify_content_review(
        content_info, announcement, attachment, _job_sha, pdf_sha,
    )
    if content_audit is None:
        status = "NEEDS_REVIEW" if "returned NEEDS_REVIEW" in content_error or "are required" in content_error else "UNVERIFIABLE"
        if "returned REJECTED" in content_error:
            status = "REJECTED"
        raise AttachCvError(status, "CV_CONTENT_REVIEW_BLOCKED")
    invalid = verificar_anexo._validate_request(url_prefix, selector, pdf_sha)
    if invalid:
        raise AttachCvError("UNVERIFIABLE", invalid)

    approval = run_cv_approval_gate(announcement, attachment, runner=approval_runner)
    content_audit_after, content_error_after = cv_intent_gate._verify_content_review(
        content_info, announcement, attachment, _job_sha, pdf_sha,
    )
    if content_audit_after is None or content_audit_after != content_audit:
        status = "NEEDS_REVIEW" if "returned NEEDS_REVIEW" in content_error_after else "UNVERIFIABLE"
        if "returned REJECTED" in content_error_after:
            status = "REJECTED"
        raise AttachCvError(status, "CV_CONTENT_REVIEW_CHANGED")
    verifier = verify_func or verificar_anexo.verify_selected_attachment
    selection = _select_in_browser(
        url_prefix=url_prefix,
        selector=selector,
        attachment=attachment,
        expected_sha256=pdf_sha,
        chrome_factory=chrome_factory or _load_chrome,
        verify_func=verifier,
    )
    browser_check = selection["browser_check"]
    return {
        "status": "APPROVED",
        "selection": selection["selection"],
        "cv_manifest_id": approval["manifest_id"],
        "cv_job_sha256": approval["job_description_sha256"],
        "cv_pdf_sha256": approval["pdf_sha256"],
        "cv_job_key": application_key,
        "cv_job_company": company,
        "cv_job_title": title,
        "cv_announcement_path": str(announcement),
        "cv_attachment_path": str(attachment),
        "cv_browser_url_prefix": url_prefix,
        "cv_browser_input_selector": selector,
        **requirement_info,
        **requirement_audit,
        **content_info,
        **content_audit,
        "selected_sha256": browser_check["selected_sha256"],
        "verified_at": browser_check["verified_at"],
        "submit_clicked": False,
        "upload_may_have_started": selection["selection"] == "SELECTED_AND_HASH_VERIFIED",
        "portal_receipt_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--announcement", required=True, help="absolute path to the exact job description")
    parser.add_argument("--pdf", required=True, help="absolute path to the CV approved for this description")
    parser.add_argument("--application-key", required=True, help="stable key used by estado.py")
    parser.add_argument("--company", required=True, help="official company name for the application")
    parser.add_argument("--title", required=True, help="official job title for the application")
    parser.add_argument("--url-prefix", required=True, help="unique path prefix of the open application tab")
    parser.add_argument("--selector", required=True, help="CSS selector for exactly one input[type=file]")
    parser.add_argument("--requirements-profile", required=True, help="absolute private ResumeData used by the review")
    parser.add_argument("--requirements-assessment", required=True, help="absolute private typed assessment")
    parser.add_argument("--requirements-receipt", required=True, help="absolute private receipt paired with the assessment")
    parser.add_argument("--content-cv-base", required=True, help="absolute current CV master used as factual evidence")
    parser.add_argument("--content-candidate-data", required=True, help="absolute structured candidate source used as factual evidence")
    parser.add_argument("--content-proposal", required=True, help="absolute hash-bound textual claim proposal")
    parser.add_argument("--content-assessment", required=True, help="absolute reviewed claim assessment")
    parser.add_argument("--content-receipt", required=True, help="absolute receipt paired with the reviewed assessment")
    parser.add_argument("--select", action="store_true", help="select the approved file in the matched tab; never submits")
    args = parser.parse_args(argv)

    if not args.select:
        result = {
            "status": "NEEDS_REVIEW",
            "error_code": "EXPLICIT_SELECTION_REQUIRED",
            "submit_clicked": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1
    try:
        result = attach_cv(
            announcement_path=args.announcement,
            attachment_path=args.pdf,
            application_key=args.application_key,
            company=args.company,
            title=args.title,
            url_prefix=args.url_prefix,
            selector=args.selector,
            requirements_profile_path=args.requirements_profile,
            requirements_assessment_path=args.requirements_assessment,
            requirements_receipt_path=args.requirements_receipt,
            content_cv_base_path=args.content_cv_base,
            content_candidate_data_path=args.content_candidate_data,
            content_proposal_path=args.content_proposal,
            content_assessment_path=args.content_assessment,
            content_receipt_path=args.content_receipt,
        )
    except AttachCvError as exc:
        result = {"status": exc.status, "error_code": exc.error_code, "submit_clicked": False}
    except Exception:
        result = {"status": "UNVERIFIABLE", "error_code": "ATTACHMENT_SELECTION_FAILED", "submit_clicked": False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get("status") == "APPROVED":
        return 0
    if result.get("status") in {"REJECTED", "NEEDS_REVIEW"}:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
