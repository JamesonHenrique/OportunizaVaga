"""Synthetic tests for the hash-bound final CV content review."""

import importlib.util
import io
import json
import os
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cv_content_review", ROOT / "bot" / "cv_content_review.py"
)
reviewer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reviewer)


@pytest.fixture
def inputs(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    os.chmod(private_dir, 0o700)
    job = private_dir / "job.txt"
    job.write_text("Synthetic Junior Java role", encoding="utf-8")
    pdf = private_dir / "resume.pdf"
    document = canvas.Canvas(str(pdf))
    document.drawString(72, 760, "Synthetic Candidate")
    document.drawString(72, 740, "Java and Spring Boot project experience")
    document.save()
    cv_base = private_dir / "cv_base.md"
    cv_base.write_text(
        "# Synthetic profile\nSynthetic Candidate\nJava and Spring Boot project experience\n",
        encoding="utf-8",
    )
    candidate = private_dir / "candidate.json"
    candidate.write_text(
        json.dumps({"nome": "Synthetic Candidate", "projects": [{"name": "Synthetic project"}]}),
        encoding="utf-8",
    )
    return {
        "dir": private_dir,
        "job": job,
        "pdf": pdf,
        "cv_base": cv_base,
        "candidate": candidate,
    }


def _proposal(files):
    return reviewer.build_proposal(
        job_path=files["job"],
        pdf_path=files["pdf"],
        cv_base_path=files["cv_base"],
        candidate_data_path=files["candidate"],
    )


def _approved_review(proposal):
    review = reviewer.build_review_template(proposal)
    review["acknowledgements"] = {
        name: True for name in reviewer.ACKNOWLEDGEMENTS
    }
    review["claims"] = [
        {
            "claim_id": claim["id"],
            "decision": "SUPPORTED",
            "evidence_refs": [
                "dados_candidato.json:/nome"
                if "Synthetic Candidate" in claim["text"]
                else "cv_base.md:L0003"
            ],
        }
        for claim in proposal["claims"]
    ]
    return review


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.chmod(path, 0o600)


def test_proposal_extracts_lines_and_template_requires_review(inputs):
    proposal = _proposal(inputs)
    template = reviewer.build_review_template(proposal)

    assert proposal["status"] == "NEEDS_REVIEW"
    assert proposal["claim_count"] >= 2
    assert all(claim["text"] for claim in proposal["claims"])
    assert all(value is False for value in template["acknowledgements"].values())
    assert all(item["decision"] == "UNCONFIRMED" for item in template["claims"])


def test_approved_review_is_hash_bound_and_verifiable(inputs):
    proposal = _proposal(inputs)
    assessment, receipt, result = reviewer.approve_review(
        proposal=proposal,
        review=_approved_review(proposal),
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )

    assert result["status"] == "APPROVED"
    assert assessment["claim_count"] == proposal["claim_count"]
    assert receipt["status"] == "APPROVED"

    proposal_path = inputs["dir"] / "proposal.json"
    assessment_path = inputs["dir"] / "assessment.json"
    receipt_path = inputs["dir"] / "receipt.json"
    _write_json(proposal_path, proposal)
    _write_json(assessment_path, assessment)
    _write_json(receipt_path, receipt)
    verified = reviewer.validate_review_files(
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
        proposal_path=proposal_path,
        assessment_path=assessment_path,
        receipt_path=receipt_path,
    )
    assert verified["status"] == "APPROVED"
    assert verified["claim_count"] == proposal["claim_count"]


@pytest.mark.parametrize(
    ("decision", "expected"),
    [("UNSUPPORTED", "REJECTED"), ("UNCONFIRMED", "NEEDS_REVIEW")],
)
def test_unproven_claim_never_approves(inputs, decision, expected):
    proposal = _proposal(inputs)
    review = _approved_review(proposal)
    review["claims"][0] = {
        "claim_id": proposal["claims"][0]["id"],
        "decision": decision,
        "evidence_refs": [],
    }

    assessment, receipt, result = reviewer.approve_review(
        proposal=proposal,
        review=review,
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )

    assert assessment is None
    assert receipt is None
    assert result["status"] == expected


def test_missing_evidence_blocks_supported_claim(inputs):
    proposal = _proposal(inputs)
    review = _approved_review(proposal)
    review["claims"][0]["evidence_refs"] = []

    _, _, result = reviewer.approve_review(
        proposal=proposal,
        review=review,
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )
    assert result == {
        "status": "REJECTED",
        "error_code": "SUPPORTED_CLAIM_WITHOUT_EVIDENCE",
    }


def test_document_with_no_supported_factual_claims_is_not_approved(inputs):
    proposal = _proposal(inputs)
    review = reviewer.build_review_template(proposal)
    review["acknowledgements"] = {name: True for name in reviewer.ACKNOWLEDGEMENTS}
    review["claims"] = [
        {"claim_id": claim["id"], "decision": "NON_FACTUAL", "evidence_refs": []}
        for claim in proposal["claims"]
    ]

    assessment, receipt, result = reviewer.approve_review(
        proposal=proposal,
        review=review,
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )
    assert assessment is None
    assert receipt is None
    assert result == {"status": "NEEDS_REVIEW", "error_code": "NO_SUPPORTED_CLAIMS"}


def test_malformed_decision_does_not_crash_review(inputs):
    proposal = _proposal(inputs)
    review = _approved_review(proposal)
    review["claims"][0]["decision"] = {"unexpected": "object"}

    _, _, result = reviewer.approve_review(
        proposal=proposal,
        review=review,
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )
    assert result["status"] == "UNVERIFIABLE"


def test_changed_job_or_profile_invalidates_existing_proposal(inputs):
    proposal = _proposal(inputs)
    review = _approved_review(proposal)
    inputs["job"].write_text("Changed synthetic role", encoding="utf-8")

    _, _, result = reviewer.approve_review(
        proposal=proposal,
        review=review,
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )
    assert result == {
        "status": "UNVERIFIABLE",
        "error_code": "PROPOSAL_INPUTS_CHANGED",
    }


def test_invalid_pdf_or_empty_extraction_is_unverifiable(inputs, monkeypatch):
    inputs["pdf"].write_bytes(b"not a PDF")
    with pytest.raises(reviewer.ContentReviewError) as error:
        _proposal(inputs)
    assert error.value.status == "REJECTED"

    document = canvas.Canvas(str(inputs["pdf"]))
    document.save()
    monkeypatch.setattr(reviewer, "_run_pdf_text_extractor", lambda _pdf: b"")
    with pytest.raises(reviewer.ContentReviewError) as error:
        _proposal(inputs)
    assert error.value.status == "UNVERIFIABLE"
    assert error.value.code == "PDF_TEXT_EXTRACTION_FAILED"


def test_pdf_text_extraction_stops_when_output_exceeds_limit(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.stdout = io.BytesIO(b"x" * 100)
            self.returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self):
            return self.returncode

    monkeypatch.setattr(reviewer, "MAX_EXTRACTED_TEXT_BYTES", 16)
    monkeypatch.setattr(reviewer.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    with pytest.raises(reviewer.ContentReviewError) as error:
        reviewer._run_pdf_text_extractor(b"synthetic-pdf")
    assert error.value.code == "PDF_TEXT_TOO_LARGE"


def test_pdf_text_extraction_has_a_timeout(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.stdout = io.BytesIO(b"")
            self.returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self):
            return self.returncode

    ticks = iter((0.0, 31.0))
    monkeypatch.setattr(reviewer.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(reviewer.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(reviewer.time, "sleep", lambda _seconds: None)
    with pytest.raises(reviewer.ContentReviewError) as error:
        reviewer._run_pdf_text_extractor(b"synthetic-pdf")
    assert error.value.code == "PDF_TEXT_EXTRACTION_TIMEOUT"


def test_profile_symlink_is_not_accepted(inputs, tmp_path):
    linked_profile = tmp_path / "profile-link.md"
    linked_profile.symlink_to(inputs["cv_base"])
    with pytest.raises(reviewer.ContentReviewError) as error:
        reviewer.build_proposal(
            job_path=inputs["job"],
            pdf_path=inputs["pdf"],
            cv_base_path=linked_profile,
            candidate_data_path=inputs["candidate"],
        )
    assert error.value.status == "UNVERIFIABLE"


def test_private_writer_enforces_mode_and_no_overwrite(inputs):
    output = inputs["dir"] / "receipt.json"
    reviewer._write_new_private(str(output), {"status": "APPROVED"})
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(reviewer.ContentReviewError) as error:
        reviewer._write_new_private(str(output), {"status": "REJECTED"})
    assert error.value.status == "CONFLICT"
    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "APPROVED"}


def test_assessment_or_receipt_tampering_is_not_approved(inputs):
    proposal = _proposal(inputs)
    assessment, receipt, _ = reviewer.approve_review(
        proposal=proposal,
        review=_approved_review(proposal),
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
    )
    proposal_path = inputs["dir"] / "proposal.json"
    assessment_path = inputs["dir"] / "assessment.json"
    receipt_path = inputs["dir"] / "receipt.json"
    _write_json(proposal_path, proposal)
    assessment["status"] = "REJECTED"
    _write_json(assessment_path, assessment)
    _write_json(receipt_path, receipt)

    result = reviewer.validate_review_files(
        job_path=inputs["job"],
        pdf_path=inputs["pdf"],
        cv_base_path=inputs["cv_base"],
        candidate_data_path=inputs["candidate"],
        proposal_path=proposal_path,
        assessment_path=assessment_path,
        receipt_path=receipt_path,
    )
    assert result["status"] != "APPROVED"


def test_cli_propose_approve_verify_roundtrip(inputs, capsys):
    proposal_path = inputs["dir"] / "cli-proposal.json"
    review_path = inputs["dir"] / "cli-review.json"
    assessment_path = inputs["dir"] / "cli-assessment.json"
    receipt_path = inputs["dir"] / "cli-receipt.json"
    common = [
        "--job", str(inputs["job"]),
        "--pdf", str(inputs["pdf"]),
        "--cv-base", str(inputs["cv_base"]),
        "--candidate-data", str(inputs["candidate"]),
        "--proposal", str(proposal_path),
    ]

    assert reviewer.main(["propose", *common, "--review-template", str(review_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NEEDS_REVIEW"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    review = reviewer.build_review_template(proposal)
    review["acknowledgements"] = {name: True for name in reviewer.ACKNOWLEDGEMENTS}
    review["claims"] = [
        {
            "claim_id": claim["id"],
            "decision": "SUPPORTED",
            "evidence_refs": [
                "dados_candidato.json:/nome"
                if "Synthetic Candidate" in claim["text"]
                else "cv_base.md:L0003"
            ],
        }
        for claim in proposal["claims"]
    ]
    _write_json(review_path, review)
    assert reviewer.main([
        "approve", *common,
        "--review", str(review_path),
        "--assessment", str(assessment_path),
        "--receipt", str(receipt_path),
    ]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "APPROVED"
    assert reviewer.main([
        "verify", *common,
        "--assessment", str(assessment_path),
        "--receipt", str(receipt_path),
    ]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "APPROVED"
