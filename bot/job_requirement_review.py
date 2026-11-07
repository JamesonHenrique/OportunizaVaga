#!/usr/bin/env python3
"""Create hash-bound, human-reviewed assessments of non-technical job requirements.

This module proposes source spans using local deterministic cues only. It never
decides whether a candidate is eligible, calls an LLM, or executes job-ad text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_JOB_BYTES = 1024 * 1024
MAX_PROFILE_BYTES = 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_CANDIDATES = 250
MAX_MANUAL_REQUIREMENTS = 100
MAX_SOURCE_SPAN = 1200
MAX_EVIDENCE_REFS = 20
MAX_JOB_REQUIREMENT_FACTS = 16
MAX_JOB_REQUIREMENT_FACT_BYTES = 2048

CATEGORIES = {
    "availability",
    "compensation",
    "contract",
    "education",
    "experience",
    "language",
    "location",
    "modality",
    "certification",
    "seniority",
    "work_authorization",
    "other",
}
STATUSES = {"MET", "PARTIAL", "NOT_MET", "UNCONFIRMED"}
BARRIERS = {"PARTIAL", "NOT_MET", "UNCONFIRMED"}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_PROFILE_FACT_KEY_RE = re.compile(r"^[a-z][a-zA-Z0-9_]{0,39}$")

# Cues only locate text for review. They do not classify a requirement as
# mandatory and cannot establish candidate eligibility.
_CUES: dict[str, tuple[re.Pattern[str], ...]] = {
    "availability": (
        re.compile(r"\b(?:disponibilidade|availability|schedule|shift|turno|escala|in[ií]cio imediato|immediate start|start date|travel|viagens)\b", re.I),
    ),
    "compensation": (
        re.compile(r"\b(?:sal[aá]rio|remunera[cç][aã]o|salary|compensation|pay range|faixa salarial|bolsa|stipend)\b", re.I),
    ),
    "contract": (
        re.compile(r"\b(?:CLT|PJ|contractor|contract type|full.time|part.time|est[aá]gio|internship|apprentice|aprendiz|tempor[aá]rio)\b", re.I),
    ),
    "education": (
        re.compile(r"\b(?:diploma|degree|bachelor(?:'s)?|master(?:'s)?|bacharelado|licenciatura|gradua[cç][aã]o|ensino superior|curso superior|forma[cç][aã]o|enrolled in|currently pursuing|estar cursando)\b", re.I),
    ),
    "experience": (
        re.compile(r"\b(?:\d+\s*\+?\s*(?:years?|anos?)|anos? de experi[eê]ncia|years? of experience|experi[eê]ncia m[ií]nima|minimum experience|experience required)\b", re.I),
    ),
    "language": (
        re.compile(r"\b(?:idioma|language|ingl[eê]s|english|espanhol|spanish|portugu[eê]s|portuguese|fluent|fluency|proficient|proficiency|bilingual|bil[ií]ngue)\b", re.I),
    ),
    "location": (
        re.compile(r"\b(?:residir|resid[eê]ncia|morar|localizado|localizada|resid(?:e|es|ent|ency)|residence|based in|located in|work from|within \d+ (?:km|miles?))\b", re.I),
    ),
    "modality": (
        re.compile(r"\b(?:remoto|remota|remote|h[ií]brido|h[ií]brida|hybrid|presencial|onsite|on.site|office.based|telework)\b", re.I),
    ),
    "certification": (
        re.compile(r"\b(?:certifica[cç][aã]o|certificado|certification|certificate|license|licen[cç]a|registro profissional|professional registration)\b", re.I),
    ),
    "seniority": (
        re.compile(r"\b(?:junior|j[uú]nior|j[uú]nior|jr\.?|trainee|entry.level|associate|pleno|mid.level|senior|s[eê]nior|staff|principal)\b", re.I),
    ),
    "work_authorization": (
        re.compile(r"\b(?:authorized to work|work authorization|right to work|work permit|work visa|autoriza[cç][aã]o de trabalho|permiss[aã]o de trabalho|visto de trabalho)\b", re.I),
    ),
}
_REQUIRED_CUE = re.compile(
    r"\b(?:must|required|mandatory|minimum|at least|obrigat[oó]rio|obrigat[oó]ria|necess[aá]rio|necess[aá]ria|m[ií]nimo|m[ií]nima|deve|exigido|exigida|indispens[aá]vel)\b",
    re.I,
)


class RequirementReviewError(ValueError):
    """Invalid source, proposal, review, assessment or receipt."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _profile_refs(profile: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    summary = profile.get("summary")
    if isinstance(summary, str) and summary.strip():
        refs.append("summary")
    for field in ("workExperience", "personalProjects", "education"):
        rows = profile.get(field, [])
        if isinstance(rows, list):
            for index, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    continue
                has_heading = any(
                    isinstance(row.get(key), str) and row[key].strip()
                    for key in ("title", "company", "name", "role", "institution", "degree")
                )
                description = row.get("description")
                has_description = (
                    isinstance(description, str) and bool(description.strip())
                    or isinstance(description, list) and any(isinstance(value, str) and value.strip() for value in description)
                )
                if has_heading or has_description:
                    refs.append(f"{field}#{index}")
    additional = profile.get("additional", {})
    if isinstance(additional, dict):
        for key in ("technicalSkills", "languages", "certificationsTraining", "awards"):
            values = additional.get(key)
            if isinstance(values, list) and any(isinstance(value, str) and value.strip() for value in values):
                refs.append(f"additional.{key}")
    custom = profile.get("customSections", {})
    if isinstance(custom, dict):
        for index, section in enumerate(custom.values(), start=1):
            if isinstance(section, dict) and section.get("sectionType") == "stringList":
                values = section.get("strings")
                if isinstance(values, list) and any(isinstance(value, str) and value.strip() for value in values):
                    refs.append(f"customSections#{index}")
    job_requirements = profile.get("jobRequirements", {})
    if isinstance(job_requirements, dict):
        for key, value in sorted(job_requirements.items()):
            values = value if isinstance(value, list) else [value]
            if any(isinstance(item, str) and item.strip() for item in values):
                refs.append(f"jobRequirements.{key}")
    return refs


def _parse_profile(profile_bytes: bytes) -> dict[str, Any]:
    if not isinstance(profile_bytes, bytes) or not profile_bytes or len(profile_bytes) > MAX_PROFILE_BYTES:
        raise RequirementReviewError("ResumeData is empty or exceeds its size limit")
    try:
        profile = json.loads(profile_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RequirementReviewError("ResumeData is not valid UTF-8 JSON") from exc
    if not isinstance(profile, dict) or not profile:
        raise RequirementReviewError("ResumeData must be a non-empty JSON object")
    facts = profile.get("jobRequirements", {})
    if not isinstance(facts, dict) or len(facts) > MAX_JOB_REQUIREMENT_FACTS:
        raise RequirementReviewError("Job requirement context has an unsupported shape")
    for key, value in facts.items():
        if not isinstance(key, str) or not _PROFILE_FACT_KEY_RE.fullmatch(key):
            raise RequirementReviewError("Job requirement context contains an invalid fact key")
        values = value if isinstance(value, list) else [value]
        if not values or len(values) > 20 or any(
            not isinstance(item, str) or not item.strip() or len(item.encode("utf-8")) > MAX_JOB_REQUIREMENT_FACT_BYTES
            for item in values
        ):
            raise RequirementReviewError("Job requirement context contains an invalid fact value")
    return profile


def _suggested_required(text: str) -> bool:
    return bool(_REQUIRED_CUE.search(text))


def _candidate_id(category: str, start: int, end: int, quote: str) -> str:
    return "req-" + _sha256(f"{category}\0{start}\0{end}\0{quote}".encode("utf-8"))[:20]


def _source_spans(text: str, matches: list[re.Match[str]]) -> tuple[int, int, str]:
    first = min(match.start() for match in matches)
    last = max(match.end() for match in matches)
    line_start = text.rfind("\n", 0, first) + 1
    line_end = text.find("\n", last)
    if line_end < 0:
        line_end = len(text)
    while line_end > line_start and text[line_end - 1] == "\r":
        line_end -= 1
    if line_end - line_start <= MAX_SOURCE_SPAN:
        return line_start, line_end, text[line_start:line_end]
    start = max(line_start, first - MAX_SOURCE_SPAN // 3)
    end = min(line_end, max(last, start + MAX_SOURCE_SPAN))
    if end - start > MAX_SOURCE_SPAN:
        start = max(line_start, end - MAX_SOURCE_SPAN)
    return start, end, text[start:end]


def build_proposal(job_bytes: bytes, title: str, profile_bytes: bytes) -> dict[str, Any]:
    if not isinstance(job_bytes, bytes) or not job_bytes or len(job_bytes) > MAX_JOB_BYTES:
        raise RequirementReviewError("Job description is empty or exceeds its size limit")
    try:
        text = job_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise RequirementReviewError("Job description must be UTF-8") from exc
    if not isinstance(title, str) or not title.strip() or len(title) > 256 or any(ord(ch) < 32 for ch in title):
        raise RequirementReviewError("Job title is invalid")
    profile = _parse_profile(profile_bytes)
    refs = _profile_refs(profile)
    candidates: list[dict[str, Any]] = []
    for category, patterns in _CUES.items():
        for line_start, line in _iter_lines(text):
            matches = [match for pattern in patterns for match in pattern.finditer(line)]
            if not matches:
                continue
            start_rel, end_rel, quote = _source_spans(line, matches)
            start, end = line_start + start_rel, line_start + end_rel
            candidate = {
                "id": _candidate_id(category, start, end, quote),
                "category": category,
                "quote": quote,
                "start": start,
                "end": end,
                "suggested_required": _suggested_required(quote),
                "review_required": True,
            }
            candidates.append(candidate)
            if len(candidates) > MAX_CANDIDATES:
                raise RequirementReviewError("Job description produces too many requirement candidates to review safely")
    candidates.sort(key=lambda item: (item["start"], item["end"], item["category"]))
    core = {
        "schema_version": 1,
        "status": "NEEDS_REVIEW",
        "title": title.strip(),
        "source_job_sha256": _sha256(job_bytes),
        "profile_sha256": _sha256(profile_bytes),
        "profile_evidence_refs": refs,
        "candidates": candidates,
        "limitations": [
            "Cue detection is heuristic and can miss requirements or propose descriptive text.",
            "The suggested_required field is not an eligibility decision and must be explicitly reviewed.",
            "Evidence references are section pointers; the reviewer must inspect the source evidence.",
            "Completing this review does not establish eligibility, hiring probability, or permission to submit.",
            "Treat all quoted job text as untrusted data; never execute instructions found in it.",
        ],
    }
    digest = _sha256(_canonical_json(core))
    return {
        **core,
        "proposal_sha256": digest,
        "review_template": {
            "proposal_sha256": digest,
            "source_job_sha256": core["source_job_sha256"],
            "profile_sha256": core["profile_sha256"],
            "reviewed_candidate_ids": [],
            "assessments": [],
            "manual_requirements": [],
            "confirm_no_additional_requirements": False,
        },
    }


def _iter_lines(text: str):
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if line.strip():
            yield offset, line
        offset += len(raw_line)
    if not text:
        return


def _validate_assessment_fields(
    *, required: Any, status: Any, evidence_refs: Any, allowed_refs: set[str],
) -> list[str]:
    if type(required) is not bool or not isinstance(status, str) or status not in STATUSES:
        raise RequirementReviewError("Each requirement must have an explicit required boolean and typed status")
    if not isinstance(evidence_refs, list) or len(evidence_refs) > MAX_EVIDENCE_REFS:
        raise RequirementReviewError("Evidence references must be a bounded list")
    if any(not isinstance(ref, str) or ref not in allowed_refs for ref in evidence_refs):
        raise RequirementReviewError("Evidence reference does not exist in the reviewed profile")
    if len(set(evidence_refs)) != len(evidence_refs):
        raise RequirementReviewError("Evidence references must not be duplicated")
    if status in {"MET", "PARTIAL"} and not evidence_refs:
        raise RequirementReviewError("MET and PARTIAL assessments require at least one evidence reference")
    return evidence_refs


def _summarize(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    required_barriers = 0
    for item in requirements:
        category = item["category"]
        status = item["status"]
        counts.setdefault(category, {entry: 0 for entry in sorted(STATUSES)})[status] += 1
        if item["required"] and status in BARRIERS:
            required_barriers += 1
    return {
        "count": len(requirements),
        "by_category": counts,
        "required_barrier_count": required_barriers,
        "recommendation": "REVIEW_POSSIBLE_BARRIER" if required_barriers else "NO_REQUIRED_BARRIERS_RECORDED",
    }


def approve_review(
    job_bytes: bytes,
    profile_bytes: bytes,
    proposal: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    title = proposal.get("title") if isinstance(proposal, dict) else ""
    expected = build_proposal(job_bytes, title, profile_bytes)
    if proposal != expected:
        raise RequirementReviewError("Proposal does not match the current job description, title, or profile")
    if not isinstance(review, dict) or set(review) != {
        "proposal_sha256", "source_job_sha256", "profile_sha256", "reviewed_candidate_ids",
        "assessments", "manual_requirements", "confirm_no_additional_requirements",
    }:
        raise RequirementReviewError("Review file has an unsupported shape")
    if (
        review.get("proposal_sha256") != expected["proposal_sha256"]
        or review.get("source_job_sha256") != expected["source_job_sha256"]
        or review.get("profile_sha256") != expected["profile_sha256"]
    ):
        raise RequirementReviewError("Review file references a different proposal, job, or profile")
    candidates = expected["candidates"]
    candidate_ids = [item["id"] for item in candidates]
    reviewed_ids = review.get("reviewed_candidate_ids")
    if not isinstance(reviewed_ids, list) or any(not isinstance(value, str) for value in reviewed_ids):
        raise RequirementReviewError("Review must list every detected candidate that was inspected")
    if len(set(reviewed_ids)) != len(reviewed_ids) or set(reviewed_ids) != set(candidate_ids):
        raise RequirementReviewError("Every detected candidate must be reviewed exactly once")
    assessments = review.get("assessments")
    if not isinstance(assessments, list) or len(assessments) != len(candidates):
        raise RequirementReviewError("Review must contain one assessment for every detected candidate")
    refs = set(expected["profile_evidence_refs"])
    candidates_by_id = {item["id"]: item for item in candidates}
    seen_ids: set[str] = set()
    requirements: list[dict[str, Any]] = []
    for assessment in assessments:
        if not isinstance(assessment, dict) or set(assessment) != {"candidate_id", "required", "status", "evidence_refs"}:
            raise RequirementReviewError("Each assessment must contain candidate_id, required, status and evidence_refs")
        candidate_id = assessment["candidate_id"]
        if not isinstance(candidate_id, str):
            raise RequirementReviewError("Assessment candidate_id must be a string")
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None or candidate_id in seen_ids:
            raise RequirementReviewError("Assessment references an unknown or duplicate candidate")
        seen_ids.add(candidate_id)
        evidence_refs = _validate_assessment_fields(
            required=assessment["required"], status=assessment["status"],
            evidence_refs=assessment["evidence_refs"], allowed_refs=refs,
        )
        requirements.append({
            "id": candidate_id,
            "category": candidate["category"],
            "required": assessment["required"],
            "status": assessment["status"],
            "evidence_refs": evidence_refs,
            "source_start": candidate["start"],
            "source_end": candidate["end"],
            "source_span_sha256": _sha256(candidate["quote"].encode("utf-8")),
            "manual": False,
        })
    if seen_ids != set(candidate_ids):
        raise RequirementReviewError("Detected candidates are missing assessments")

    manual = review.get("manual_requirements")
    if not isinstance(manual, list) or len(manual) > MAX_MANUAL_REQUIREMENTS:
        raise RequirementReviewError("Manual requirements must be a bounded list")
    text = job_bytes.decode("utf-8")
    manual_spans: set[tuple[int, int, str]] = set()
    for item in manual:
        if not isinstance(item, dict) or set(item) != {
            "text", "start", "end", "category", "required", "status", "evidence_refs",
        }:
            raise RequirementReviewError("Manual requirements need exact source spans and a complete assessment")
        phrase, start, end, category = item["text"], item["start"], item["end"], item["category"]
        if (
            not isinstance(phrase, str) or not phrase.strip() or len(phrase) > MAX_SOURCE_SPAN
            or isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or not 0 <= start < end <= len(text) or text[start:end] != phrase
            or not isinstance(category, str) or category not in CATEGORIES
        ):
            raise RequirementReviewError("Manual requirement must reference an exact source span and supported category")
        span_key = (start, end, category)
        if span_key in manual_spans:
            raise RequirementReviewError("Manual requirement source span is duplicated")
        manual_spans.add(span_key)
        evidence_refs = _validate_assessment_fields(
            required=item["required"], status=item["status"],
            evidence_refs=item["evidence_refs"], allowed_refs=refs,
        )
        requirements.append({
            "id": _candidate_id(category, start, end, phrase),
            "category": category,
            "required": item["required"],
            "status": item["status"],
            "evidence_refs": evidence_refs,
            "source_start": start,
            "source_end": end,
            "source_span_sha256": _sha256(phrase.encode("utf-8")),
            "manual": True,
        })

    confirm_none = review.get("confirm_no_additional_requirements")
    if type(confirm_none) is not bool:
        raise RequirementReviewError("confirm_no_additional_requirements must be a boolean")
    if not candidates and not manual and confirm_none is not True:
        raise RequirementReviewError("When no cues were found, explicitly confirm that the full description was reviewed")
    if (candidates or manual) and confirm_none:
        raise RequirementReviewError("Do not confirm no requirements when reviewed or manual requirements are present")

    summary = _summarize(requirements)
    review_sha = _sha256(_canonical_json(review))
    assessment = {
        "schema_version": 1,
        "status": "APPROVED",
        "review_complete": True,
        "title": expected["title"],
        "source_job_sha256": expected["source_job_sha256"],
        "profile_sha256": expected["profile_sha256"],
        "proposal_sha256": expected["proposal_sha256"],
        "review_sha256": review_sha,
        "requirements": requirements,
        **summary,
        "limitations": [
            "APPROVED means the local review is complete, not that the candidate is eligible or likely to be hired.",
            "Evidence references are pointers; the human reviewer remains responsible for factual interpretation.",
            "The proposal can miss requirements; inspect the full official description and add exact manual spans.",
            "Any required status other than MET needs review and must not be treated as a pass.",
        ],
    }
    receipt = {
        "schema_version": 1,
        "status": "APPROVED",
        "review_complete": True,
        "source_job_sha256": expected["source_job_sha256"],
        "profile_sha256": expected["profile_sha256"],
        "proposal_sha256": expected["proposal_sha256"],
        "review_sha256": review_sha,
        "assessment_sha256": _sha256(_canonical_json(assessment)),
        "reviewed_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return assessment, receipt


def validate_approved(
    job_bytes: bytes,
    profile_bytes: bytes,
    assessment: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(assessment, dict) or not isinstance(receipt, dict):
        raise RequirementReviewError("Assessment and receipt must be JSON objects")
    assessment_keys = {
        "schema_version", "status", "review_complete", "title", "source_job_sha256",
        "profile_sha256", "proposal_sha256", "review_sha256", "requirements", "count",
        "by_category", "required_barrier_count", "recommendation", "limitations",
    }
    receipt_keys = {
        "schema_version", "status", "review_complete", "source_job_sha256", "profile_sha256",
        "proposal_sha256", "review_sha256", "assessment_sha256", "reviewed_at_local",
    }
    if set(assessment) != assessment_keys or set(receipt) != receipt_keys:
        raise RequirementReviewError("Assessment or receipt contains unsupported fields")
    try:
        proposal = build_proposal(job_bytes, assessment.get("title", ""), profile_bytes)
    except RequirementReviewError:
        raise
    if (
        assessment.get("schema_version") != 1
        or assessment.get("status") != "APPROVED"
        or assessment.get("review_complete") is not True
        or assessment.get("source_job_sha256") != proposal["source_job_sha256"]
        or assessment.get("profile_sha256") != proposal["profile_sha256"]
        or assessment.get("proposal_sha256") != proposal["proposal_sha256"]
        or not isinstance(assessment.get("review_sha256"), str)
        or not HASH_RE.fullmatch(assessment["review_sha256"])
    ):
        raise RequirementReviewError("Assessment is stale, incomplete, or bound to another job/profile")
    reqs = assessment.get("requirements")
    if not isinstance(reqs, list) or len(reqs) > MAX_CANDIDATES + MAX_MANUAL_REQUIREMENTS:
        raise RequirementReviewError("Assessment requirements are invalid")
    refs = set(proposal["profile_evidence_refs"])
    candidates = {candidate["id"]: candidate for candidate in proposal["candidates"]}
    seen: set[str] = set()
    manual_count = 0
    allowed_keys = {
        "id", "category", "required", "status", "evidence_refs", "source_start",
        "source_end", "source_span_sha256", "manual",
    }
    source_text = job_bytes.decode("utf-8")
    for item in reqs:
        if not isinstance(item, dict) or set(item) != allowed_keys:
            raise RequirementReviewError("Assessment contains an invalid requirement shape")
        identifier = item["id"]
        if not isinstance(identifier, str) or identifier in seen:
            raise RequirementReviewError("Assessment contains duplicate or invalid requirement IDs")
        seen.add(identifier)
        if item["category"] not in CATEGORIES or type(item["manual"]) is not bool:
            raise RequirementReviewError("Assessment category or manual marker is invalid")
        _validate_assessment_fields(
            required=item["required"], status=item["status"],
            evidence_refs=item["evidence_refs"], allowed_refs=refs,
        )
        start, end = item["source_start"], item["source_end"]
        if (
            isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or not 0 <= start < end <= len(source_text)
            or not isinstance(item["source_span_sha256"], str)
            or _sha256(source_text[start:end].encode("utf-8")) != item["source_span_sha256"]
        ):
            raise RequirementReviewError("Assessment source span no longer matches the announcement")
        candidate = candidates.get(identifier)
        if candidate:
            if (
                item["manual"] is True or item["category"] != candidate["category"]
                or start != candidate["start"] or end != candidate["end"]
            ):
                raise RequirementReviewError("Detected requirement was altered after review")
        else:
            manual_count += 1
            if item["manual"] is not True or identifier != _candidate_id(item["category"], start, end, source_text[start:end]):
                raise RequirementReviewError("Manual requirement ID does not match its exact source span")
    if manual_count > MAX_MANUAL_REQUIREMENTS:
        raise RequirementReviewError("Assessment has too many manual requirements")
    if not set(candidates).issubset(seen):
        raise RequirementReviewError("Assessment omits detected requirements")
    summary = _summarize(reqs)
    for key, value in summary.items():
        if assessment.get(key) != value:
            raise RequirementReviewError("Assessment summary does not match its requirement rows")
    expected_receipt = {
        "schema_version": 1,
        "status": "APPROVED",
        "review_complete": True,
        "source_job_sha256": assessment["source_job_sha256"],
        "profile_sha256": assessment["profile_sha256"],
        "proposal_sha256": assessment["proposal_sha256"],
        "review_sha256": assessment["review_sha256"],
        "assessment_sha256": _sha256(_canonical_json(assessment)),
    }
    for key, value in expected_receipt.items():
        if receipt.get(key) != value:
            raise RequirementReviewError("Receipt does not approve this exact assessment")
    reviewed_at = receipt.get("reviewed_at_local")
    if not isinstance(reviewed_at, str):
        raise RequirementReviewError("Receipt timestamp is missing")
    try:
        parsed = datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise RequirementReviewError("Receipt timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise RequirementReviewError("Receipt timestamp must include a timezone")
    return assessment


def validate_review_files(
    *, job_path: str, title: str, profile_path: str, assessment_path: str, receipt_path: str,
) -> dict[str, Any]:
    """Validate private review artifacts against the current job and ResumeData files."""
    _job, job_bytes = _read_file(job_path, "Job description", MAX_JOB_BYTES)
    _profile, profile_bytes = _read_file(profile_path, "ResumeData", MAX_PROFILE_BYTES, private=True)
    _assessment, assessment_bytes, assessment = _load_json(assessment_path, "Assessment", private=True)
    _receipt, receipt_bytes, receipt = _load_json(receipt_path, "Receipt", private=True)
    if not isinstance(assessment, dict) or not isinstance(receipt, dict):
        raise RequirementReviewError("Assessment and receipt must be JSON objects")
    if not isinstance(title, str) or not title.strip() or assessment.get("title") != title.strip():
        raise RequirementReviewError("Assessment title does not match the official vacancy title")

    validated = validate_approved(job_bytes, profile_bytes, assessment, receipt)
    blockers = [
        item for item in validated["requirements"]
        if item["required"] is True and item["status"] in BARRIERS
    ]
    status = "APPROVED"
    error_code = None
    if any(item["status"] == "NOT_MET" for item in blockers):
        status, error_code = "REJECTED", "REQUIRED_REQUIREMENT_NOT_MET"
    elif blockers:
        status, error_code = "NEEDS_REVIEW", "REQUIRED_REQUIREMENT_UNRESOLVED"

    result = {
        "status": status,
        "source_job_sha256": validated["source_job_sha256"],
        "profile_sha256": validated["profile_sha256"],
        "review_sha256": validated["review_sha256"],
        "assessment_sha256": _sha256(assessment_bytes),
        "receipt_sha256": _sha256(receipt_bytes),
        "required_barrier_count": len(blockers),
        "requirement_count": validated["count"],
    }
    if error_code:
        result["error_code"] = error_code
    return result


def _read_file(path_value: str, label: str, limit: int, *, private: bool = False) -> tuple[Path, bytes]:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise RequirementReviewError(f"{label} path must be absolute and not a symbolic link")
    try:
        resolved = path.resolve(strict=True)
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > limit:
                raise RequirementReviewError(f"{label} is empty or exceeds its size limit")
            if os.name == "posix" and info.st_uid != os.getuid():
                raise RequirementReviewError(f"{label} is not owned by the current user")
            if private and os.name == "posix" and info.st_mode & 0o077:
                raise RequirementReviewError(f"{label} must be readable only by the current user")
            raw = stream.read(limit + 1)
    except RequirementReviewError:
        raise
    except OSError as exc:
        raise RequirementReviewError(f"{label} is unavailable") from exc
    if len(raw) > limit:
        raise RequirementReviewError(f"{label} exceeds its size limit")
    return resolved, raw


def _load_json(path: str, label: str, *, private: bool = False) -> tuple[Path, bytes, Any]:
    resolved, raw = _read_file(path, label, MAX_JSON_BYTES, private=private)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RequirementReviewError(f"{label} is invalid UTF-8 JSON") from exc
    return resolved, raw, value


def _write_new(path_value: str, data: bytes, label: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise RequirementReviewError(f"{label} output path must be absolute and not a symbolic link")
    try:
        parent = path.parent.resolve(strict=True)
        if not parent.is_dir():
            raise RequirementReviewError(f"{label} output directory is unavailable")
        target = parent / path.name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RequirementReviewError(f"Refusing to overwrite existing {label}") from exc
    except OSError as exc:
        raise RequirementReviewError(f"Could not write {label}") from exc
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    propose = commands.add_parser("propose", help="propose requirement spans for explicit review")
    propose.add_argument("--job", required=True, help="absolute UTF-8 job announcement")
    propose.add_argument("--title", required=True, help="exact official job title")
    propose.add_argument("--profile", required=True, help="absolute private ResumeData JSON")
    propose.add_argument("--out", required=True, help="absolute new proposal path")
    propose.add_argument("--review-template", required=True, help="absolute new review template path")

    approve = commands.add_parser("approve", help="validate a completed human review and issue hash-bound files")
    approve.add_argument("--job", required=True)
    approve.add_argument("--profile", required=True)
    approve.add_argument("--proposal", required=True)
    approve.add_argument("--review", required=True)
    approve.add_argument("--out", required=True, help="absolute new assessment path")
    approve.add_argument("--receipt", required=True, help="absolute new receipt path")
    approve.add_argument("--confirm-job-hash", required=True, help="first 12 chars of current job SHA-256")
    approve.add_argument("--confirm-profile-hash", required=True, help="first 12 chars of current profile SHA-256")

    verify = commands.add_parser("verify", help="revalidate private assessment and receipt against current inputs")
    verify.add_argument("--job", required=True)
    verify.add_argument("--title", required=True)
    verify.add_argument("--profile", required=True)
    verify.add_argument("--assessment", required=True)
    verify.add_argument("--receipt", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _job_path, job_bytes = _read_file(args.job, "Job description", MAX_JOB_BYTES)
        profile_path, profile_bytes = _read_file(args.profile, "ResumeData", MAX_PROFILE_BYTES, private=True)
        if args.command == "propose":
            proposal = build_proposal(job_bytes, args.title, profile_bytes)
            proposal_path = _write_new(args.out, _canonical_json(proposal) + b"\n", "proposal")
            try:
                review_path = _write_new(
                    args.review_template,
                    _canonical_json(proposal["review_template"]) + b"\n",
                    "review template",
                )
            except RequirementReviewError:
                proposal_path.unlink(missing_ok=True)
                raise
            print(json.dumps({
                "status": "NEEDS_REVIEW",
                "proposal_path": str(proposal_path),
                "review_template_path": str(review_path),
                "candidate_count": len(proposal["candidates"]),
                "source_job_sha256": proposal["source_job_sha256"],
                "profile_sha256": proposal["profile_sha256"],
                "proposal_sha256": proposal["proposal_sha256"],
            }, ensure_ascii=False))
            return 0

        if args.command == "verify":
            result = validate_review_files(
                job_path=args.job,
                title=args.title,
                profile_path=args.profile,
                assessment_path=args.assessment,
                receipt_path=args.receipt,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return {"APPROVED": 0, "REJECTED": 1, "NEEDS_REVIEW": 1}[result["status"]]

        if _sha256(job_bytes)[:12] != args.confirm_job_hash or _sha256(profile_bytes)[:12] != args.confirm_profile_hash:
            raise RequirementReviewError("Explicit job/profile hash confirmation does not match current inputs")
        _proposal_path, _proposal_raw, proposal = _load_json(args.proposal, "Proposal", private=True)
        _review_path, _review_raw, review = _load_json(args.review, "Review", private=True)
        if not isinstance(proposal, dict) or not isinstance(review, dict):
            raise RequirementReviewError("Proposal and review must be JSON objects")
        assessment, receipt = approve_review(job_bytes, profile_bytes, proposal, review)
        assessment_path = _write_new(args.out, _canonical_json(assessment) + b"\n", "assessment")
        try:
            receipt_path = _write_new(args.receipt, _canonical_json(receipt) + b"\n", "receipt")
        except RequirementReviewError:
            assessment_path.unlink(missing_ok=True)
            raise
        print(json.dumps({
            "status": "APPROVED",
            "assessment_path": str(assessment_path),
            "receipt_path": str(receipt_path),
            "source_job_sha256": assessment["source_job_sha256"],
            "profile_sha256": assessment["profile_sha256"],
            "recommendation": assessment["recommendation"],
            "required_barrier_count": assessment["required_barrier_count"],
            "requirement_count": assessment["count"],
        }, ensure_ascii=False))
        return 0
    except RequirementReviewError as exc:
        print(json.dumps({"status": "UNVERIFIABLE", "error_code": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
