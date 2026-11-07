#!/usr/bin/env python3
"""Score one explicitly selected discovery job with reviewed keywords and local ResumeData.

The score is advisory and heuristic. Candidate data stays local; only hashes and
job-derived score details are copied into the discovery queue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

BOT_DIR = Path(__file__).resolve().parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

import jsonlock
import job_keyword_proposal
import job_requirement_review
import resume_matcher_bridge

MAX_QUEUE_BYTES = 32 * 1024 * 1024
MAX_DESCRIPTION_BYTES = 1024 * 1024
MAX_KEYWORDS_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 256 * 1024
MAX_PROFILE_BYTES = 1024 * 1024
MAX_REQUIREMENTS_BYTES = 2 * 1024 * 1024
MAX_BATCH_BYTES = 1024 * 1024
MAX_BATCH_JOBS = 50
MAX_REPORT_AGE = timedelta(days=30)
REPORT_FIELD = "resume_matcher_compatibility"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
KEYWORD_FIELDS = {"required_skills", "preferred_skills", "keywords"}


class QueueCompatibilityError(ValueError):
    """The selected job, source files, or local queue are invalid or stale."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_file(path_value: str | Path, label: str, limit: int, *, private: bool = False) -> tuple[Path, bytes]:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise QueueCompatibilityError(f"{label} path must be absolute and must not be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > limit:
                raise QueueCompatibilityError(f"{label} is empty or exceeds its size limit")
            if os.name == "posix":
                if info.st_uid != os.getuid():
                    raise QueueCompatibilityError(f"{label} is not owned by the current user")
                if private and info.st_mode & 0o077:
                    raise QueueCompatibilityError(f"{label} must be readable only by the current user")
            data = stream.read(limit + 1)
    except QueueCompatibilityError:
        raise
    except OSError as exc:
        raise QueueCompatibilityError(f"{label} is unavailable") from exc
    if not data or len(data) > limit:
        raise QueueCompatibilityError(f"{label} is empty or exceeds its size limit")
    return resolved, data


def _load_object(path: str | Path, label: str, limit: int, *, private: bool = False) -> tuple[Path, bytes, dict[str, Any]]:
    resolved, raw = _read_file(path, label, limit, private=private)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QueueCompatibilityError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise QueueCompatibilityError(f"{label} must contain a JSON object")
    return resolved, raw, data


def _queue_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise QueueCompatibilityError("Queue path must be absolute and must not be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > MAX_QUEUE_BYTES:
                raise QueueCompatibilityError("Queue file is empty or exceeds its size limit")
            if os.name == "posix" and info.st_uid != os.getuid():
                raise QueueCompatibilityError("Queue file is not owned by the current user")
            json.loads(stream.read(MAX_QUEUE_BYTES + 1).decode("utf-8"))
    except QueueCompatibilityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QueueCompatibilityError("Queue file is unavailable or invalid JSON") from exc
    return resolved


def _read_queue(path: Path) -> dict[str, Any]:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > MAX_QUEUE_BYTES:
                raise QueueCompatibilityError("Queue file is empty or exceeds its size limit")
            if os.name == "posix" and info.st_uid != os.getuid():
                raise QueueCompatibilityError("Queue file is not owned by the current user")
            raw = stream.read(MAX_QUEUE_BYTES + 1)
        value = json.loads(raw.decode("utf-8"))
    except QueueCompatibilityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QueueCompatibilityError("Queue file is unavailable or invalid JSON") from exc
    if len(raw) > MAX_QUEUE_BYTES or not isinstance(value, dict) or not isinstance(value.get("vagas"), dict):
        raise QueueCompatibilityError("Queue schema does not contain a bounded jobs object")
    return value


def _selected_job(queue: dict[str, Any], key: str) -> dict[str, Any]:
    if not isinstance(key, str) or not key or len(key) > 256 or any(ord(ch) < 32 for ch in key):
        raise QueueCompatibilityError("Queue job key is invalid")
    job = queue["vagas"].get(key)
    if not isinstance(job, dict) or job.get("status") != "nova":
        raise QueueCompatibilityError("Only a new, pending queue job can be analyzed")
    if job.get("desc_checada") is not True:
        raise QueueCompatibilityError("Run discovery description triage before compatibility analysis")
    title, url = job.get("titulo"), job.get("url")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise QueueCompatibilityError("Queue job title is missing or invalid")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")) or len(url) > 4096:
        raise QueueCompatibilityError("Queue job URL is missing or invalid")
    return job


def description_cache_id(key: str) -> str:
    if not isinstance(key, str) or not key or len(key) > 256:
        raise QueueCompatibilityError("Queue job key is invalid")
    return _sha256(key.encode("utf-8"))


def description_path_for(queue_path: str | Path, key: str) -> Path:
    queue = _queue_path(queue_path)
    directory = queue.parent / "job-descriptions"
    if directory.is_symlink():
        raise QueueCompatibilityError("Job description directory must not be a symbolic link")
    return directory / f"{description_cache_id(key)}.txt"


def cache_job_description(state_dir: str | Path, key: str, text: str) -> tuple[str, str]:
    """Persist the exact text used by discovery's deterministic description gate."""
    if not isinstance(text, str) or not text.strip():
        raise QueueCompatibilityError("Job description is empty")
    data = text.encode("utf-8")
    if len(data) > MAX_DESCRIPTION_BYTES:
        raise QueueCompatibilityError("Job description exceeds its size limit")
    root_input = Path(state_dir).expanduser()
    if not root_input.is_absolute() or root_input.is_symlink():
        raise QueueCompatibilityError("Discovery state directory must be absolute and must not be a symbolic link")
    try:
        root_input.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = root_input.resolve(strict=True)
    except OSError as exc:
        raise QueueCompatibilityError("Discovery state directory is unavailable") from exc
    directory = root / "job-descriptions"
    try:
        if directory.is_symlink():
            raise QueueCompatibilityError("Job description directory must not be a symbolic link")
        directory.mkdir(mode=0o700, exist_ok=True)
        directory = directory.resolve(strict=True)
        if directory.parent != root or not directory.is_dir():
            raise QueueCompatibilityError("Job description directory is invalid")
        if os.name == "posix":
            info = directory.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise QueueCompatibilityError("Job description directory must be private to the current user")
        destination = directory / f"{description_cache_id(key)}.txt"
        if destination.is_symlink():
            raise QueueCompatibilityError("Job description cache file must not be a symbolic link")
        fd, temporary_name = tempfile.mkstemp(prefix=".description-", suffix=".tmp", dir=directory)
        temporary = Path(temporary_name)
        try:
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    except QueueCompatibilityError:
        raise
    except OSError as exc:
        raise QueueCompatibilityError("Job description could not be cached locally") from exc
    return description_cache_id(key), _sha256(data)


def _normalized(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", value.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def _validate_keywords(
    *, description_sha: str, title: str, keywords_path: str | Path, receipt_path: str | Path,
) -> tuple[Path, bytes, dict[str, Any], Path, bytes]:
    resolved_keywords, keyword_bytes, keywords = _load_object(keywords_path, "Reviewed job keywords", MAX_KEYWORDS_BYTES)
    resolved_receipt, receipt_bytes, receipt = _load_object(receipt_path, "Keyword review receipt", MAX_RECEIPT_BYTES)
    if set(keywords) - (KEYWORD_FIELDS | {"role", "source_job_sha256"}):
        raise QueueCompatibilityError("Job keywords contain unsupported fields")
    if keywords.get("source_job_sha256") != description_sha:
        raise QueueCompatibilityError("Job keywords do not match the cached description hash")
    role = keywords.get("role")
    if not isinstance(role, str) or _normalized(role) != _normalized(title):
        raise QueueCompatibilityError("Reviewed keyword title does not match the queue job")
    for field in KEYWORD_FIELDS:
        values = keywords.get(field, [])
        if not isinstance(values, list) or len(values) > job_keyword_proposal.MAX_OUTPUT_GROUP:
            raise QueueCompatibilityError(f"Job keyword field {field} is invalid")
        if any(not isinstance(item, str) or not item.strip() or len(item) > job_keyword_proposal.MAX_TERM_LENGTH for item in values):
            raise QueueCompatibilityError(f"Job keyword field {field} contains an invalid term")
    if not any(keywords.get(field) for field in KEYWORD_FIELDS):
        raise QueueCompatibilityError("Reviewed job keywords are empty")
    if (
        receipt.get("status") != "APPROVED"
        or receipt.get("source_job_sha256") != description_sha
        or receipt.get("keywords_sha256") != _sha256(_canonical_json(keywords))
    ):
        raise QueueCompatibilityError("Keyword review receipt does not approve this description and keyword file")
    return resolved_keywords, keyword_bytes, keywords, resolved_receipt, receipt_bytes


def _validate_requirement_review(
    *, job_bytes: bytes, title: str, profile_bytes: bytes,
    assessment_value: str, receipt_value: str,
) -> tuple[Path, bytes, Path, bytes, dict[str, Any]]:
    assessment_path, assessment_bytes, assessment = _load_object(
        assessment_value, "Requirement assessment", MAX_REQUIREMENTS_BYTES, private=True,
    )
    receipt_path, receipt_bytes, receipt = _load_object(
        receipt_value, "Requirement review receipt", MAX_RECEIPT_BYTES, private=True,
    )
    if assessment.get("title") != title:
        raise QueueCompatibilityError("Requirement assessment title differs from the selected job")
    try:
        job_requirement_review.validate_approved(job_bytes, profile_bytes, assessment, receipt)
    except job_requirement_review.RequirementReviewError as exc:
        raise QueueCompatibilityError("Requirement review is stale, incomplete, or invalid") from exc
    summary = {
        "status": "APPROVED",
        "recommendation": assessment["recommendation"],
        "count": assessment["count"],
        "required_barrier_count": assessment["required_barrier_count"],
        "by_category": assessment["by_category"],
        "assessment_sha256": _sha256(assessment_bytes),
        "receipt_sha256": _sha256(receipt_bytes),
    }
    return assessment_path, assessment_bytes, receipt_path, receipt_bytes, summary


def _score(
    resume_path: Path,
    keywords: dict[str, Any],
    score_runner: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sanitized = {field: value for field, value in keywords.items() if field != "source_job_sha256"}
    try:
        with tempfile.TemporaryDirectory(prefix="ov-resume-score-") as temporary:
            score_path = Path(temporary) / "job-keywords.json"
            score_path.write_bytes(_canonical_json(sanitized))
            if os.name == "posix":
                score_path.chmod(0o600)
            runner = score_runner or resume_matcher_bridge.score_draft
            result = runner(str(resume_path), str(score_path))
    except Exception as exc:
        if isinstance(exc, QueueCompatibilityError):
            raise
        raise QueueCompatibilityError("Resume-Matcher scoring is unavailable") from exc
    if not isinstance(result, dict) or result.get("heuristic_only") is not True:
        raise QueueCompatibilityError("Resume-Matcher returned an invalid heuristic score")
    match = result.get("keyword_match_percentage")
    subscores = result.get("sub_scores")
    coverage = subscores.get("skills_coverage") if isinstance(subscores, dict) else None
    missing = result.get("missing_keywords")
    if (
        isinstance(match, bool) or not isinstance(match, (int, float)) or not 0 <= match <= 100
        or isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not 0 <= coverage <= 100
        or not isinstance(missing, list) or any(not isinstance(item, str) for item in missing)
    ):
        raise QueueCompatibilityError("Resume-Matcher score fields are incomplete")
    return {
        "heuristic_only": True,
        "keyword_match_percentage": round(float(match), 1),
        "skills_coverage": round(float(coverage), 1),
        "missing_keywords": missing[:30],
    }


def _gaps(keywords: dict[str, Any], score: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    missing = {_normalized(value) for value in score["missing_keywords"]}
    required = [value for value in keywords.get("required_skills", []) if _normalized(value) in missing]
    preferred = [value for value in keywords.get("preferred_skills", []) if _normalized(value) in missing]
    classified = {_normalized(value) for value in (*required, *preferred)}
    other = [value for value in score["missing_keywords"] if _normalized(value) not in classified]
    return required, preferred, other


def _evidence_references(profile: dict[str, Any], keywords: dict[str, Any]) -> dict[str, list[str]]:
    """Map exact normalized vacancy terms to ResumeData section labels, never text."""
    sources: list[tuple[str, str]] = []
    summary = profile.get("summary")
    if isinstance(summary, str):
        sources.append(("summary", summary))

    for field, title_fields in (
        ("workExperience", ("title", "company")),
        ("personalProjects", ("name", "role")),
        ("education", ("institution", "degree")),
    ):
        entries = profile.get(field, [])
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                continue
            description = entry.get("description", [])
            if isinstance(description, str):
                descriptions = [description]
            elif isinstance(description, list):
                descriptions = [value for value in description if isinstance(value, str)]
            else:
                descriptions = []
            headings = [str(entry.get(name, "")) for name in title_fields]
            sources.append((f"{field}#{index}", " ".join((*headings, *descriptions))))

    additional = profile.get("additional", {})
    if isinstance(additional, dict):
        for field, label in (
            ("technicalSkills", "additional.technicalSkills"),
            ("languages", "additional.languages"),
            ("certificationsTraining", "additional.certificationsTraining"),
        ):
            values = additional.get(field, [])
            if isinstance(values, list):
                sources.append((label, " ".join(value for value in values if isinstance(value, str))))

    custom = profile.get("customSections", {})
    if isinstance(custom, dict):
        for index, section in enumerate(custom.values(), start=1):
            if not isinstance(section, dict) or section.get("sectionType") != "stringList":
                continue
            values = section.get("strings", [])
            if isinstance(values, list):
                sources.append((f"customSections#{index}", " ".join(value for value in values if isinstance(value, str))))

    terms: list[str] = []
    seen: set[str] = set()
    for field in ("required_skills", "preferred_skills", "keywords"):
        for term in keywords.get(field, []):
            normalized = _normalized(term)
            if normalized and normalized not in seen:
                seen.add(normalized)
                terms.append(term)

    references: dict[str, list[str]] = {}
    for term in terms:
        normalized = _normalized(term)
        pattern = re.compile(
            r"(?<![\w+#.])" + re.escape(normalized).replace(r"\ ", r"\s+") + r"(?![\w+#]|\.(?=\w))",
            re.IGNORECASE,
        )
        found = [label for label, text in sources if pattern.search(_normalized(text))]
        references[term] = found[:8]
    return references


def _sidecar_path(queue_path: Path, key: str) -> Path:
    return queue_path.parent / ".resume-matcher-compatibility" / f"{description_cache_id(key)}.json"


def _atomic_private_json(path: Path, value: dict[str, Any]) -> None:
    directory = path.parent
    if directory.is_symlink():
        raise QueueCompatibilityError("Compatibility sidecar directory must not be a symbolic link")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = directory.resolve(strict=True)
    if os.name == "posix":
        info = directory.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise QueueCompatibilityError("Compatibility sidecar directory must be private to the current user")
    if path.exists() and path.is_symlink():
        raise QueueCompatibilityError("Compatibility sidecar must not be a symbolic link")
    payload = _canonical_json(value) + b"\n"
    fd, temporary_name = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=directory)
    temporary = Path(temporary_name)
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_private_sidecar(path: Path) -> dict[str, Any]:
    """Read an owner-only sidecar without following its directory or file symlinks."""
    max_bytes = 256 * 1024
    if os.name == "posix":
        directory_fd = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            directory_info = os.fstat(directory_fd)
            if (
                not stat.S_ISDIR(directory_info.st_mode)
                or directory_info.st_uid != os.getuid()
                or directory_info.st_mode & 0o077
            ):
                raise QueueCompatibilityError("Compatibility sidecar directory is not private")
            file_fd = os.open(
                path.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_fd,
            )
            with os.fdopen(file_fd, "rb") as stream:
                file_info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(file_info.st_mode)
                    or file_info.st_uid != os.getuid()
                    or file_info.st_mode & 0o077
                    or file_info.st_size <= 0
                    or file_info.st_size > max_bytes
                ):
                    raise QueueCompatibilityError("Compatibility sidecar is not a private regular file")
                raw = stream.read(max_bytes + 1)
        finally:
            os.close(directory_fd)
    else:
        if path.parent.is_symlink() or path.is_symlink():
            raise QueueCompatibilityError("Compatibility sidecar paths must not be symbolic links")
        with path.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise QueueCompatibilityError("Compatibility sidecar is not a regular file")
            raw = stream.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise QueueCompatibilityError("Compatibility sidecar is empty or exceeds its size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QueueCompatibilityError("Compatibility sidecar is invalid JSON") from exc
    if not isinstance(value, dict):
        raise QueueCompatibilityError("Compatibility sidecar must contain a JSON object")
    return value


def _sidecar_record(
    *, queue_path: Path, key: str, report: dict[str, Any], job_path: Path,
    keywords_path: Path, receipt_path: Path, profile_path: Path,
    requirements_path: Path | None = None, requirements_receipt_path: Path | None = None,
) -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "queue_path_sha256": _sha256(str(queue_path).encode("utf-8")),
        "queue_job_key": key,
        "report_sha256": _sha256(_canonical_json(report)),
        "job_path": str(job_path),
        "keywords_path": str(keywords_path),
        "receipt_path": str(receipt_path),
        "profile_path": str(profile_path),
        "job_description_sha256": report["job_description_sha256"],
        "keywords_sha256": report["keywords_sha256"],
        "review_receipt_sha256": report["review_receipt_sha256"],
        "profile_sha256": report["profile_sha256"],
        "title": report["title"],
        "job_url_sha256": report["job_url_sha256"],
    }
    if requirements_path is not None and requirements_receipt_path is not None:
        review = report["requirements_review"]
        record.update({
            "requirements_path": str(requirements_path),
            "requirements_receipt_path": str(requirements_receipt_path),
            "requirements_sha256": review["assessment_sha256"],
            "requirements_receipt_sha256": review["receipt_sha256"],
        })
    return record


def _persist_report(
    *, queue_path: Path, key: str, report: dict[str, Any], sidecar: dict[str, Any],
) -> None:
    with jsonlock.travado(str(queue_path)):
        queue = _read_queue(queue_path)
        job = _selected_job(queue, key)
        current_url_sha = _sha256(job["url"].encode("utf-8"))
        if (
            job["titulo"] != report["title"]
            or current_url_sha != report["job_url_sha256"]
            or job.get("job_description_id") != description_cache_id(key)
            or job.get("job_description_sha256") != report["job_description_sha256"]
        ):
            raise QueueCompatibilityError("Queue job changed while Resume-Matcher was scoring it")
        _atomic_private_json(_sidecar_path(queue_path, key), sidecar)
        job[REPORT_FIELD] = report
        try:
            jsonlock.gravar(str(queue_path), queue)
        except OSError as exc:
            raise QueueCompatibilityError("Compatibility report could not be saved to the queue") from exc


def analyze_queue_job(
    *,
    queue_path_value: str,
    key: str,
    resume_data_value: str,
    keywords_value: str,
    receipt_value: str,
    requirements_value: str | None = None,
    requirements_receipt_value: str | None = None,
    persist: bool = False,
    score_runner: Callable[[str, str], dict[str, Any]] | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    queue_path = _queue_path(queue_path_value)
    queue = _read_queue(queue_path)
    job = _selected_job(queue, key)
    revision = _pinned_revision()
    if expected_revision is not None and revision != expected_revision:
        raise QueueCompatibilityError("Resume-Matcher revision changed during batch analysis")
    title = job["titulo"].strip()
    url_sha = _sha256(job["url"].encode("utf-8"))
    if job.get("job_description_id") != description_cache_id(key):
        raise QueueCompatibilityError("Queue job has no current cached description; run discovery triage")
    description_path = description_path_for(queue_path, key)
    resolved_job, job_bytes = _read_file(description_path, "Cached job description", MAX_DESCRIPTION_BYTES)
    job_sha = _sha256(job_bytes)
    if job.get("job_description_sha256") != job_sha:
        raise QueueCompatibilityError("Cached job description differs from the discovery triage result")
    keywords_path, keywords_bytes, keywords, receipt_path, receipt_bytes = _validate_keywords(
        description_sha=job_sha,
        title=title,
        keywords_path=keywords_value,
        receipt_path=receipt_value,
    )
    profile_path, profile_bytes, profile_data = _load_object(
        resume_data_value, "ResumeData", MAX_PROFILE_BYTES, private=True
    )
    if not profile_data:
        raise QueueCompatibilityError("ResumeData is empty")
    if bool(requirements_value) != bool(requirements_receipt_value):
        raise QueueCompatibilityError("Requirement assessment and receipt must be supplied together")
    requirements_path: Path | None = None
    requirements_receipt_path: Path | None = None
    requirements_bytes: bytes | None = None
    requirements_receipt_bytes: bytes | None = None
    requirements_summary = {
        "status": "NOT_REVIEWED",
        "recommendation": "REVIEW_REQUIRED",
        "count": 0,
        "required_barrier_count": None,
        "by_category": {},
        "assessment_sha256": None,
        "receipt_sha256": None,
    }
    if requirements_value and requirements_receipt_value:
        (
            requirements_path, requirements_bytes,
            requirements_receipt_path, requirements_receipt_bytes,
            requirements_summary,
        ) = _validate_requirement_review(
            job_bytes=job_bytes, title=title, profile_bytes=profile_bytes,
            assessment_value=requirements_value, receipt_value=requirements_receipt_value,
        )
    score = _score(profile_path, keywords, score_runner)
    if _pinned_revision() != revision:
        raise QueueCompatibilityError("Resume-Matcher revision changed while scoring the job")
    # Re-read every input after the external CLI returns. A score is discarded if any
    # source changed while the parser was running, even when the caller did not persist it.
    _job_after, job_bytes_after = _read_file(description_path, "Cached job description", MAX_DESCRIPTION_BYTES)
    keywords_path_after, keywords_bytes_after, _keywords_after, receipt_path_after, receipt_bytes_after = _validate_keywords(
        description_sha=_sha256(job_bytes_after),
        title=title,
        keywords_path=keywords_path,
        receipt_path=receipt_path,
    )
    profile_path_after, profile_bytes_after, _profile_after = _load_object(
        profile_path, "ResumeData", MAX_PROFILE_BYTES, private=True
    )
    requirements_bytes_after = None
    requirements_receipt_bytes_after = None
    if requirements_path is not None and requirements_receipt_path is not None:
        (
            requirements_path_after, requirements_bytes_after,
            requirements_receipt_path_after, requirements_receipt_bytes_after,
            requirements_summary_after,
        ) = _validate_requirement_review(
            job_bytes=job_bytes_after, title=title, profile_bytes=profile_bytes_after,
            assessment_value=str(requirements_path), receipt_value=str(requirements_receipt_path),
        )
        if (
            str(requirements_path_after) != str(requirements_path)
            or str(requirements_receipt_path_after) != str(requirements_receipt_path)
            or requirements_summary_after != requirements_summary
        ):
            raise QueueCompatibilityError("Requirement review changed while Resume-Matcher was scoring the job")
    queue_after = _read_queue(queue_path)
    job_after = _selected_job(queue_after, key)
    if (
        job_after.get("titulo") != title
        or _sha256(job_after["url"].encode("utf-8")) != url_sha
        or job_after.get("job_description_id") != description_cache_id(key)
        or job_after.get("job_description_sha256") != job_sha
        or _sha256(job_bytes_after) != job_sha
        or str(keywords_path_after) != str(keywords_path)
        or _sha256(keywords_bytes_after) != _sha256(keywords_bytes)
        or str(receipt_path_after) != str(receipt_path)
        or _sha256(receipt_bytes_after) != _sha256(receipt_bytes)
        or str(profile_path_after) != str(profile_path)
        or _sha256(profile_bytes_after) != _sha256(profile_bytes)
        or (requirements_bytes is not None and _sha256(requirements_bytes_after or b"") != _sha256(requirements_bytes))
        or (
            requirements_receipt_bytes is not None
            and _sha256(requirements_receipt_bytes_after or b"") != _sha256(requirements_receipt_bytes)
        )
    ):
        raise QueueCompatibilityError("A job or profile input changed while Resume-Matcher was scoring it")
    required_gaps, preferred_gaps, other_gaps = _gaps(keywords, score)
    evidence_by_keyword = _evidence_references(profile_data, keywords)
    recommendation = (
        "REVIEW_POSSIBLE_BARRIER"
        if requirements_summary["status"] == "APPROVED" and requirements_summary["required_barrier_count"]
        else
        "REVIEW_PROFILE_GAPS" if required_gaps else
        "REVIEW_UNCONFIRMED_REQUIREMENTS" if other_gaps else
        "POTENTIAL_FIT_REQUIRES_REVIEW"
    )
    report = {
        "schema_version": 1,
        "status": "ANALYZED",
        "heuristic_only": True,
        "title": title,
        "queue_job_key": key,
        "job_url_sha256": url_sha,
        "job_description_sha256": job_sha,
        "keywords_sha256": _sha256(keywords_bytes),
        "review_receipt_sha256": _sha256(receipt_bytes),
        "profile_sha256": _sha256(profile_bytes),
        "resume_matcher_revision": revision,
        "analyzed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "score": score,
        "required_gaps": required_gaps,
        "preferred_gaps": preferred_gaps,
        "other_missing_keywords": other_gaps,
        "evidence_match_method": "literal_normalized_terms",
        "evidence_by_keyword": evidence_by_keyword,
        "requirements_review": requirements_summary,
        "recommendation": recommendation,
        "limitations": [
            "Heuristic comparison, not a probability of hiring or an ATS score.",
            "The report does not verify experience claims or answer personal application questions.",
            "Review the current official posting and profile evidence before preparing or sending an application.",
        ],
    }
    sidecar = _sidecar_record(
        queue_path=queue_path,
        key=key,
        report=report,
        job_path=resolved_job,
        keywords_path=keywords_path,
        receipt_path=receipt_path,
        profile_path=profile_path,
        requirements_path=requirements_path,
        requirements_receipt_path=requirements_receipt_path,
    )
    if persist:
        _persist_report(queue_path=queue_path, key=key, report=report, sidecar=sidecar)
    return report


def _pinned_revision() -> str:
    revision = os.environ.get("OV_RESUME_MATCHER_REVISION", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise QueueCompatibilityError("OV_RESUME_MATCHER_REVISION must be a pinned 40-character Git commit")
    return revision


def _load_batch_manifest(path_value: str | Path) -> list[dict[str, str]]:
    _path, _raw, manifest = _load_object(
        path_value, "Private batch manifest", MAX_BATCH_BYTES, private=True,
    )
    if set(manifest) != {"schema_version", "jobs"} or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise QueueCompatibilityError("Batch manifest schema_version must be 1 with only a jobs array")
    entries = manifest.get("jobs")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_BATCH_JOBS:
        raise QueueCompatibilityError(f"Batch manifest must contain 1 to {MAX_BATCH_JOBS} jobs")
    required = {"key", "resume_data", "keywords", "review_receipt"}
    optional = {"requirements", "requirements_receipt"}
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not required <= set(entry) or set(entry) - required - optional:
            raise QueueCompatibilityError(f"Batch job {index + 1} has an invalid schema")
        if bool(entry.get("requirements")) != bool(entry.get("requirements_receipt")):
            raise QueueCompatibilityError(f"Batch job {index + 1} must provide both requirement review files or neither")
        key = entry.get("key")
        if not isinstance(key, str) or not key or len(key) > 256 or any(ord(ch) < 32 for ch in key):
            raise QueueCompatibilityError(f"Batch job {index + 1} has an invalid queue key")
        if key in seen:
            raise QueueCompatibilityError("Batch manifest contains duplicate queue keys")
        seen.add(key)
        row = {"key": key}
        for field in ("resume_data", "keywords", "review_receipt"):
            value = entry.get(field)
            if not isinstance(value, str) or not value or not Path(value).expanduser().is_absolute():
                raise QueueCompatibilityError(f"Batch job {index + 1} field {field} must be an absolute path")
            row[field] = value
        for field in optional:
            if field not in entry:
                continue
            value = entry[field]
            if not isinstance(value, str) or not value or not Path(value).expanduser().is_absolute():
                raise QueueCompatibilityError(f"Batch job {index + 1} field {field} must be an absolute path")
            row[field] = value
        normalized.append(row)
    return normalized


def analyze_queue_batch(
    *,
    queue_path_value: str,
    manifest_value: str,
    persist: bool = False,
    score_runner: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze a private manifest sequentially; never submits or reorders jobs."""
    queue_path = _queue_path(queue_path_value)
    revision = _pinned_revision()
    rows = _load_batch_manifest(manifest_value)
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            report = analyze_queue_job(
                queue_path_value=str(queue_path),
                key=row["key"],
                resume_data_value=row["resume_data"],
                keywords_value=row["keywords"],
                receipt_value=row["review_receipt"],
                requirements_value=row.get("requirements"),
                requirements_receipt_value=row.get("requirements_receipt"),
                persist=persist,
                score_runner=score_runner,
                expected_revision=revision,
            )
            results.append({"queue_job_key": row["key"], "status": "ANALYZED", "report": report})
        except QueueCompatibilityError as exc:
            results.append({
                "queue_job_key": row["key"],
                "status": "UNVERIFIABLE",
                "error_code": str(exc),
            })
    analyzed_count = sum(result["status"] == "ANALYZED" for result in results)
    status = "ANALYZED" if analyzed_count == len(results) else "PARTIAL" if analyzed_count else "UNVERIFIABLE"
    return {
        "schema_version": 1,
        "status": status,
        "sequential": True,
        "persisted": persist,
        "analyzed_count": analyzed_count,
        "unverifiable_count": len(results) - analyzed_count,
        "jobs": results,
    }


def report_is_current(queue_path_value: str | Path, key: str, job: dict[str, Any], report: dict[str, Any]) -> bool:
    """Show an advisory marker only while all local inputs still match the approved analysis."""
    try:
        queue_path = _queue_path(queue_path_value)
        if not isinstance(job, dict) or not isinstance(report, dict):
            return False
        current_queue = _read_queue(queue_path)
        current_job = current_queue.get("vagas", {}).get(key)
        if (
            not isinstance(current_job, dict)
            or current_job.get("status") != "nova"
            or current_job.get(REPORT_FIELD) != report
            or current_job.get("titulo") != job.get("titulo")
            or current_job.get("url") != job.get("url")
            or current_job.get("job_description_id") != job.get("job_description_id")
            or current_job.get("job_description_sha256") != job.get("job_description_sha256")
            or current_job.get("job_description_id") != description_cache_id(key)
            or current_job.get("job_description_sha256") != report.get("job_description_sha256")
        ):
            return False
        if (
            report.get("schema_version") != 1
            or report.get("status") != "ANALYZED"
            or report.get("heuristic_only") is not True
            or report.get("queue_job_key") != key
            or report.get("title") != job.get("titulo")
            or report.get("job_url_sha256") != _sha256(str(job.get("url") or "").encode("utf-8"))
            or not HASH_RE.fullmatch(str(report.get("job_description_sha256") or ""))
            or not HASH_RE.fullmatch(str(report.get("profile_sha256") or ""))
        ):
            return False
        analyzed = datetime.fromisoformat(report.get("analyzed_at", ""))
        if analyzed.tzinfo is None or datetime.now().astimezone() - analyzed > MAX_REPORT_AGE or analyzed > datetime.now().astimezone() + timedelta(minutes=5):
            return False
        path = _sidecar_path(queue_path, key)
        record = _read_private_sidecar(path)
        if not isinstance(record, dict) or record != _sidecar_record_from_report(record, queue_path, key, report):
            return False
        if record.get("report_sha256") != _sha256(_canonical_json(report)):
            return False
        job_path, job_bytes = _read_file(record["job_path"], "Cached job description", MAX_DESCRIPTION_BYTES)
        keywords_path, keyword_bytes, keywords, receipt_path, receipt_bytes = _validate_keywords(
            description_sha=_sha256(job_bytes),
            title=report["title"],
            keywords_path=record["keywords_path"],
            receipt_path=record["receipt_path"],
        )
        profile_path, profile_bytes, _profile_data = _load_object(
            record["profile_path"], "ResumeData", MAX_PROFILE_BYTES, private=True
        )
        inputs_current = (
            str(job_path) == record["job_path"]
            and str(keywords_path) == record["keywords_path"]
            and str(receipt_path) == record["receipt_path"]
            and str(profile_path) == record["profile_path"]
            and _sha256(job_bytes) == report["job_description_sha256"]
            and _sha256(keyword_bytes) == report["keywords_sha256"]
            and _sha256(receipt_bytes) == report["review_receipt_sha256"]
            and _sha256(profile_bytes) == report["profile_sha256"]
        )
        requirement_review = report.get("requirements_review")
        if requirement_review is not None:
            if not isinstance(requirement_review, dict):
                return False
            if requirement_review.get("status") == "NOT_REVIEWED":
                if any(key in record for key in (
                    "requirements_path", "requirements_receipt_path",
                    "requirements_sha256", "requirements_receipt_sha256",
                )):
                    return False
            elif requirement_review.get("status") == "APPROVED":
                requirement_path = record.get("requirements_path")
                requirement_receipt_path = record.get("requirements_receipt_path")
                if not isinstance(requirement_path, str) or not isinstance(requirement_receipt_path, str):
                    return False
                (
                    resolved_assessment, assessment_bytes,
                    resolved_requirement_receipt, requirement_receipt_bytes,
                    current_requirement_summary,
                ) = _validate_requirement_review(
                    job_bytes=job_bytes, title=report["title"], profile_bytes=profile_bytes,
                    assessment_value=requirement_path,
                    receipt_value=requirement_receipt_path,
                )
                inputs_current = inputs_current and (
                    str(resolved_assessment) == requirement_path
                    and str(resolved_requirement_receipt) == requirement_receipt_path
                    and _sha256(assessment_bytes) == requirement_review.get("assessment_sha256")
                    and _sha256(requirement_receipt_bytes) == requirement_review.get("receipt_sha256")
                    and current_requirement_summary == requirement_review
                )
            else:
                return False
        revision = report.get("resume_matcher_revision")
        return inputs_current and isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision) is not None
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError, QueueCompatibilityError):
        return False


def _sidecar_record_from_report(record: dict[str, Any], queue_path: Path, key: str, report: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "queue_path_sha256": _sha256(str(queue_path).encode("utf-8")),
        "queue_job_key": key,
        "report_sha256": _sha256(_canonical_json(report)),
        "job_path": record.get("job_path"),
        "keywords_path": record.get("keywords_path"),
        "receipt_path": record.get("receipt_path"),
        "profile_path": record.get("profile_path"),
        "job_description_sha256": report.get("job_description_sha256"),
        "keywords_sha256": report.get("keywords_sha256"),
        "review_receipt_sha256": report.get("review_receipt_sha256"),
        "profile_sha256": report.get("profile_sha256"),
        "title": report.get("title"),
        "job_url_sha256": report.get("job_url_sha256"),
    }
    requirements_review = report.get("requirements_review")
    if isinstance(requirements_review, dict) and requirements_review.get("status") == "APPROVED":
        expected.update({
            "requirements_path": record.get("requirements_path"),
            "requirements_receipt_path": record.get("requirements_receipt_path"),
            "requirements_sha256": requirements_review.get("assessment_sha256"),
            "requirements_receipt_sha256": requirements_review.get("receipt_sha256"),
        })
    return expected


def _default_queue_path() -> Path:
    try:
        import descobrir

        return Path(descobrir.Ctx().fila_path).resolve(strict=True)
    except Exception as exc:
        raise QueueCompatibilityError("Could not resolve the active discovery queue") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    describe = subparsers.add_parser("description", help="show the cached description path for a triaged job")
    describe.add_argument("--key", required=True, help="stable queue key")
    describe.add_argument("--queue", help="absolute queue path; defaults to the active profile queue")
    analyze = subparsers.add_parser("analyze", help="score an explicitly selected queue job")
    analyze.add_argument("--key", required=True, help="stable queue key")
    analyze.add_argument("--queue", help="absolute queue path; defaults to the active profile queue")
    analyze.add_argument("--resume-data", required=True, help="absolute private ResumeData JSON file")
    analyze.add_argument("--keywords", required=True, help="approved JobKeywords JSON file")
    analyze.add_argument("--review-receipt", required=True, help="approval receipt emitted by job_keyword_proposal.py")
    analyze.add_argument("--requirements", help="optional hash-bound human-reviewed non-technical requirements assessment")
    analyze.add_argument("--requirements-receipt", help="receipt for the optional requirements assessment")
    analyze.add_argument("--persist", action="store_true", help="store the advisory report in the local discovery queue")
    analyze_batch = subparsers.add_parser("analyze-batch", help="analyze up to 50 reviewed queue jobs sequentially")
    analyze_batch.add_argument("--queue", help="absolute queue path; defaults to the active profile queue")
    analyze_batch.add_argument("--manifest", required=True, help="private JSON manifest with per-job profile, keyword and optional requirement review paths")
    analyze_batch.add_argument("--persist", action="store_true", help="persist successful advisory reports to their queue jobs")
    args = parser.parse_args(argv)
    try:
        queue_path = _queue_path(args.queue) if args.queue else _default_queue_path()
        if args.command == "analyze-batch":
            result = analyze_queue_batch(
                queue_path_value=str(queue_path),
                manifest_value=args.manifest,
                persist=args.persist,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["status"] == "ANALYZED" else 1
        queue = _read_queue(queue_path)
        job = _selected_job(queue, args.key)
        if args.command == "description":
            path = description_path_for(queue_path, args.key)
            resolved, raw = _read_file(path, "Cached job description", MAX_DESCRIPTION_BYTES)
            result = {
                "status": "READY",
                "key": args.key,
                "title": job["titulo"],
                "description_path": str(resolved),
                "job_description_sha256": _sha256(raw),
            }
            if (
                job.get("job_description_id") != description_cache_id(args.key)
                or job.get("job_description_sha256") != result["job_description_sha256"]
            ):
                raise QueueCompatibilityError("Cached description differs from the discovery triage result")
        else:
            result = analyze_queue_job(
                queue_path_value=str(queue_path),
                key=args.key,
                resume_data_value=args.resume_data,
                keywords_value=args.keywords,
                receipt_value=args.review_receipt,
                requirements_value=args.requirements,
                requirements_receipt_value=args.requirements_receipt,
                persist=args.persist,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except QueueCompatibilityError as exc:
        print(json.dumps({"status": "UNVERIFIABLE", "error_code": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
