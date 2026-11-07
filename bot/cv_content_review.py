#!/usr/bin/env python3
"""Create and verify a hash-bound human review of every textual claim in a CV PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_JOB_BYTES = 1024 * 1024
MAX_PDF_BYTES = 4 * 1024 * 1024
MAX_PROFILE_BYTES = 2 * 1024 * 1024
MAX_REVIEW_BYTES = 4 * 1024 * 1024
MAX_EXTRACTED_TEXT_BYTES = 1024 * 1024
MAX_CLAIMS = 1200
MAX_CLAIM_CHARS = 3000
MAX_EVIDENCE_REFS = 5000
MAX_EVIDENCE_PER_CLAIM = 50
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACKNOWLEDGEMENTS = (
    "factual_claims_checked",
    "employment_and_project_types_checked",
    "dates_and_metrics_checked",
    "identity_matches_job_checked",
    "visual_review_completed",
)
DECISIONS = {"SUPPORTED", "NON_FACTUAL", "UNSUPPORTED", "UNCONFIRMED"}


class ContentReviewError(Exception):
    def __init__(self, status: str, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _read_regular(path_value: str | Path, label: str, maximum: int) -> tuple[Path, bytes]:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_PATH_INVALID")
    try:
        resolved = path.resolve(strict=True)
        if resolved != path:
            raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_PATH_INVALID")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > maximum:
                raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_FILE_INVALID")
            if os.name == "posix" and info.st_uid != os.getuid():
                raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_FILE_OWNER_INVALID")
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_FILE_INVALID")
        return resolved, data
    except ContentReviewError:
        raise
    except OSError:
        raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_FILE_UNAVAILABLE") from None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return _sha256(_canonical(value))


def _run_pdf_text_extractor(pdf_bytes: bytes) -> bytes:
    try:
        with tempfile.TemporaryFile() as pdf_input:
            pdf_input.write(pdf_bytes)
            pdf_input.seek(0)
            process = subprocess.Popen(
                ["pdftotext", "-layout", "-", "-"],
                stdin=pdf_input,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": os.environ.get("HOME", str(Path.home())),
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
            )
            if process.stdout is None:
                process.kill()
                process.wait()
                raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_PIPE_UNAVAILABLE")

            extracted = bytearray()
            too_large = threading.Event()
            read_failed = threading.Event()

            def read_bounded_output() -> None:
                try:
                    while len(extracted) <= MAX_EXTRACTED_TEXT_BYTES:
                        remaining = MAX_EXTRACTED_TEXT_BYTES + 1 - len(extracted)
                        chunk = process.stdout.read(min(64 * 1024, remaining))
                        if not chunk:
                            return
                        extracted.extend(chunk)
                    too_large.set()
                except (OSError, ValueError):
                    read_failed.set()

            reader = threading.Thread(target=read_bounded_output, daemon=True)
            reader.start()
            deadline = time.monotonic() + 30
            try:
                while process.poll() is None:
                    if too_large.is_set():
                        process.kill()
                        process.wait()
                        raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_TOO_LARGE")
                    if time.monotonic() >= deadline:
                        process.kill()
                        process.wait()
                        raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_EXTRACTION_TIMEOUT")
                    time.sleep(0.05)
                reader.join(timeout=1)
                if process.returncode != 0:
                    raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_EXTRACTION_FAILED")
                if too_large.is_set() or len(extracted) > MAX_EXTRACTED_TEXT_BYTES:
                    raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_TOO_LARGE")
                if reader.is_alive() or read_failed.is_set():
                    raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_EXTRACTION_FAILED")
                return bytes(extracted)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
                reader.join(timeout=1)
    except OSError:
        raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_EXTRACTOR_UNAVAILABLE") from None


def _extract_pdf_claims(pdf_bytes: bytes) -> list[dict[str, str]]:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ContentReviewError("REJECTED", "ATTACHMENT_NOT_PDF")
    text_bytes = _run_pdf_text_extractor(pdf_bytes)
    if not text_bytes:
        raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_EXTRACTION_FAILED")
    try:
        text = text_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_ENCODING_INVALID") from None
    claims: list[dict[str, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = " ".join(raw_line.split())
        if not line:
            continue
        if len(line) > MAX_CLAIM_CHARS:
            raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_LINE_TOO_LARGE")
        claim_id = "c" + hashlib.sha256(f"{line_number}\0{line}".encode("utf-8")).hexdigest()[:20]
        claims.append({"id": claim_id, "text": line})
        if len(claims) > MAX_CLAIMS:
            raise ContentReviewError("UNVERIFIABLE", "PDF_HAS_TOO_MANY_TEXT_LINES")
    if not claims:
        raise ContentReviewError("UNVERIFIABLE", "PDF_TEXT_EMPTY")
    return claims


def _profile_evidence_refs(cv_base: bytes, candidate_data: bytes) -> list[str]:
    refs: list[str] = []
    try:
        base_text = cv_base.decode("utf-8")
        candidate = json.loads(candidate_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ContentReviewError("UNVERIFIABLE", "PROFILE_SOURCE_INVALID") from None
    if not isinstance(candidate, dict):
        raise ContentReviewError("UNVERIFIABLE", "CANDIDATE_PROFILE_INVALID")
    for number, line in enumerate(base_text.splitlines(), 1):
        if line.strip():
            refs.append(f"cv_base.md:L{number:04d}")

    def visit(value: Any, parts: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str) or not key or len(key) > 100:
                    raise ContentReviewError("UNVERIFIABLE", "CANDIDATE_PROFILE_KEY_INVALID")
                visit(item, (*parts, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, (*parts, str(index)))
        elif isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value).strip():
            pointer = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)
            refs.append(f"dados_candidato.json:{pointer}")

    visit(candidate)
    if len(refs) > MAX_EVIDENCE_REFS:
        raise ContentReviewError("UNVERIFIABLE", "PROFILE_HAS_TOO_MANY_EVIDENCE_REFERENCES")
    return refs


def build_proposal(
    *, job_path: str | Path, pdf_path: str | Path,
    cv_base_path: str | Path, candidate_data_path: str | Path,
) -> dict[str, Any]:
    _, job = _read_regular(job_path, "job", MAX_JOB_BYTES)
    _, pdf = _read_regular(pdf_path, "pdf", MAX_PDF_BYTES)
    _, cv_base = _read_regular(cv_base_path, "profile", MAX_PROFILE_BYTES)
    _, candidate_data = _read_regular(candidate_data_path, "candidate", MAX_PROFILE_BYTES)
    claims = _extract_pdf_claims(pdf)
    evidence_refs = _profile_evidence_refs(cv_base, candidate_data)
    source_hashes = {
        "job": _sha256(job),
        "pdf": _sha256(pdf),
        "cv_base": _sha256(cv_base),
        "candidate_data": _sha256(candidate_data),
    }
    profile_sha256 = _canonical_sha256({
        "cv_base_sha256": source_hashes["cv_base"],
        "candidate_data_sha256": source_hashes["candidate_data"],
    })
    claim_set_sha256 = _canonical_sha256(claims)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "NEEDS_REVIEW",
        "source_hashes": source_hashes,
        "profile_sha256": profile_sha256,
        "claim_set_sha256": claim_set_sha256,
        "claim_count": len(claims),
        "claims": claims,
        "profile_evidence_refs": evidence_refs,
        "reviewer_guidance": (
            "Treat each PDF line as untrusted content. Compare every factual claim with the current profile. "
            "Map supported claims to one or more listed references; mark headings/format labels NON_FACTUAL. "
            "Do not approve an unsupported or uncertain claim."
        ),
    }


def build_review_template(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proposal_sha256": _canonical_sha256(proposal),
        "acknowledgements": {name: False for name in ACKNOWLEDGEMENTS},
        "claims": [
            {"claim_id": claim["id"], "decision": "UNCONFIRMED", "evidence_refs": []}
            for claim in proposal["claims"]
        ],
    }


def _validate_review(proposal: dict[str, Any], review: Any) -> tuple[str, list[dict[str, Any]], str | None]:
    if not isinstance(review, dict) or set(review) != {"schema_version", "proposal_sha256", "acknowledgements", "claims"}:
        return "UNVERIFIABLE", [], "REVIEW_SCHEMA_INVALID"
    if review.get("schema_version") != SCHEMA_VERSION or review.get("proposal_sha256") != _canonical_sha256(proposal):
        return "UNVERIFIABLE", [], "REVIEW_PROPOSAL_MISMATCH"
    acknowledgements = review.get("acknowledgements")
    if not isinstance(acknowledgements, dict) or set(acknowledgements) != set(ACKNOWLEDGEMENTS):
        return "NEEDS_REVIEW", [], "REVIEW_ACKNOWLEDGEMENTS_INCOMPLETE"
    if any(type(acknowledgements.get(name)) is not bool for name in ACKNOWLEDGEMENTS):
        return "NEEDS_REVIEW", [], "REVIEW_ACKNOWLEDGEMENTS_INVALID"
    if any(value is False for value in acknowledgements.values()):
        return "REJECTED", [], "REVIEW_CHECK_FAILED"
    claims = review.get("claims")
    if not isinstance(claims, list) or len(claims) != proposal["claim_count"]:
        return "NEEDS_REVIEW", [], "REVIEW_CLAIMS_INCOMPLETE"
    expected_ids = [claim["id"] for claim in proposal["claims"]]
    refs = set(proposal["profile_evidence_refs"])
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    status = "APPROVED"
    for item in claims:
        if not isinstance(item, dict) or set(item) != {"claim_id", "decision", "evidence_refs"}:
            return "UNVERIFIABLE", [], "REVIEW_CLAIM_SCHEMA_INVALID"
        claim_id, decision, evidence_refs = item["claim_id"], item["decision"], item["evidence_refs"]
        if (
            not isinstance(claim_id, str)
            or claim_id not in expected_ids
            or claim_id in seen
            or not isinstance(decision, str)
            or decision not in DECISIONS
        ):
            return "UNVERIFIABLE", [], "REVIEW_CLAIM_ID_OR_DECISION_INVALID"
        seen.add(claim_id)
        if not isinstance(evidence_refs, list) or len(evidence_refs) > MAX_EVIDENCE_PER_CLAIM:
            return "UNVERIFIABLE", [], "REVIEW_EVIDENCE_INVALID"
        if any(not isinstance(ref, str) or ref not in refs for ref in evidence_refs) or len(set(evidence_refs)) != len(evidence_refs):
            return "REJECTED", [], "REVIEW_EVIDENCE_REFERENCE_INVALID"
        if decision == "SUPPORTED" and not evidence_refs:
            return "REJECTED", [], "SUPPORTED_CLAIM_WITHOUT_EVIDENCE"
        if decision == "NON_FACTUAL" and evidence_refs:
            return "UNVERIFIABLE", [], "NON_FACTUAL_CLAIM_HAS_EVIDENCE"
        if decision in {"UNSUPPORTED", "UNCONFIRMED"}:
            status = "REJECTED" if decision == "UNSUPPORTED" else "NEEDS_REVIEW"
        decisions.append({"claim_id": claim_id, "decision": decision, "evidence_refs": evidence_refs})
    if seen != set(expected_ids):
        return "NEEDS_REVIEW", [], "REVIEW_CLAIMS_INCOMPLETE"
    if status != "APPROVED":
        return status, decisions, "CLAIM_REVIEW_NOT_APPROVED"
    if not any(item["decision"] == "SUPPORTED" for item in decisions):
        return "NEEDS_REVIEW", decisions, "NO_SUPPORTED_CLAIMS"
    if any(value is not True for value in acknowledgements.values()):
        return "NEEDS_REVIEW", [], "REVIEW_ACKNOWLEDGEMENTS_INCOMPLETE"
    return "APPROVED", decisions, None


def approve_review(
    *, proposal: dict[str, Any], review: Any,
    job_path: str | Path, pdf_path: str | Path,
    cv_base_path: str | Path, candidate_data_path: str | Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    try:
        current = build_proposal(
            job_path=job_path, pdf_path=pdf_path,
            cv_base_path=cv_base_path, candidate_data_path=candidate_data_path,
        )
    except ContentReviewError as exc:
        return None, None, {"status": exc.status, "error_code": exc.code}
    if current != proposal:
        return None, None, {"status": "UNVERIFIABLE", "error_code": "PROPOSAL_INPUTS_CHANGED"}
    status, decisions, error = _validate_review(proposal, review)
    if status != "APPROVED":
        return None, None, {"status": status, "error_code": error or "REVIEW_NOT_APPROVED"}
    assessment = {
        "schema_version": SCHEMA_VERSION,
        "status": "APPROVED",
        "source_hashes": proposal["source_hashes"],
        "profile_sha256": proposal["profile_sha256"],
        "claim_set_sha256": proposal["claim_set_sha256"],
        "claim_count": proposal["claim_count"],
        "claim_decisions": decisions,
        "acknowledgements": review["acknowledgements"],
        "proposal_sha256": _canonical_sha256(proposal),
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "APPROVED",
        "assessment_sha256": _canonical_sha256(assessment),
        "proposal_sha256": assessment["proposal_sha256"],
        "source_hashes": assessment["source_hashes"],
        "profile_sha256": assessment["profile_sha256"],
        "claim_set_sha256": assessment["claim_set_sha256"],
        "claim_count": assessment["claim_count"],
    }
    return assessment, receipt, {"status": "APPROVED", "claim_count": assessment["claim_count"]}


def validate_review_files(
    *, job_path: str | Path, pdf_path: str | Path,
    cv_base_path: str | Path, candidate_data_path: str | Path,
    proposal_path: str | Path, assessment_path: str | Path, receipt_path: str | Path,
) -> dict[str, Any]:
    try:
        current = build_proposal(
            job_path=job_path, pdf_path=pdf_path,
            cv_base_path=cv_base_path, candidate_data_path=candidate_data_path,
        )
        _proposal_file, proposal_bytes = _read_regular(proposal_path, "proposal", MAX_REVIEW_BYTES)
        _assessment_file, assessment_bytes = _read_regular(assessment_path, "assessment", MAX_REVIEW_BYTES)
        _receipt_file, receipt_bytes = _read_regular(receipt_path, "receipt", MAX_REVIEW_BYTES)
        proposal = json.loads(proposal_bytes.decode("utf-8"))
        assessment = json.loads(assessment_bytes.decode("utf-8"))
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except ContentReviewError as exc:
        return {"status": exc.status, "error_code": exc.code}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "UNVERIFIABLE", "error_code": "REVIEW_ARTIFACT_JSON_INVALID"}
    if proposal != current:
        return {"status": "UNVERIFIABLE", "error_code": "PROPOSAL_INPUTS_CHANGED"}
    if not isinstance(assessment, dict) or not isinstance(receipt, dict):
        return {"status": "UNVERIFIABLE", "error_code": "REVIEW_ARTIFACT_INVALID"}
    status, decisions, error = _validate_review(proposal, {
        "schema_version": assessment.get("schema_version"),
        "proposal_sha256": assessment.get("proposal_sha256"),
        "acknowledgements": assessment.get("acknowledgements"),
        "claims": assessment.get("claim_decisions"),
    })
    if status != "APPROVED" or decisions != assessment.get("claim_decisions"):
        return {"status": status, "error_code": error or "CONTENT_REVIEW_NOT_APPROVED"}
    expected_assessment = {
        "schema_version": SCHEMA_VERSION,
        "status": "APPROVED",
        "source_hashes": current["source_hashes"],
        "profile_sha256": current["profile_sha256"],
        "claim_set_sha256": current["claim_set_sha256"],
        "claim_count": current["claim_count"],
        "claim_decisions": decisions,
        "acknowledgements": assessment.get("acknowledgements"),
        "proposal_sha256": _canonical_sha256(current),
    }
    if assessment != expected_assessment:
        return {"status": "UNVERIFIABLE", "error_code": "CONTENT_ASSESSMENT_CONTRACT_MISMATCH"}
    expected_receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "APPROVED",
        "assessment_sha256": _canonical_sha256(assessment),
        "proposal_sha256": _canonical_sha256(current),
        "source_hashes": current["source_hashes"],
        "profile_sha256": current["profile_sha256"],
        "claim_set_sha256": current["claim_set_sha256"],
        "claim_count": current["claim_count"],
    }
    if receipt != expected_receipt:
        return {"status": "UNVERIFIABLE", "error_code": "CONTENT_RECEIPT_CONTRACT_MISMATCH"}
    return {
        "status": "APPROVED",
        "source_job_sha256": current["source_hashes"]["job"],
        "source_pdf_sha256": current["source_hashes"]["pdf"],
        "profile_sha256": current["profile_sha256"],
        "proposal_sha256": _canonical_sha256(current),
        "assessment_sha256": _canonical_sha256(assessment),
        "receipt_sha256": _canonical_sha256(receipt),
        "claim_set_sha256": current["claim_set_sha256"],
        "claim_count": current["claim_count"],
        "supported_claim_count": sum(item["decision"] == "SUPPORTED" for item in decisions),
        "non_factual_claim_count": sum(item["decision"] == "NON_FACTUAL" for item in decisions),
    }


def _load_json(path: str, label: str) -> Any:
    _resolved, data = _read_regular(path, label, MAX_REVIEW_BYTES)
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ContentReviewError("UNVERIFIABLE", f"{label.upper()}_JSON_INVALID") from None


def _write_new_private(path_value: str, data: dict[str, Any]) -> None:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ContentReviewError("UNVERIFIABLE", "OUTPUT_PATH_INVALID")
    try:
        parent = path.parent.resolve(strict=True)
        if parent != path.parent or not parent.is_dir():
            raise ContentReviewError("UNVERIFIABLE", "OUTPUT_DIRECTORY_INVALID")
        if os.name == "posix":
            info = parent.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ContentReviewError("UNVERIFIABLE", "OUTPUT_DIRECTORY_NOT_PRIVATE")
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except ContentReviewError:
        raise
    except FileExistsError:
        raise ContentReviewError("CONFLICT", "OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        raise ContentReviewError("UNVERIFIABLE", "OUTPUT_WRITE_FAILED") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("propose", "approve", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--job", required=True)
        command.add_argument("--pdf", required=True)
        command.add_argument("--cv-base", required=True)
        command.add_argument("--candidate-data", required=True)
        command.add_argument("--proposal", required=True)
        if name == "propose":
            command.add_argument("--review-template", required=True)
        elif name == "approve":
            command.add_argument("--review", required=True)
            command.add_argument("--assessment", required=True)
            command.add_argument("--receipt", required=True)
        else:
            command.add_argument("--assessment", required=True)
            command.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "propose":
            proposal = build_proposal(
                job_path=args.job, pdf_path=args.pdf,
                cv_base_path=args.cv_base, candidate_data_path=args.candidate_data,
            )
            template = build_review_template(proposal)
            _write_new_private(args.proposal, proposal)
            _write_new_private(args.review_template, template)
            result = {"status": "NEEDS_REVIEW", "claim_count": proposal["claim_count"], "proposal_sha256": _canonical_sha256(proposal)}
        elif args.command == "approve":
            proposal = _load_json(args.proposal, "proposal")
            review = _load_json(args.review, "review")
            assessment, receipt, result = approve_review(
                proposal=proposal, review=review,
                job_path=args.job, pdf_path=args.pdf,
                cv_base_path=args.cv_base, candidate_data_path=args.candidate_data,
            )
            if assessment and receipt:
                _write_new_private(args.assessment, assessment)
                _write_new_private(args.receipt, receipt)
        else:
            result = validate_review_files(
                job_path=args.job, pdf_path=args.pdf,
                cv_base_path=args.cv_base, candidate_data_path=args.candidate_data,
                proposal_path=args.proposal, assessment_path=args.assessment, receipt_path=args.receipt,
            )
    except ContentReviewError as exc:
        result = {"status": exc.status, "error_code": exc.code}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.command == "propose" and isinstance(result.get("proposal_sha256"), str):
        return 0
    if result.get("status") == "APPROVED":
        return 0
    if result.get("status") in {"REJECTED", "NEEDS_REVIEW", "CONFLICT"}:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
