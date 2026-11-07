"""Synthetic-only tests for local, review-gated keyword proposal generation."""

import hashlib
import json

import pytest

from bot.job_keyword_proposal import KeywordProposalError, approve_review, build_proposal, main


def _fixture():
    job = (
        "Synthetic Junior Developer\nRequirements:\n- Java and Spring Boot.\n"
        "Nice to have:\n- Docker.\n"
    ).encode()
    catalog = json.dumps({"technology_categories": {"backend": [
        {"name": "Java"}, {"name": "Spring Boot"}, {"name": "Docker"},
    ]}}).encode()
    return job, catalog


def _review(proposal, selected):
    return {
        "proposal_sha256": proposal["proposal_sha256"],
        "source_job_sha256": proposal["source_job_sha256"],
        "reviewed_candidate_ids": [candidate["id"] for candidate in proposal["candidates"]],
        "selected": selected,
        "manual_terms": [],
    }


def test_proposal_is_hash_bound_unapproved_and_context_is_only_a_suggestion():
    job, catalog = _fixture()
    proposal = build_proposal(job, "Synthetic Junior Developer", catalog)
    candidates = {item["term"]: item for item in proposal["candidates"]}

    assert proposal["status"] == "NEEDS_REVIEW"
    assert proposal["source_job_sha256"] == hashlib.sha256(job).hexdigest()
    assert candidates["Java"]["suggested_fields"] == ["required_skills"]
    assert candidates["Docker"]["suggested_fields"] == ["preferred_skills"]
    assert proposal["review_template"]["selected"] == []


def test_review_output_conforms_to_keywords_contract_and_cannot_invent_terms():
    job, catalog = _fixture()
    proposal = build_proposal(job, "Synthetic Junior Developer", catalog)
    java = next(item for item in proposal["candidates"] if item["term"] == "Java")
    keywords, receipt = approve_review(
        job, catalog, proposal,
        _review(proposal, [{"candidate_id": java["id"], "field": "required_skills"}]),
    )

    assert keywords["source_job_sha256"] == hashlib.sha256(job).hexdigest()
    assert keywords["required_skills"] == ["Java"]
    assert keywords["preferred_skills"] == []
    assert receipt["status"] == "APPROVED"


def test_review_requires_each_candidate_to_be_inspected():
    job, catalog = _fixture()
    proposal = build_proposal(job, "Synthetic Junior Developer", catalog)
    review = _review(proposal, [])
    review["reviewed_candidate_ids"].pop()

    with pytest.raises(KeywordProposalError, match="Every proposed keyword"):
        approve_review(job, catalog, proposal, review)


def test_changed_description_invalidates_proposal():
    job, catalog = _fixture()
    proposal = build_proposal(job, "Synthetic Junior Developer", catalog)

    with pytest.raises(KeywordProposalError, match="does not match"):
        approve_review(job + b"Changed", catalog, proposal, _review(proposal, []))


def test_cli_requires_an_explicit_catalog(capsys):
    with pytest.raises(SystemExit) as error:
        main([
            "propose", "--job", "/tmp/synthetic-job.txt", "--title", "Synthetic Role",
            "--out", "/tmp/synthetic-proposal.json",
        ])

    assert error.value.code == 2
    assert "--catalog" in capsys.readouterr().err
