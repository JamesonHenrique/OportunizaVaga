"""Fail-closed checks that bind a pending application to its approved CV and browser file."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import unicodedata
from pathlib import Path

import cv_content_review
import job_requirement_review

MANIFEST_FIELDS = ("cv_manifest_id", "cv_job_sha256", "cv_pdf_sha256")
JOB_BINDING_FIELDS = ("cv_job_key", "cv_job_company", "cv_job_title")
ARTIFACT_PATH_FIELDS = ("cv_announcement_path", "cv_attachment_path")
BROWSER_FIELDS = ("cv_browser_url_prefix", "cv_browser_input_selector")
REQUIREMENT_REVIEW_PATH_FIELDS = (
    "cv_requirements_profile_path", "cv_requirements_assessment_path", "cv_requirements_receipt_path",
)
REQUIREMENT_AUDIT_FIELDS = (
    "cv_requirement_review_sha256", "cv_requirement_assessment_sha256",
    "cv_requirement_receipt_sha256", "cv_requirement_profile_sha256",
    "cv_requirement_status", "cv_requirement_required_barrier_count",
)
CONTENT_REVIEW_PATH_FIELDS = (
    "cv_content_cv_base_path",
    "cv_content_candidate_data_path",
    "cv_content_proposal_path",
    "cv_content_assessment_path",
    "cv_content_receipt_path",
)
CONTENT_REVIEW_AUDIT_FIELDS = (
    "cv_content_review_status",
    "cv_content_review_sha256",
    "cv_content_assessment_sha256",
    "cv_content_receipt_sha256",
    "cv_content_profile_sha256",
    "cv_content_claim_set_sha256",
    "cv_content_claim_count",
    "cv_content_supported_claim_count",
    "cv_content_non_factual_claim_count",
)
RECOMMENDATIONS = {
    "DO_NOT_PREPARE",
    "REVIEW_PROFILE_GAPS",
    "REVIEW_UNCONFIRMED_REQUIREMENTS",
    "POTENTIAL_FIT_REQUIRES_HUMAN_REVIEW",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
JOB_KEY_RE = re.compile(r"^[\w.\-#]{3,160}$")
MAX_ANNOUNCEMENT_BYTES = 1024 * 1024
MAX_PDF_BYTES = 4 * 1024 * 1024
GATE_TIMEOUT_SECONDS = 90
BROWSER_TIMEOUT_SECONDS = 45


def manifest_fields(record: dict) -> dict | None:
    """Return a complete immutable reference, {}, or None for a partial/invalid reference."""
    present = [field in record for field in MANIFEST_FIELDS]
    binding_present = [field in record for field in JOB_BINDING_FIELDS]
    if not any(present):
        has_audit = any(field in record for field in (*REQUIREMENT_AUDIT_FIELDS, *CONTENT_REVIEW_AUDIT_FIELDS))
        return None if any(binding_present) or has_audit else {}
    if not all(present):
        return None
    manifest_id, job_sha, pdf_sha = (record.get(field) for field in MANIFEST_FIELDS)
    if (
        not isinstance(job_sha, str)
        or not SHA256_RE.fullmatch(job_sha)
        or not isinstance(pdf_sha, str)
        or not SHA256_RE.fullmatch(pdf_sha)
        or manifest_id != f"{job_sha}-{pdf_sha}"
    ):
        return None
    reference = {field: record[field] for field in MANIFEST_FIELDS}
    if any(binding_present):
        if not all(binding_present):
            return None
        job_key, company, title = (record.get(field) for field in JOB_BINDING_FIELDS)
        if (
            not isinstance(job_key, str)
            or not JOB_KEY_RE.fullmatch(job_key)
            or not isinstance(company, str)
            or not company.strip()
            or len(company) > 200
            or not isinstance(title, str)
            or not title.strip()
            or len(title) > 200
        ):
            return None
        reference.update({field: record[field] for field in JOB_BINDING_FIELDS})
    requirement_audit = requirement_audit_fields(record)
    if requirement_audit is None:
        return None
    reference.update(requirement_audit)
    content_audit = content_review_audit_fields(record)
    if content_audit is None:
        return None
    reference.update(content_audit)
    return reference


def requirement_audit_fields(record: dict, *, required: bool = False) -> dict | None:
    present = [field in record for field in REQUIREMENT_AUDIT_FIELDS]
    if not any(present):
        return None if required else {}
    if not all(present):
        return None
    for field in REQUIREMENT_AUDIT_FIELDS[:4]:
        if not isinstance(record.get(field), str) or not SHA256_RE.fullmatch(record[field]):
            return None
    barrier_count = record.get("cv_requirement_required_barrier_count")
    if (
        record.get("cv_requirement_status") != "APPROVED"
        or isinstance(barrier_count, bool)
        or not isinstance(barrier_count, int)
        or barrier_count != 0
    ):
        return None
    return {field: record[field] for field in REQUIREMENT_AUDIT_FIELDS}


def content_review_audit_fields(record: dict, *, required: bool = False) -> dict | None:
    present = [field in record for field in CONTENT_REVIEW_AUDIT_FIELDS]
    if not any(present):
        return None if required else {}
    if not all(present):
        return None
    result = {field: record[field] for field in CONTENT_REVIEW_AUDIT_FIELDS}
    if result["cv_content_review_status"] != "APPROVED":
        return None
    for field in CONTENT_REVIEW_AUDIT_FIELDS[1:6]:
        if not isinstance(result[field], str) or not SHA256_RE.fullmatch(result[field]):
            return None
    counts = [result[field] for field in CONTENT_REVIEW_AUDIT_FIELDS[6:]]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
        return None
    claim_count, supported_count, non_factual_count = counts
    if claim_count < 1 or supported_count < 1 or supported_count + non_factual_count != claim_count:
        return None
    return result


def _normalize_job_identity(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _validate_job_binding(info: dict, reference: dict, application_key: str | None) -> str:
    if not all(field in reference for field in JOB_BINDING_FIELDS):
        return "approved CV reference is missing its job identity binding"
    if not isinstance(application_key, str) or reference.get("cv_job_key") != application_key:
        return "approved CV belongs to a different application key"
    for field, application_field, label in (
        ("cv_job_company", "empresa", "company"),
        ("cv_job_title", "vaga", "title"),
    ):
        value = info.get(application_field)
        approved = reference.get(field)
        if (
            not isinstance(value, str)
            or not value.strip()
            or not isinstance(approved, str)
            or _normalize_job_identity(value) != _normalize_job_identity(approved)
        ):
            return f"application {label} does not match the approved CV job binding"
    return ""


def _hash_regular_file(value, label, maximum_bytes):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} path is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ValueError(f"{label} path must be absolute and must not be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(f"{label} is not a regular file")
            if before.st_size > maximum_bytes:
                raise ValueError(f"{label} exceeds the allowed size")
            for chunk in iter(lambda: stream.read(131072), b""):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        current = resolved.stat()
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise ValueError(f"{label} changed while it was being checked")
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    return resolved, digest.hexdigest()


def _safe_environment(allowed: set[str]) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env.setdefault("HOME", str(Path.home()))
    return env


def _read_json_result(stdout: str) -> dict | None:
    records = []
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "status" in record:
            records.append(record)
    return records[0] if len(records) == 1 else None


def _verify_browser_attachment(info: dict, expected_sha256: str) -> tuple[dict | None, str]:
    if any(field not in info for field in BROWSER_FIELDS):
        return None, "both browser URL prefix and file-input selector are required"
    url_prefix, selector = (info.get(field) for field in BROWSER_FIELDS)
    if not isinstance(url_prefix, str) or not isinstance(selector, str):
        return None, "browser URL prefix or file-input selector is invalid"

    gate_value = os.environ.get("OV_CV_BROWSER_GATE", "").strip()
    gate = Path(gate_value).expanduser() if gate_value else Path(__file__).resolve().with_name("verificar_anexo.py")
    if not gate.is_absolute() or not gate.is_file():
        return None, "browser attachment verifier is unavailable"

    try:
        result = subprocess.run(
            [
                sys.executable, str(gate),
                "--url-prefix", url_prefix,
                "--selector", selector,
                "--expected-sha256", expected_sha256,
            ],
            cwd=str(Path(__file__).resolve().parent),
            env=_safe_environment({"PATH", "HOME", "LANG", "LC_ALL", "CDP_URL"}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=BROWSER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "browser attachment verification timed out"
    except OSError:
        return None, "browser attachment verifier could not be started"

    record = _read_json_result(result.stdout)
    if (
        result.returncode != 0
        or not isinstance(record, dict)
        or record.get("status") != "APPROVED"
        or record.get("expected_sha256") != expected_sha256
        or record.get("selected_sha256") != expected_sha256
        or type(record.get("input_count")) is not int
        or record.get("input_count") != 1
        or type(record.get("selected_file_count")) is not int
        or record.get("selected_file_count") != 1
        or type(record.get("matching_file_count")) is not int
        or record.get("matching_file_count") != 1
        or not isinstance(record.get("verified_at"), str)
        or not record.get("verified_at")
    ):
        status = record.get("status", "UNVERIFIABLE") if isinstance(record, dict) else "UNVERIFIABLE"
        return None, f"browser attachment verifier returned {status}"
    return {
        "url_prefix": url_prefix,
        "input_selector": selector,
        "selected_sha256": expected_sha256,
        "verified_at": record["verified_at"],
    }, ""


def _verify_requirement_review(
    info: dict, announcement: Path, title: str, expected_job_sha256: str,
) -> tuple[dict | None, str]:
    if not all(field in info for field in REQUIREMENT_REVIEW_PATH_FIELDS):
        return None, "typed requirement review profile, assessment and receipt are required"
    if any(not isinstance(info[field], str) or not info[field].strip() for field in REQUIREMENT_REVIEW_PATH_FIELDS):
        return None, "typed requirement review profile, assessment and receipt are required"
    try:
        result = job_requirement_review.validate_review_files(
            job_path=str(announcement),
            title=title,
            profile_path=info[REQUIREMENT_REVIEW_PATH_FIELDS[0]],
            assessment_path=info[REQUIREMENT_REVIEW_PATH_FIELDS[1]],
            receipt_path=info[REQUIREMENT_REVIEW_PATH_FIELDS[2]],
        )
    except Exception:
        return None, "typed requirement review is unverifiable"
    if result.get("status") != "APPROVED":
        return None, f"typed requirement review returned {result.get('status', 'UNVERIFIABLE')}"
    if result.get("source_job_sha256") != expected_job_sha256:
        return None, "typed requirement review is bound to a different announcement"
    audit = {
        "cv_requirement_review_sha256": result.get("review_sha256"),
        "cv_requirement_assessment_sha256": result.get("assessment_sha256"),
        "cv_requirement_receipt_sha256": result.get("receipt_sha256"),
        "cv_requirement_profile_sha256": result.get("profile_sha256"),
        "cv_requirement_status": "APPROVED",
        "cv_requirement_required_barrier_count": result.get("required_barrier_count"),
    }
    if requirement_audit_fields(audit, required=True) != audit:
        return None, "typed requirement review returned an invalid audit summary"
    supplied = requirement_audit_fields(info)
    if supplied is None or supplied and supplied != audit:
        return None, "typed requirement review changed after the caller prepared the intent"
    return audit, ""


def _verify_content_review(
    info: dict, announcement: Path, attachment: Path,
    expected_job_sha256: str, expected_pdf_sha256: str,
) -> tuple[dict | None, str]:
    if not all(field in info for field in CONTENT_REVIEW_PATH_FIELDS):
        return None, "final factual content review proposal, assessment, receipt and profile sources are required"
    if any(not isinstance(info[field], str) or not info[field].strip() for field in CONTENT_REVIEW_PATH_FIELDS):
        return None, "final factual content review paths are invalid"
    try:
        result = cv_content_review.validate_review_files(
            job_path=str(announcement),
            pdf_path=str(attachment),
            cv_base_path=info[CONTENT_REVIEW_PATH_FIELDS[0]],
            candidate_data_path=info[CONTENT_REVIEW_PATH_FIELDS[1]],
            proposal_path=info[CONTENT_REVIEW_PATH_FIELDS[2]],
            assessment_path=info[CONTENT_REVIEW_PATH_FIELDS[3]],
            receipt_path=info[CONTENT_REVIEW_PATH_FIELDS[4]],
        )
    except Exception:
        return None, "final factual content review is unverifiable"
    if result.get("status") != "APPROVED":
        return None, f"final factual content review returned {result.get('status', 'UNVERIFIABLE')}"
    if (
        result.get("source_job_sha256") != expected_job_sha256
        or result.get("source_pdf_sha256") != expected_pdf_sha256
    ):
        return None, "final factual content review is bound to a different job or PDF"
    audit = {
        "cv_content_review_status": "APPROVED",
        "cv_content_review_sha256": result.get("proposal_sha256"),
        "cv_content_assessment_sha256": result.get("assessment_sha256"),
        "cv_content_receipt_sha256": result.get("receipt_sha256"),
        "cv_content_profile_sha256": result.get("profile_sha256"),
        "cv_content_claim_set_sha256": result.get("claim_set_sha256"),
        "cv_content_claim_count": result.get("claim_count"),
        "cv_content_supported_claim_count": result.get("supported_claim_count"),
        "cv_content_non_factual_claim_count": result.get("non_factual_claim_count"),
    }
    if content_review_audit_fields(audit, required=True) != audit:
        return None, "final factual content review returned an invalid audit summary"
    supplied = content_review_audit_fields(info)
    if supplied is None or supplied and supplied != audit:
        return None, "final factual content review changed after the caller prepared the intent"
    return audit, ""


def verify_cv_attachment(
    info: dict, reference: dict, application_key: str | None = None
) -> tuple[dict | None, str]:
    """Rerun the required ATS/Resume-Matcher gate and confirm the exact browser-selected file."""
    binding_error = _validate_job_binding(info, reference, application_key)
    if binding_error:
        return None, binding_error
    try:
        announcement, job_sha = _hash_regular_file(
            info.get("cv_announcement_path"), "Job description", MAX_ANNOUNCEMENT_BYTES
        )
        attachment, pdf_sha = _hash_regular_file(
            info.get("cv_attachment_path"), "CV attachment", MAX_PDF_BYTES
        )
    except ValueError as exc:
        return None, str(exc)
    if job_sha != reference["cv_job_sha256"] or pdf_sha != reference["cv_pdf_sha256"]:
        return None, "job description or PDF hash differs from the approved manifest"
    if reference["cv_manifest_id"] != f"{job_sha}-{pdf_sha}":
        return None, "manifest id does not match the selected job/PDF pair"

    requirements_review, requirements_error = _verify_requirement_review(
        info, announcement, reference["cv_job_title"], job_sha,
    )
    if requirements_review is None:
        return None, requirements_error
    content_review, content_error = _verify_content_review(
        info, announcement, attachment, job_sha, pdf_sha,
    )
    if content_review is None:
        return None, content_error

    recommendation = info.get("cv_compatibility_recommendation")
    if recommendation is not None:
        if not isinstance(recommendation, str) or recommendation not in RECOMMENDATIONS:
            return None, "compatibility recommendation is invalid"
        if recommendation == "DO_NOT_PREPARE":
            return None, "vacancy compatibility gate says DO_NOT_PREPARE"

    gate_value = os.environ.get("OV_CV_READY_GATE", "").strip()
    gate = Path(gate_value).expanduser() if gate_value else Path(__file__).resolve().with_name("cv-pronto.sh")
    if not gate.is_absolute() or not gate.is_file() or not os.access(gate, os.X_OK):
        return None, "CV approval gate is unavailable"

    allowed = {
        "PATH", "HOME", "LANG", "LC_ALL", "CV_BASE_FILE", "DADOS_CANDIDATO_FILE", "BOT_ROOT", "OV_ATS_LOG",
        "OV_RESUME_MATCHER_BRIDGE", "OV_RESUME_MATCHER_CLI", "OV_RESUME_MATCHER_REVISION",
        "OV_RESUME_MATCHER_BACKEND_DIR", "OV_RESUME_MATCHER_DATA_DIR", "OV_RESUME_MATCHER_MANIFEST_DIR",
        "OV_RESUME_MATCHER_LOG",
        "CDP_URL", "OV_CV_READY_GATE", "OV_CV_BROWSER_GATE",
    }
    env = _safe_environment(allowed)
    env["OV_RESUME_MATCHER_REQUIRED"] = "1"
    try:
        result = subprocess.run(
            [str(gate), str(announcement), str(attachment)],
            cwd=str(Path(__file__).resolve().parent),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GATE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "CV approval gate timed out"
    except OSError:
        return None, "CV approval gate could not be started"

    record = _read_json_result(result.stdout)
    attach_lines = [line[7:] for line in result.stdout.splitlines() if line.startswith("ANEXAR ")]
    if (
        result.returncode != 0
        or not isinstance(record, dict)
        or record.get("status") != "APPROVED"
        or record.get("manifest_verified") is not True
        or record.get("manifest_id") != reference["cv_manifest_id"]
        or record.get("job_description_sha256") != job_sha
        or record.get("pdf_sha256") != pdf_sha
        or record.get("sha256") != pdf_sha
        or not isinstance(record.get("resume_matcher_revision"), str)
        or re.fullmatch(r"[0-9a-f]{40}", record.get("resume_matcher_revision", "")) is None
        or isinstance(record.get("verifier_policy_version"), bool)
        or not isinstance(record.get("verifier_policy_version"), int)
        or record.get("verifier_policy_version") < 1
        or not isinstance(record.get("verified_at"), str)
        or not record.get("verified_at")
        or attach_lines != [str(attachment)]
    ):
        status = record.get("status", "UNVERIFIABLE") if isinstance(record, dict) else "UNVERIFIABLE"
        return None, f"CV approval gate returned {status} or a mismatched manifest"

    browser, browser_error = _verify_browser_attachment(info, pdf_sha)
    if browser is None:
        return None, browser_error
    try:
        if _hash_regular_file(str(announcement), "Job description", MAX_ANNOUNCEMENT_BYTES)[1] != job_sha:
            return None, "job description changed during final verification"
        if _hash_regular_file(str(attachment), "CV attachment", MAX_PDF_BYTES)[1] != pdf_sha:
            return None, "PDF changed during final verification"
    except ValueError as exc:
        return None, str(exc)

    return {
        "reference": dict(reference),
        "announcement_path": str(announcement),
        "attachment_path": str(attachment),
        "job_sha256": job_sha,
        "pdf_sha256": pdf_sha,
        "compatibility_recommendation": recommendation,
        "requirements_review": requirements_review,
        "content_review": content_review,
        "browser": browser,
    }, ""


def check_preflight(
    info: dict, reference: dict, preflight: dict | None, application_key: str | None = None
) -> tuple[bool, str]:
    """Recheck artifact hashes and transient browser identifiers while the state lock is held."""
    if not isinstance(preflight, dict) or preflight.get("reference") != reference:
        return False, "fresh CV approval is missing"
    binding_error = _validate_job_binding(info, reference, application_key)
    if binding_error:
        return False, binding_error
    if info.get("cv_compatibility_recommendation") != preflight.get("compatibility_recommendation"):
        return False, "compatibility recommendation changed after verification"
    browser = preflight.get("browser")
    if (
        not isinstance(browser, dict)
        or info.get("cv_browser_url_prefix") != browser.get("url_prefix")
        or info.get("cv_browser_input_selector") != browser.get("input_selector")
        or browser.get("selected_sha256") != reference.get("cv_pdf_sha256")
    ):
        return False, "selected browser attachment changed after verification"
    try:
        announcement, job_sha = _hash_regular_file(
            info.get("cv_announcement_path"), "Job description", MAX_ANNOUNCEMENT_BYTES
        )
        attachment, pdf_sha = _hash_regular_file(
            info.get("cv_attachment_path"), "CV attachment", MAX_PDF_BYTES
        )
    except ValueError as exc:
        return False, str(exc)
    if (
        str(announcement) != preflight.get("announcement_path")
        or str(attachment) != preflight.get("attachment_path")
        or job_sha != reference.get("cv_job_sha256")
        or pdf_sha != reference.get("cv_pdf_sha256")
    ):
        return False, "job description or PDF changed before the intent was recorded"
    requirements_review, requirements_error = _verify_requirement_review(
        info, announcement, reference.get("cv_job_title", ""), job_sha,
    )
    if requirements_review is None or requirements_review != preflight.get("requirements_review"):
        return False, requirements_error or "typed requirement review changed before the intent was recorded"
    content_review, content_error = _verify_content_review(info, announcement, attachment, job_sha, pdf_sha)
    if content_review is None or content_review != preflight.get("content_review"):
        return False, content_error or "final factual content review changed before the intent was recorded"
    return True, ""
