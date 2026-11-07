#!/usr/bin/env python3
"""Propose local Resume-Matcher keywords for explicit review before analysis."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from array import array
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_JOB_BYTES = 1024 * 1024
MAX_CATALOG_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_CATALOG_TERMS = 5000
MAX_CANDIDATES = 250
MAX_OCCURRENCES_PER_CANDIDATE = 5
MAX_OUTPUT_GROUP = 100
MAX_TERM_LENGTH = 160
ALLOWED_FIELDS = {"required_skills", "preferred_skills", "keywords"}

_REQUIRED_CUES = (
    "obrigatorio", "obrigatoria", "essencial", "necessario", "necessaria",
    "requisito", "requirements", "required", "must have", "minimum qualifications", "required qualifications",
    "what you need", "what you will need", "what we're looking for", "you have",
)
_PREFERRED_CUES = (
    "desejavel", "desejaveis", "diferencial", "nice to have", "preferred",
    "bonus", "a plus", "good to have", "seria um diferencial",
)


class KeywordProposalError(ValueError):
    """Input or review data is invalid or no longer matches its source."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_file(path_value: str | Path, label: str, limit: int) -> tuple[Path, bytes]:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        raise KeywordProposalError(f"{label} path must be absolute")
    try:
        resolved = path.resolve(strict=True)
        with resolved.open("rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > limit:
                raise KeywordProposalError(f"{label} is empty or exceeds its size limit")
            data = handle.read(limit + 1)
    except OSError as exc:
        raise KeywordProposalError(f"{label} is unavailable") from exc
    if not data or len(data) > limit:
        raise KeywordProposalError(f"{label} is empty or exceeds its size limit")
    return resolved, data


def _normalize_with_offsets(text: str) -> tuple[str, array, array]:
    chars: list[str] = []
    starts = array("I")
    ends = array("I")
    for index, original in enumerate(text):
        folded = unicodedata.normalize("NFKD", original).casefold()
        for char in folded:
            if unicodedata.combining(char):
                continue
            if char.isspace():
                if chars and chars[-1] == " ":
                    ends[-1] = index + 1
                else:
                    chars.append(" ")
                    starts.append(index)
                    ends.append(index + 1)
            else:
                chars.append(char)
                starts.append(index)
                ends.append(index + 1)
    while chars and chars[-1] == " ":
        chars.pop()
        starts.pop()
        ends.pop()
    return "".join(chars), starts, ends


def _normalize(value: str) -> str:
    return _normalize_with_offsets(value)[0].strip()


def _is_word_char(char: str) -> bool:
    return char == "_" or char.isalnum()


def _has_term_boundaries(text: str, start: int, end: int, term: str) -> bool:
    if start and term and _is_word_char(term[0]) and _is_word_char(text[start - 1]):
        return False
    if end < len(text) and term and _is_word_char(term[-1]) and _is_word_char(text[end]):
        return False
    # A one-letter language is too ambiguous to treat as a deterministic match.
    if term in {"c", "r"}:
        return False
    return True


def _load_catalog(data: bytes) -> list[tuple[str, str, str]]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise KeywordProposalError("Technology catalog is not valid UTF-8 JSON") from exc
    categories = value.get("technology_categories") if isinstance(value, dict) else None
    if not isinstance(categories, dict):
        raise KeywordProposalError("Technology catalog has no technology_categories object")

    result: list[tuple[str, str, str]] = []
    for category, entries in categories.items():
        if not isinstance(category, str) or not isinstance(entries, list):
            raise KeywordProposalError("Technology catalog category has an invalid shape")
        for entry in entries:
            if isinstance(entry, str):
                name, aliases = entry, []
            elif isinstance(entry, dict):
                name, aliases = entry.get("name"), entry.get("aliases", [])
            else:
                raise KeywordProposalError("Technology catalog contains an invalid term")
            if not isinstance(name, str) or not name.strip() or not isinstance(aliases, list):
                raise KeywordProposalError("Technology catalog contains an invalid name or alias list")
            if any(not isinstance(alias, str) for alias in aliases):
                raise KeywordProposalError("Technology catalog aliases must be strings")
            for term in [name, *aliases]:
                normalized = _normalize(term)
                if normalized:
                    result.append((normalized, name.strip(), category))
                    if len(result) > MAX_CATALOG_TERMS:
                        raise KeywordProposalError("Technology catalog has too many terms")
    if not result:
        raise KeywordProposalError("Technology catalog has no usable terms")
    return result


def _line_ranges(text: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        end = cursor + len(line)
        ranges.append((cursor, end, line.rstrip("\r\n")))
        cursor = end
    if cursor < len(text) or not ranges:
        ranges.append((cursor, len(text), text[cursor:]))
    return ranges


def _line_field_suggestions(lines: list[tuple[int, int, str]]) -> list[str]:
    state = "keywords"
    result: list[str] = []
    for _start, _end, line in lines:
        clean = line.strip()
        normalized = _normalize(clean.lstrip("# "))
        required = any(cue in normalized for cue in _REQUIRED_CUES)
        preferred = any(cue in normalized for cue in _PREFERRED_CUES)
        colon = clean.find(":")
        prefix = _normalize(clean[:colon]) if colon >= 0 else ""
        cue_in_prefix = any(cue in prefix for cue in _REQUIRED_CUES + _PREFERRED_CUES)
        heading = bool(clean.startswith("#") or clean.endswith(":") or (
            len(clean) <= 80
            and not clean.startswith(("-", "*", "•", "→"))
            and not re.search(r"[.!?;]", clean)
        ) or cue_in_prefix)
        if required != preferred and (required or preferred):
            suggestion = "required_skills" if required else "preferred_skills"
            if heading:
                state = suggestion
        elif required and preferred:
            suggestion = "keywords"
            if heading:
                state = "keywords"
        else:
            suggestion = "keywords" if heading else state
            if heading:
                state = "keywords"
        result.append(suggestion)
    return result


def build_proposal(job_bytes: bytes, title: str, catalog_bytes: bytes) -> dict[str, Any]:
    if not title.strip() or len(title) > 200:
        raise KeywordProposalError("Exact vacancy title is required and must be at most 200 characters")
    try:
        text = job_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KeywordProposalError("Job description must be UTF-8 text") from exc
    terms = _load_catalog(catalog_bytes)
    normalized_text, offset_starts, offset_ends = _normalize_with_offsets(text)
    lines = _line_ranges(text)
    line_starts = [line[0] for line in lines]
    line_fields = _line_field_suggestions(lines)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    total_matches = 0

    # Each lookup is a literal search over a bounded local vocabulary. No job text
    # is interpreted as instructions or sent to an LLM or external service.
    for normalized_term, canonical, category in terms:
        cursor = 0
        local_count = 0
        while local_count < MAX_OCCURRENCES_PER_CANDIDATE:
            start = normalized_text.find(normalized_term, cursor)
            if start < 0:
                break
            end = start + len(normalized_term)
            cursor = max(end, start + 1)
            if not _has_term_boundaries(normalized_text, start, end, normalized_term):
                continue
            if not offset_starts or end > len(offset_starts):
                continue
            original_start = offset_starts[start]
            original_end = offset_ends[end - 1]
            line_index = max(0, bisect.bisect_right(line_starts, original_start) - 1)
            line_start, line_end, _line = lines[line_index]
            excerpt_start = max(line_start, original_start - 100)
            excerpt_end = min(line_end, original_end + 100)
            key = (canonical.casefold(), category)
            candidate = grouped.setdefault(key, {
                "id": "skill-" + hashlib.sha256(f"{canonical}\0{category}".encode()).hexdigest()[:16],
                "term": canonical,
                "category": category,
                "match_aliases": [],
                "occurrences": [],
                "occurrence_count": 0,
                "occurrences_truncated": False,
                "suggested_fields": [],
                "confidence": "ambiguous_catalog_term; review_required"
                if normalized_term in {"go", "bi", "make", "oracle", "lambda", "apache"}
                or len(normalized_term) <= 2
                else "exact_catalog_phrase; review_required",
            })
            if normalized_term not in candidate["match_aliases"]:
                candidate["match_aliases"].append(normalized_term)
            if normalized_term in {"go", "bi", "make", "oracle", "lambda", "apache"} or len(normalized_term) <= 2:
                candidate["confidence"] = "ambiguous_catalog_term; review_required"
            occurrence = {
                "start": original_start,
                "end": original_end,
                "matched_text": text[original_start:original_end],
                "excerpt": text[excerpt_start:excerpt_end].strip(),
                "suggested_field": line_fields[line_index],
            }
            if occurrence not in candidate["occurrences"]:
                candidate["occurrence_count"] += 1
                if len(candidate["occurrences"]) < MAX_OCCURRENCES_PER_CANDIDATE:
                    candidate["occurrences"].append(occurrence)
                else:
                    candidate["occurrences_truncated"] = True
                if occurrence["suggested_field"] not in candidate["suggested_fields"]:
                    candidate["suggested_fields"].append(occurrence["suggested_field"])
            local_count += 1
            total_matches += 1
            if total_matches > MAX_CANDIDATES * MAX_OCCURRENCES_PER_CANDIDATE:
                raise KeywordProposalError("Job description produces too many catalog matches to review safely")
        if local_count == MAX_OCCURRENCES_PER_CANDIDATE:
            next_match = normalized_text.find(normalized_term, cursor)
            while next_match >= 0 and not _has_term_boundaries(
                normalized_text, next_match, next_match + len(normalized_term), normalized_term,
            ):
                next_match = normalized_text.find(normalized_term, next_match + 1)
            if next_match >= 0:
                candidate = grouped.get((canonical.casefold(), category))
                if candidate is not None:
                    candidate["occurrences_truncated"] = True

    candidates = sorted(grouped.values(), key=lambda item: (item["term"].casefold(), item["category"]))
    if len(candidates) > MAX_CANDIDATES:
        raise KeywordProposalError("Job description produces too many distinct keywords to review safely")
    core = {
        "schema_version": 1,
        "status": "NEEDS_REVIEW",
        "role": title.strip(),
        "source_job_sha256": _sha256(job_bytes),
        "catalog_sha256": _sha256(catalog_bytes),
        "candidates": candidates,
        "limitations": [
            "Only exact matches from the local technology catalog are proposed.",
            "Context-based field suggestions are heuristic and are not approved keywords.",
            "Terms absent from the catalog may be missed; add them only as exact source spans in the review file.",
            "This analysis does not establish candidate experience or recommend submitting an application.",
        ],
    }
    proposal_digest = _sha256(_canonical_json(core))
    return {
        **core,
        "proposal_sha256": proposal_digest,
        "review_template": {
            "proposal_sha256": proposal_digest,
            "source_job_sha256": core["source_job_sha256"],
            "reviewed_candidate_ids": [],
            "selected": [],
            "manual_terms": [],
        },
    }


def approve_review(
    job_bytes: bytes,
    catalog_bytes: bytes,
    proposal: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = build_proposal(job_bytes, proposal.get("role", ""), catalog_bytes)
    if proposal != expected:
        raise KeywordProposalError("Proposal does not match the current job, title, or catalog")
    if not isinstance(review, dict) or set(review) - {
        "proposal_sha256", "source_job_sha256", "reviewed_candidate_ids", "selected", "manual_terms",
    }:
        raise KeywordProposalError("Review file has an unsupported shape")
    if review.get("proposal_sha256") != expected["proposal_sha256"]:
        raise KeywordProposalError("Review file references a different proposal")
    if review.get("source_job_sha256") != expected["source_job_sha256"]:
        raise KeywordProposalError("Review file references a different job description")

    candidate_ids = [candidate["id"] for candidate in expected["candidates"]]
    reviewed = review.get("reviewed_candidate_ids")
    if not isinstance(reviewed, list) or any(not isinstance(item, str) for item in reviewed):
        raise KeywordProposalError("Review must list every candidate id that was inspected")
    if len(set(reviewed)) != len(reviewed) or set(reviewed) != set(candidate_ids):
        raise KeywordProposalError("Every proposed keyword must be explicitly reviewed exactly once")

    selected = review.get("selected")
    if not isinstance(selected, list) or len(selected) > MAX_CANDIDATES:
        raise KeywordProposalError("Review selection must be a bounded list")
    candidates_by_id = {candidate["id"]: candidate for candidate in expected["candidates"]}
    fields: dict[str, list[str]] = {field: [] for field in sorted(ALLOWED_FIELDS)}
    selected_ids: set[str] = set()
    for decision in selected:
        if not isinstance(decision, dict) or set(decision) != {"candidate_id", "field"}:
            raise KeywordProposalError("Each selection needs exactly candidate_id and field")
        candidate_id, field = decision["candidate_id"], decision["field"]
        if candidate_id not in candidates_by_id or candidate_id in selected_ids or field not in ALLOWED_FIELDS:
            raise KeywordProposalError("Review selected an unknown, duplicated, or unsupported keyword")
        selected_ids.add(candidate_id)
        fields[field].append(candidates_by_id[candidate_id]["term"])

    manual_terms = review.get("manual_terms", [])
    if not isinstance(manual_terms, list) or len(manual_terms) > MAX_CANDIDATES:
        raise KeywordProposalError("Manual terms must be a bounded list")
    text = job_bytes.decode("utf-8")
    for item in manual_terms:
        if not isinstance(item, dict) or set(item) != {"text", "start", "end", "field"}:
            raise KeywordProposalError("Each manual term needs exact source text, offsets, and field")
        phrase, start, end, field = item["text"], item["start"], item["end"], item["field"]
        if (
            not isinstance(phrase, str) or not phrase.strip() or len(phrase) > MAX_TERM_LENGTH
            or isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or not 0 <= start < end <= len(text) or text[start:end] != phrase
            or field not in ALLOWED_FIELDS
        ):
            raise KeywordProposalError("Manual term must exactly match a bounded source span and supported field")
        fields[field].append(phrase.strip())

    global_terms: dict[str, str] = {}
    for field, values in fields.items():
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = _normalize(value)
            if normalized not in seen:
                if normalized in global_terms and global_terms[normalized] != field:
                    raise KeywordProposalError("The same keyword cannot be assigned to multiple requirement groups")
                global_terms[normalized] = field
                seen.add(normalized)
                deduped.append(value)
        if len(deduped) > MAX_OUTPUT_GROUP:
            raise KeywordProposalError(f"Review exceeds the {MAX_OUTPUT_GROUP}-item limit for {field}")
        fields[field] = deduped

    if not any(fields.values()):
        raise KeywordProposalError("Review selected no keywords")
    keywords = {
        "source_job_sha256": expected["source_job_sha256"],
        "role": expected["role"],
        **fields,
    }
    receipt = {
        "status": "APPROVED",
        "source_job_sha256": expected["source_job_sha256"],
        "proposal_sha256": expected["proposal_sha256"],
        "review_sha256": _sha256(_canonical_json(review)),
        "keywords_sha256": _sha256(_canonical_json(keywords)),
        "selected_counts": {field: len(values) for field, values in fields.items()},
        "reviewed_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return keywords, receipt


def _load_json(path_value: str, label: str) -> tuple[Path, bytes, Any]:
    path, raw = _read_file(path_value, label, MAX_JSON_BYTES)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise KeywordProposalError(f"{label} is not valid UTF-8 JSON") from exc
    return path, raw, value


def _write_new(path_value: str, data: bytes, label: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        raise KeywordProposalError(f"{label} output path must be absolute")
    parent = path.parent.resolve(strict=True)
    if not parent.is_dir():
        raise KeywordProposalError(f"{label} output directory is unavailable")
    target = parent / path.name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    created = False
    try:
        fd = os.open(target, flags, 0o600)
        created = True
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise KeywordProposalError(f"Refusing to overwrite existing {label} output") from exc
    except OSError as exc:
        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        raise KeywordProposalError(f"Could not write {label} output") from exc
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    propose = commands.add_parser("propose", help="create an unapproved keyword proposal")
    propose.add_argument("--job", required=True, help="absolute UTF-8 job description path")
    propose.add_argument("--title", required=True, help="exact title from the job posting")
    propose.add_argument("--catalog", required=True, help="absolute path to a caller-provided technical vocabulary JSON")
    propose.add_argument("--out", required=True, help="absolute output proposal path; will not overwrite")
    propose.add_argument("--review-template", help="optional absolute review-sheet path; will not overwrite")

    approve = commands.add_parser("approve", help="convert a reviewed proposal to JobKeywords JSON")
    approve.add_argument("--job", required=True, help="absolute UTF-8 job description path")
    approve.add_argument("--proposal", required=True, help="proposal JSON from the propose command")
    approve.add_argument("--review", required=True, help="completed review-template JSON")
    approve.add_argument("--catalog", required=True, help="absolute path to the same reviewed technical vocabulary JSON")
    approve.add_argument("--out", required=True, help="absolute strict JobKeywords JSON output; will not overwrite")
    approve.add_argument("--receipt", required=True, help="absolute review receipt output; will not overwrite")
    approve.add_argument(
        "--confirm-job-hash",
        required=True,
        help="explicit review confirmation: first 12 chars of current job SHA-256",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        _job_path, job_bytes = _read_file(args.job, "Job description", MAX_JOB_BYTES)
        _catalog_path, catalog_bytes = _read_file(args.catalog, "Technology catalog", MAX_CATALOG_BYTES)
        digest = _sha256(job_bytes)
        if args.command == "propose":
            proposal = build_proposal(job_bytes, args.title, catalog_bytes)
            output = _write_new(args.out, _canonical_json(proposal) + b"\n", "proposal")
            review_template_path = None
            if args.review_template:
                try:
                    review_template_path = _write_new(
                        args.review_template,
                        _canonical_json(proposal["review_template"]) + b"\n",
                        "review template",
                    )
                except KeywordProposalError:
                    output.unlink(missing_ok=True)
                    raise
            print(json.dumps({
                "status": proposal["status"], "proposal_path": str(output),
                "review_template_path": str(review_template_path) if review_template_path else None,
                "candidate_count": len(proposal["candidates"]),
                "source_job_sha256": digest, "proposal_sha256": proposal["proposal_sha256"],
            }))
            return 0

        _proposal_path, _proposal_raw, proposal = _load_json(args.proposal, "Proposal")
        _review_path, review_raw, review = _load_json(args.review, "Review")
        if not isinstance(proposal, dict) or not isinstance(review, dict):
            raise KeywordProposalError("Proposal and review must be JSON objects")
        if args.confirm_job_hash != digest[:12]:
            raise KeywordProposalError(
                "Explicit confirmation must equal the first 12 characters of the current job SHA-256"
            )
        keywords, receipt = approve_review(job_bytes, catalog_bytes, proposal, review)
        keywords_bytes = _canonical_json(keywords) + b"\n"
        receipt["keywords_sha256"] = _sha256(keywords_bytes.rstrip(b"\n"))
        receipt["review_sha256"] = _sha256(review_raw)
        receipt_path = _write_new(args.receipt, _canonical_json(receipt) + b"\n", "review receipt")
        try:
            keywords_path = _write_new(args.out, keywords_bytes, "approved keywords")
        except Exception:
            receipt_path.unlink(missing_ok=True)
            raise
        print(json.dumps({
            "status": "APPROVED", "keywords_path": str(keywords_path),
            "receipt_path": str(receipt_path), "source_job_sha256": digest,
            "keyword_counts": receipt["selected_counts"],
        }))
        return 0
    except KeywordProposalError as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
