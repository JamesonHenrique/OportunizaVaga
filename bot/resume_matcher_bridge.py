#!/usr/bin/env python3
"""Small, local-only adapter for Resume-Matcher's structured CLI.

The existing OportunizaVaga generator and factual/keyword gates remain the
source of truth. This adapter adds a second, independent PDF parse check and a
deterministic draft-to-job keyword score. It never invokes an LLM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
PARSE_TIMEOUT_SECONDS = 60
SCORE_TIMEOUT_SECONDS = 60
APPROVED = "APPROVED"
REJECTED = "REJECTED"
UNVERIFIABLE = "UNVERIFIABLE"
NEEDS_REVIEW = "NEEDS_REVIEW"
MANIFEST_SCHEMA_VERSION = 1
VERIFIER_POLICY_VERSION = 1


class BridgeError(Exception):
    """A local configuration, input, or Resume-Matcher CLI failure."""


def _data_dir() -> Path:
    configured = os.environ.get("OV_RESUME_MATCHER_DATA_DIR", "").strip()
    path = Path(configured).expanduser() if configured else (
        Path.home() / ".local" / "share" / "oportunizavaga" / "resume-matcher"
    )
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BridgeError("Resume-Matcher data directory is unavailable") from exc
    if not resolved.is_dir():
        raise BridgeError("Resume-Matcher data path is not a directory")
    if os.name == "posix" and resolved.stat().st_mode & 0o077:
        raise BridgeError("Resume-Matcher data directory must be private to the current user")
    return resolved


def _command() -> tuple[list[str], Path]:
    """Resolve an executable without invoking a shell or inheriting credentials."""
    cli = os.environ.get("OV_RESUME_MATCHER_CLI", "").strip()
    backend = os.environ.get("OV_RESUME_MATCHER_BACKEND_DIR", "").strip()
    if cli and backend:
        raise BridgeError("Configure only one of OV_RESUME_MATCHER_CLI or OV_RESUME_MATCHER_BACKEND_DIR")

    if cli:
        executable = Path(cli).expanduser()
        if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
            raise BridgeError("OV_RESUME_MATCHER_CLI must be an absolute executable path")
        return [str(executable.resolve())], _data_dir()

    if backend:
        project = Path(backend).expanduser()
        if not project.is_absolute() or not (project / "pyproject.toml").is_file():
            raise BridgeError("OV_RESUME_MATCHER_BACKEND_DIR must be an absolute backend project directory")
        uv = shutil.which("uv")
        if not uv:
            raise BridgeError("uv is required for OV_RESUME_MATCHER_BACKEND_DIR")
        return [uv, "run", "--no-sync", "--project", str(project.resolve()), "resume-matcher"], _data_dir()

    executable = shutil.which("resume-matcher")
    if executable:
        return [executable], _data_dir()
    raise BridgeError("Resume-Matcher CLI is not configured")


def _safe_environment(data_dir: Path) -> dict[str, str]:
    """Pass only runtime basics; API keys and unrelated candidate data stay out."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "DATA_DIR": str(data_dir),
        "LOG_LEVEL": "WARNING",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("LANG", "LC_ALL", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _run_tool(tool: str, arguments: list[str], timeout: int) -> dict[str, Any]:
    command, data_dir = _command()
    try:
        result = subprocess.run(
            [*command, tool, *arguments],
            cwd=data_dir,
            env=_safe_environment(data_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BridgeError("Resume-Matcher timed out") from exc
    except OSError as exc:
        raise BridgeError("Resume-Matcher could not be started") from exc
    if result.returncode != 0:
        # Do not forward stderr: it may contain local paths or user-supplied text.
        raise BridgeError("Resume-Matcher returned an error")
    try:
        value = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BridgeError("Resume-Matcher returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise BridgeError("Resume-Matcher returned an unexpected result")
    return value


def _validate_pdf(path_value: str) -> tuple[Path, str]:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        raise BridgeError("PDF path must be absolute")
    try:
        path = path.resolve(strict=True)
        if not path.is_file():
            raise BridgeError("PDF is not a regular file")
        if path.suffix.lower() != ".pdf":
            raise BridgeError("Only PDF files can be checked before attachment")
        size = path.stat().st_size
        if size <= 0 or size > MAX_DOCUMENT_BYTES:
            raise BridgeError("PDF is empty or exceeds the 4 MiB parser limit")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            header = stream.read(5)
            if header != b"%PDF-":
                raise BridgeError("File does not have a PDF signature")
            digest.update(header)
            for chunk in iter(lambda: stream.read(128 * 1024), b""):
                digest.update(chunk)
        return path, digest.hexdigest()
    except OSError as exc:
        raise BridgeError("PDF is unavailable") from exc


def _evaluate_report(report: dict[str, Any], digest: str, elapsed_ms: int) -> dict[str, Any]:
    extractability = report.get("extractability")
    score = report.get("overall_score")
    pages = report.get("page_count")
    checks = report.get("checks")
    if (
        extractability not in {"full", "partial", "none"}
        or isinstance(score, bool)
        or not isinstance(score, int)
        or not 0 <= score <= 100
        or isinstance(pages, bool)
        or not isinstance(pages, int)
        or pages < 1
        or not isinstance(checks, list)
        or not checks
    ):
        raise BridgeError("Resume-Matcher report is incomplete")

    failed: list[str] = []
    warned: list[str] = []
    high_failures: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            raise BridgeError("Resume-Matcher report has an invalid check")
        check_id, status, severity = check.get("id"), check.get("status"), check.get("severity")
        if (
            not isinstance(check_id, str)
            or status not in {"pass", "warn", "fail"}
            or severity not in {"high", "medium", "low"}
        ):
            raise BridgeError("Resume-Matcher report has an invalid check")
        if status == "fail":
            failed.append(check_id)
            if severity == "high":
                high_failures.append(check_id)
        elif status == "warn":
            warned.append(check_id)

    if extractability == "none":
        status = UNVERIFIABLE
    elif high_failures:
        status = REJECTED
    elif extractability != "full" or failed or warned or score < 80 or pages > 2:
        status = NEEDS_REVIEW
    else:
        status = APPROVED

    return {
        "status": status,
        "overall_score": score,
        "page_count": pages,
        "extractability": extractability,
        "failed_checks": failed,
        "warning_checks": warned,
        "sha256": digest,
        "elapsed_ms": elapsed_ms,
        "heuristic_only": True,
    }


def _hash_input(path_value: str, label: str, limit: int) -> str:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        raise BridgeError(f"{label} path must be absolute")
    try:
        path = path.resolve(strict=True)
        if not path.is_file() or path.stat().st_size <= 0 or path.stat().st_size > limit:
            raise BridgeError(f"{label} is missing, empty, or too large")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(128 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise BridgeError(f"{label} is unavailable") from exc


def _manifest_root(value: str, create: bool) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise BridgeError("Manifest directory must be an absolute path")
    try:
        if create:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = path.resolve(strict=True)
    except OSError as exc:
        raise BridgeError("Verification manifest directory is unavailable") from exc
    if not root.is_dir():
        raise BridgeError("Verification manifest path is not a directory")
    if os.name == "posix":
        info = root.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise BridgeError("Verification manifest directory must be private to the current user")
    return root


def _manifest_id(job_digest: str, pdf_digest: str) -> str:
    return f"{job_digest}-{pdf_digest}"


def _resume_matcher_revision() -> str:
    revision = os.environ.get("OV_RESUME_MATCHER_REVISION", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise BridgeError("OV_RESUME_MATCHER_REVISION must be the pinned 40-character Git commit")
    return revision


def _manifest_record(verdict: dict[str, Any], revision: str) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "verifier_policy_version": VERIFIER_POLICY_VERSION,
        "status": verdict["status"],
        "job_description_sha256": verdict["job_description_sha256"],
        "pdf_sha256": verdict["sha256"],
        "resume_matcher_revision": revision,
        "overall_score": verdict["overall_score"],
        "page_count": verdict["page_count"],
        "extractability": verdict["extractability"],
        "failed_checks": verdict["failed_checks"],
        "warning_checks": verdict["warning_checks"],
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _write_manifest(root: Path, record: dict[str, Any]) -> str:
    """Create one immutable, owner-only manifest per exact job/PDF hash pair."""
    if record.get("status") != APPROVED:
        raise BridgeError("Only an approved verification can be recorded")
    manifest_id = _manifest_id(record["job_description_sha256"], record["pdf_sha256"])
    destination = root / f"{manifest_id}.json"
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    temporary_path: Path | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".resume-matcher-", suffix=".tmp", dir=root)
        temporary_path = Path(temporary)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, destination)
            if os.name == "posix":
                dir_fd = os.open(root, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file():
                raise BridgeError("Existing verification manifest is not a regular file")
            if os.name == "posix":
                info = destination.stat()
                if info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise BridgeError("Existing verification manifest is not private to the current user")
            existing = json.loads(destination.read_text(encoding="utf-8"))
            comparable = dict(record)
            comparable.pop("verified_at", None)
            if not isinstance(existing, dict):
                raise BridgeError("Existing verification manifest is invalid")
            existing.pop("verified_at", None)
            if existing != comparable:
                raise BridgeError("Existing verification manifest conflicts with this result")
    except BridgeError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError("Could not persist the verification manifest") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return manifest_id


def verify_manifest(pdf_value: str, announcement_value: str, manifest_dir: str) -> dict[str, Any]:
    """Confirm the exact job/PDF pair has a current-policy approved manifest."""
    path, pdf_digest = _validate_pdf(pdf_value)
    job_digest = _hash_input(announcement_value, "Job description", MAX_JSON_BYTES)
    root = _manifest_root(manifest_dir, create=False)
    manifest_id = _manifest_id(job_digest, pdf_digest)
    manifest_path = root / f"{manifest_id}.json"
    if manifest_path.is_symlink():
        raise BridgeError("Verification manifest must not be a symbolic link")
    try:
        if not manifest_path.is_file():
            raise BridgeError("Matching verification manifest is missing or invalid")
        if os.name == "posix":
            info = manifest_path.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > MAX_JSON_BYTES:
                raise BridgeError("Verification manifest is not private to the current user")
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except BridgeError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError("Matching verification manifest is missing or invalid") from exc
    expected_revision = _resume_matcher_revision()
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or record.get("verifier_policy_version") != VERIFIER_POLICY_VERSION
        or record.get("status") != APPROVED
        or record.get("job_description_sha256") != job_digest
        or record.get("pdf_sha256") != pdf_digest
        or record.get("resume_matcher_revision") != expected_revision
        or record.get("extractability") != "full"
        or isinstance(record.get("overall_score"), bool)
        or not isinstance(record.get("overall_score"), int)
        or not 80 <= record.get("overall_score", 0) <= 100
        or isinstance(record.get("page_count"), bool)
        or not isinstance(record.get("page_count"), int)
        or not 1 <= record.get("page_count", 99) <= 2
        or record.get("failed_checks") != []
        or record.get("warning_checks") != []
        or not isinstance(record.get("verified_at"), str)
    ):
        raise BridgeError("Verification manifest does not approve this job/PDF pair")
    try:
        verified_at = datetime.fromisoformat(record["verified_at"])
    except ValueError as exc:
        raise BridgeError("Verification manifest timestamp is invalid") from exc
    if verified_at.tzinfo is None or verified_at.utcoffset() is None:
        raise BridgeError("Verification manifest timestamp must include a timezone")
    if _validate_pdf(str(path))[1] != pdf_digest or _hash_input(announcement_value, "Job description", MAX_JSON_BYTES) != job_digest:
        raise BridgeError("Job description or PDF changed during manifest verification")
    return {
        "status": APPROVED,
        "manifest_id": manifest_id,
        "job_description_sha256": job_digest,
        "pdf_sha256": pdf_digest,
        "resume_matcher_revision": record["resume_matcher_revision"],
        "verifier_policy_version": record["verifier_policy_version"],
        "overall_score": record["overall_score"],
        "page_count": record["page_count"],
        "verified_at": record["verified_at"],
    }


def parse_check(
    pdf_value: str,
    announcement_value: str | None = None,
    manifest_dir: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    path, digest = _validate_pdf(pdf_value)
    job_digest = (
        _hash_input(announcement_value, "Job description", MAX_JSON_BYTES)
        if announcement_value
        else None
    )
    report = _run_tool("parse_check_file", [f"file_path={path}"], PARSE_TIMEOUT_SECONDS)
    verdict = _evaluate_report(report, digest, int((time.monotonic() - started) * 1000))
    verdict["job_description_sha256"] = job_digest
    if _validate_pdf(str(path))[1] != digest:
        raise BridgeError("PDF changed during Resume-Matcher parsing")
    if announcement_value and _hash_input(announcement_value, "Job description", MAX_JSON_BYTES) != job_digest:
        raise BridgeError("Job description changed during Resume-Matcher parsing")
    if verdict["status"] == APPROVED and manifest_dir:
        root = _manifest_root(manifest_dir, create=True)
        revision = _resume_matcher_revision()
        record = _manifest_record(verdict, revision)
        verdict["manifest_id"] = _write_manifest(root, record)
    return verdict


def _load_json_object(value: str, label: str) -> tuple[Path, dict[str, Any]]:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise BridgeError(f"{label} path must be absolute")
    try:
        path = path.resolve(strict=True)
        if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise BridgeError(f"{label} file is missing or exceeds the 1 MiB limit")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"{label} is not readable JSON") from exc
    if not isinstance(data, dict):
        raise BridgeError(f"{label} must be a JSON object")
    return path, data


def score_draft(resume_value: str, keywords_value: str) -> dict[str, Any]:
    resume_path, resume_data = _load_json_object(resume_value, "Resume data")
    keywords_path, keywords = _load_json_object(keywords_value, "Job keywords")
    if not resume_data or not (keywords.get("required_skills") or keywords.get("preferred_skills") or keywords.get("keywords")):
        raise BridgeError("Resume data and at least one job keyword are required")
    result = _run_tool(
        "score_resume",
        [f"resume_data:=@{resume_path}", f"keywords:=@{keywords_path}"],
        SCORE_TIMEOUT_SECONDS,
    )
    overall = result.get("overall_score")
    match = result.get("keyword_match_percentage")
    subscores = result.get("sub_scores")
    if (
        isinstance(overall, bool)
        or not isinstance(overall, (int, float))
        or not 0 <= overall <= 100
        or isinstance(match, bool)
        or not isinstance(match, (int, float))
        or not 0 <= match <= 100
        or not isinstance(subscores, dict)
    ):
        raise BridgeError("Resume-Matcher score result is incomplete")
    return {
        "heuristic_only": True,
        "overall_score": overall,
        "keyword_match_percentage": match,
        "sub_scores": subscores,
        "missing_keywords": result.get("missing_keywords", []),
        "injectable_keywords": result.get("injectable_keywords", []),
        "recommendations": result.get("recommendations", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    check = subparsers.add_parser("parse-check", help="check a PDF locally before attachment")
    check.add_argument("--pdf", required=True, help="absolute path to the generated PDF")
    check.add_argument("--announcement", help="absolute path to the exact job description used by the ATS gate")
    check.add_argument("--manifest-dir", help="absolute directory for an owner-only job/PDF verification manifest")
    verify = subparsers.add_parser("verify-manifest", help="verify a saved approval for an exact job/PDF pair")
    verify.add_argument("--pdf", required=True, help="absolute path to the generated PDF")
    verify.add_argument("--announcement", required=True, help="absolute path to the exact job description")
    verify.add_argument("--manifest-dir", required=True, help="absolute directory containing the manifest")
    score = subparsers.add_parser("score", help="score synthetic or selected resume JSON against job keywords")
    score.add_argument("--resume-data", required=True, help="absolute path to Resume Matcher ResumeData JSON")
    score.add_argument("--keywords", required=True, help="absolute path to Resume Matcher JobKeywords JSON")
    args = parser.parse_args(argv)

    try:
        if args.operation == "parse-check":
            result = parse_check(args.pdf, args.announcement, args.manifest_dir)
        elif args.operation == "verify-manifest":
            result = verify_manifest(args.pdf, args.announcement, args.manifest_dir)
        else:
            result = score_draft(args.resume_data, args.keywords)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if args.operation == "parse-check":
            return 0 if result["status"] == APPROVED else (2 if result["status"] == UNVERIFIABLE else 1)
        if args.operation == "verify-manifest":
            return 0
        return 0
    except BridgeError as exc:
        if args.operation in {"parse-check", "verify-manifest"}:
            result = {
                "status": UNVERIFIABLE,
                "overall_score": None,
                "page_count": None,
                "extractability": None,
                "failed_checks": [],
                "warning_checks": [],
                "sha256": None,
                "job_description_sha256": None,
                "error_code": str(exc),
                "heuristic_only": True,
            }
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 2
        print(json.dumps({"status": UNVERIFIABLE, "error_code": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
