"""Synthetic tests for explicit, hash-bound CV selection in a single application tab."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from io import BytesIO
from pathlib import Path

from bot import job_requirement_review
from bot import cv_content_review
from reportlab.pdfgen import canvas

SCRIPT = Path(__file__).resolve().parents[1] / "bot" / "attach_cv.py"
MODULE_SPEC = importlib.util.spec_from_file_location("attach_cv_public", SCRIPT)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
ATTACH = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(ATTACH)

URL = "https://jobs.example.invalid/application/123"
SELECTOR = "input[type=file][name=resume]"
JOB_BYTES = b"Synthetic job description: remote; minimum 2 years of experience; Java and Spring Boot."


def _pdf_bytes():
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(72, 760, "Synthetic Candidate Resume")
    document.drawString(72, 740, "Java and Spring Boot project experience")
    document.save()
    return output.getvalue()


PDF_BYTES = _pdf_bytes()
JOB_SHA = hashlib.sha256(JOB_BYTES).hexdigest()
PDF_SHA = hashlib.sha256(PDF_BYTES).hexdigest()
APPROVAL = {
    "status": "APPROVED",
    "manifest_verified": True,
    "manifest_id": f"{JOB_SHA}-{PDF_SHA}",
    "job_description_sha256": JOB_SHA,
    "sha256": PDF_SHA,
    "pdf_sha256": PDF_SHA,
    "resume_matcher_revision": "a" * 40,
    "verifier_policy_version": 1,
    "verified_at": "2026-11-07T12:00:00-03:00",
}


class FakeSocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeChrome:
    def __init__(self, *, pages=None, node_ids=None, disabled=False):
        self._pages = pages if pages is not None else {"target-1": {"url": URL}}
        self.node_ids = [10] if node_ids is None else node_ids
        self.disabled = disabled
        self.calls = []
        self.selected = None
        self.ws = FakeSocket()

    def pages(self):
        return self._pages

    def anexar(self, target_id):
        assert target_id == "target-1"
        return "session-1"

    def call(self, method, params=None, session_id=None):
        params = params or {}
        self.calls.append((method, params, session_id))
        if method == "DOM.getDocument":
            return {"root": {"nodeType": 9, "nodeId": 1, "children": []}}
        if method == "DOM.querySelectorAll":
            return {"nodeIds": self.node_ids}
        if method == "DOM.describeNode":
            attributes = ["type", "file", "name", "resume"]
            if self.disabled:
                attributes += ["disabled", ""]
            return {"node": {"nodeName": "INPUT", "attributes": attributes}}
        if method == "DOM.setFileInputFiles":
            self.selected = params
            return {}
        return {}


class VerificationSequence:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def __call__(self, url_prefix, selector, expected_sha256):
        self.calls.append((url_prefix, selector, expected_sha256))
        return self.values.pop(0)


def _empty_input():
    return {"status": "NEEDS_REVIEW", "error_code": "NO_SELECTED_FILE"}


def _approved_browser():
    return {
        "status": "APPROVED",
        "selected_sha256": PDF_SHA,
        "expected_sha256": PDF_SHA,
        "input_count": 1,
        "selected_file_count": 1,
        "matching_file_count": 1,
        "verified_at": "2026-11-07T12:00:01-03:00",
    }


def _paths(tmp_path):
    job = tmp_path / "job.txt"
    pdf = tmp_path / "resume.pdf"
    job.write_bytes(JOB_BYTES)
    pdf.write_bytes(PDF_BYTES)
    return job, pdf


def _requirement_artifacts(job: Path, title: str, *, required_status: str | None = None) -> dict[str, str]:
    profile = {
        "summary": "Synthetic profile for tests.",
        "workExperience": [],
        "personalProjects": [],
        "education": [],
        "additional": {"technicalSkills": [], "languages": [], "certificationsTraining": []},
        "customSections": {},
    }
    profile_bytes = json.dumps(profile, sort_keys=True).encode("utf-8")
    proposal = job_requirement_review.build_proposal(job.read_bytes(), title, profile_bytes)
    candidates = proposal["candidates"]
    sheet = {
        "proposal_sha256": proposal["proposal_sha256"],
        "source_job_sha256": proposal["source_job_sha256"],
        "profile_sha256": proposal["profile_sha256"],
        "reviewed_candidate_ids": [item["id"] for item in candidates],
        "assessments": [
            {
                "candidate_id": item["id"],
                "required": False,
                "status": "UNCONFIRMED",
                "evidence_refs": [],
            }
            for item in candidates
        ],
        "manual_requirements": [],
        "confirm_no_additional_requirements": not candidates,
    }
    if required_status:
        assert candidates, "the synthetic job must contain at least one review cue"
        sheet["assessments"][0].update(required=True, status=required_status)
    assessment, receipt = job_requirement_review.approve_review(
        job.read_bytes(), profile_bytes, proposal, sheet,
    )

    paths = {
        "requirements_profile_path": job.parent / "requirements-profile.json",
        "requirements_assessment_path": job.parent / "requirements-assessment.json",
        "requirements_receipt_path": job.parent / "requirements-receipt.json",
    }
    paths["requirements_profile_path"].write_bytes(profile_bytes)
    paths["requirements_assessment_path"].write_text(json.dumps(assessment), encoding="utf-8")
    paths["requirements_receipt_path"].write_text(json.dumps(receipt), encoding="utf-8")
    for path in paths.values():
        path.chmod(0o600)
    return {key: str(path) for key, path in paths.items()}


def _content_review_artifacts(job: Path, pdf: Path) -> dict[str, str]:
    cv_base = job.parent / "cv_base.md"
    cv_base.write_text(
        "# Synthetic Candidate Resume\nJava and Spring Boot project experience\n",
        encoding="utf-8",
    )
    candidate = job.parent / "candidate-data.json"
    candidate.write_text(json.dumps({"candidate": "Synthetic"}), encoding="utf-8")
    proposal = cv_content_review.build_proposal(
        job_path=job,
        pdf_path=pdf,
        cv_base_path=cv_base,
        candidate_data_path=candidate,
    )
    review = cv_content_review.build_review_template(proposal)
    review["acknowledgements"] = {name: True for name in cv_content_review.ACKNOWLEDGEMENTS}
    review["claims"] = [
        {
            "claim_id": claim["id"],
            "decision": "SUPPORTED",
            "evidence_refs": [
                "cv_base.md:L0001" if "Synthetic Candidate Resume" in claim["text"] else "cv_base.md:L0002"
            ],
        }
        for claim in proposal["claims"]
    ]
    assessment, receipt, result = cv_content_review.approve_review(
        proposal=proposal,
        review=review,
        job_path=job,
        pdf_path=pdf,
        cv_base_path=cv_base,
        candidate_data_path=candidate,
    )
    assert result["status"] == "APPROVED"
    paths = {
        "content_cv_base_path": cv_base,
        "content_candidate_data_path": candidate,
        "content_proposal_path": job.parent / "content-proposal.json",
        "content_assessment_path": job.parent / "content-assessment.json",
        "content_receipt_path": job.parent / "content-receipt.json",
    }
    for key, value in (
        ("content_proposal_path", proposal),
        ("content_assessment_path", assessment),
        ("content_receipt_path", receipt),
    ):
        paths[key].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    for path in paths.values():
        path.chmod(0o600)
    return {key: str(path) for key, path in paths.items()}


def _approval_runner(attachment):
    def run(command, **kwargs):
        assert command[-1] == str(attachment)
        assert kwargs["env"]["OV_RESUME_MATCHER_REQUIRED"] == "1"
        assert kwargs["timeout"] > 0
        stdout = "ATS pass\n" + json.dumps(APPROVAL) + "\nANEXAR " + str(attachment) + "\n"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
    return run


def _call(job, pdf, **kwargs):
    required_status = kwargs.pop("required_status", None)
    content_keys = {
        "content_cv_base_path", "content_candidate_data_path", "content_proposal_path",
        "content_assessment_path", "content_receipt_path",
    }
    if content_keys <= set(kwargs):
        content_paths = {key: kwargs.pop(key) for key in content_keys}
    elif pdf.read_bytes().startswith(b"%PDF-"):
        content_paths = _content_review_artifacts(job, pdf)
    else:
        content_paths = {
            "content_cv_base_path": str(job.parent / "missing-cv-base.md"),
            "content_candidate_data_path": str(job.parent / "missing-candidate.json"),
            "content_proposal_path": str(job.parent / "missing-proposal.json"),
            "content_assessment_path": str(job.parent / "missing-assessment.json"),
            "content_receipt_path": str(job.parent / "missing-receipt.json"),
        }
    defaults = {
        "announcement_path": str(job),
        "attachment_path": str(pdf),
        "application_key": "example_java_jr_123",
        "company": "Example Ltda.",
        "title": "Desenvolvedor Java Júnior",
        "url_prefix": URL,
        "selector": SELECTOR,
        "approval_runner": _approval_runner(pdf.resolve()),
        **_requirement_artifacts(job, "Desenvolvedor Java Júnior", required_status=required_status),
        **content_paths,
    }
    defaults.update(kwargs)
    return ATTACH.attach_cv(**defaults)


def test_selects_only_the_exact_approved_file_and_returns_application_binding(tmp_path):
    job, pdf = _paths(tmp_path)
    chrome = FakeChrome()
    verification = VerificationSequence(_empty_input(), _approved_browser())

    result = _call(
        job,
        pdf,
        chrome_factory=lambda: chrome,
        verify_func=verification,
    )

    assert result["status"] == "APPROVED"
    assert result["selection"] == "SELECTED_AND_HASH_VERIFIED"
    assert result["cv_manifest_id"] == f"{JOB_SHA}-{PDF_SHA}"
    assert result["cv_job_sha256"] == JOB_SHA
    assert result["cv_pdf_sha256"] == PDF_SHA
    assert result["cv_job_key"] == "example_java_jr_123"
    assert result["cv_job_company"] == "Example Ltda."
    assert result["cv_job_title"] == "Desenvolvedor Java Júnior"
    assert result["cv_content_review_status"] == "APPROVED"
    assert result["cv_content_claim_count"] == (
        result["cv_content_supported_claim_count"] + result["cv_content_non_factual_claim_count"]
    )
    assert result["selected_sha256"] == PDF_SHA
    assert result["submit_clicked"] is False
    assert result["portal_receipt_verified"] is False
    assert all(field in result for field in ATTACH.cv_intent_gate.CONTENT_REVIEW_PATH_FIELDS)
    assert all(field in result for field in ATTACH.cv_intent_gate.CONTENT_REVIEW_AUDIT_FIELDS)
    reference = ATTACH.cv_intent_gate.manifest_fields(result)
    assert reference is not None
    assert ATTACH.cv_intent_gate._validate_job_binding(
        {"empresa": result["cv_job_company"], "vaga": result["cv_job_title"]},
        reference,
        result["cv_job_key"],
    ) == ""
    assert ATTACH.cv_intent_gate._validate_job_binding(
        {"empresa": "Different Ltda.", "vaga": result["cv_job_title"]},
        reference,
        result["cv_job_key"],
    )
    assert chrome.selected == {"files": [str(pdf.resolve())], "nodeId": 10}
    methods = [method for method, _params, _session in chrome.calls]
    assert "DOM.setFileInputFiles" in methods
    assert "Target.closeTarget" not in methods
    assert chrome.ws.closed


def test_exact_file_already_selected_is_approved_without_mutation(tmp_path):
    job, pdf = _paths(tmp_path)
    verification = VerificationSequence(_approved_browser())

    result = _call(
        job,
        pdf,
        chrome_factory=lambda: (_ for _ in ()).throw(AssertionError("must not connect")),
        verify_func=verification,
    )

    assert result["status"] == "APPROVED"
    assert result["selection"] == "ALREADY_SELECTED"
    assert len(verification.calls) == 1


def test_wrong_existing_file_is_not_replaced(tmp_path):
    job, pdf = _paths(tmp_path)
    verification = VerificationSequence({"status": "REJECTED", "error_code": "SELECTED_FILE_HASH_MISMATCH"})
    connected = False

    def factory():
        nonlocal connected
        connected = True
        raise AssertionError("wrong selection must not be replaced")

    try:
        _call(job, pdf, chrome_factory=factory, verify_func=verification)
    except ATTACH.AttachCvError as exc:
        assert exc.status == "REJECTED"
    else:
        raise AssertionError("wrong existing selection was accepted")
    assert not connected


def test_ambiguous_tabs_are_rejected_before_selecting(tmp_path):
    job, pdf = _paths(tmp_path)
    chrome = FakeChrome(pages={"target-1": {"url": URL}, "target-2": {"url": URL + "/step"}})
    verification = VerificationSequence(_empty_input())

    try:
        _call(job, pdf, chrome_factory=lambda: chrome, verify_func=verification)
    except ATTACH.AttachCvError as exc:
        assert exc.status == "NEEDS_REVIEW"
        assert exc.error_code == "BROWSER_TAB_AMBIGUOUS"
    else:
        raise AssertionError("ambiguous tabs were accepted")
    assert chrome.selected is None
    assert chrome.ws.closed


def test_ambiguous_or_disabled_inputs_are_rejected(tmp_path):
    job, pdf = _paths(tmp_path)
    for chrome in (FakeChrome(node_ids=[10, 11]), FakeChrome(disabled=True)):
        verification = VerificationSequence(_empty_input())
        try:
            _call(job, pdf, chrome_factory=lambda: chrome, verify_func=verification)
        except ATTACH.AttachCvError as exc:
            assert exc.status == "NEEDS_REVIEW"
        else:
            raise AssertionError("ambiguous or disabled file input was accepted")
        assert chrome.selected is None


def test_post_selection_hash_mismatch_does_not_approve(tmp_path):
    job, pdf = _paths(tmp_path)
    chrome = FakeChrome()
    verification = VerificationSequence(
        _empty_input(), {"status": "REJECTED", "error_code": "SELECTED_FILE_HASH_MISMATCH"}
    )

    try:
        _call(job, pdf, chrome_factory=lambda: chrome, verify_func=verification)
    except ATTACH.AttachCvError as exc:
        assert exc.status == "REJECTED"
    else:
        raise AssertionError("post-selection hash mismatch was approved")


def test_invalid_manifest_result_blocks_before_browser_access(tmp_path):
    job, pdf = _paths(tmp_path)
    bad_approval = dict(APPROVAL, manifest_verified=False)

    def bad_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 0,
            stdout=json.dumps(bad_approval) + "\nANEXAR " + str(pdf.resolve()) + "\n",
            stderr="",
        )

    connected = False

    def factory():
        nonlocal connected
        connected = True
        raise AssertionError("invalid approval must not open Chrome")

    try:
        _call(job, pdf, approval_runner=bad_runner, chrome_factory=factory)
    except ATTACH.AttachCvError as exc:
        assert exc.status == "UNVERIFIABLE"
        assert exc.error_code == "CV_APPROVAL_GATE_RESULT_INVALID"
    else:
        raise AssertionError("invalid manifest was approved")
    assert not connected


def test_gate_failure_or_timeout_is_fail_closed(tmp_path):
    job, pdf = _paths(tmp_path)

    def failed(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="synthetic failure")

    try:
        _call(job, pdf, approval_runner=failed)
    except ATTACH.AttachCvError as exc:
        assert exc.status == "UNVERIFIABLE"
    else:
        raise AssertionError("gate failure was accepted")

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    try:
        _call(job, pdf, approval_runner=timeout)
    except ATTACH.AttachCvError as exc:
        assert exc.error_code == "CV_APPROVAL_GATE_TIMEOUT"
    else:
        raise AssertionError("gate timeout was accepted")


def test_invalid_identity_and_unresolved_or_unmet_requirements_block(tmp_path):
    job, pdf = _paths(tmp_path)
    for changes, expected in (
        ({"application_key": "../other"}, "INVALID_APPLICATION_KEY"),
        ({"company": "\n"}, "INVALID_COMPANY"),
    ):
        try:
            _call(job, pdf, **changes)
        except ATTACH.AttachCvError as exc:
            assert exc.error_code == expected
        else:
            raise AssertionError(f"invalid request accepted: {expected}")

    for status, expected_status in (("UNCONFIRMED", "NEEDS_REVIEW"), ("NOT_MET", "REJECTED")):
        try:
            _call(job, pdf, required_status=status)
        except ATTACH.AttachCvError as exc:
            assert exc.status == expected_status
            assert exc.error_code == "JOB_REQUIREMENT_REVIEW_BLOCKED"
        else:
            raise AssertionError(f"required {status} barrier was accepted")

    try:
        _call(job, pdf, requirements_receipt_path="")
    except ATTACH.AttachCvError as exc:
        assert exc.status == "NEEDS_REVIEW"
        assert exc.error_code == "JOB_REQUIREMENT_REVIEW_BLOCKED"
    else:
        raise AssertionError("missing typed review receipt was accepted")


def test_invalid_url_and_non_pdf_block_without_browser(tmp_path):
    job, pdf = _paths(tmp_path)
    connected = False

    def factory():
        nonlocal connected
        connected = True
        raise AssertionError("invalid request must not connect")

    for changes in (
        {"url_prefix": URL + "?token=synthetic"},
        {"selector": ""},
    ):
        try:
            _call(job, pdf, chrome_factory=factory, **changes)
        except ATTACH.AttachCvError as exc:
            assert exc.status == "UNVERIFIABLE"
        else:
            raise AssertionError("invalid browser selector was accepted")

    non_pdf = tmp_path / "not-a-pdf.bin"
    non_pdf.write_bytes(b"not a pdf")
    try:
        _call(job, non_pdf, chrome_factory=factory)
    except ATTACH.AttachCvError as exc:
        assert exc.error_code == "ATTACHMENT_NOT_PDF"
    else:
        raise AssertionError("non-PDF attachment was accepted")
    assert not connected


def test_missing_or_tampered_content_review_blocks_before_browser(tmp_path):
    job, pdf = _paths(tmp_path)
    connected = False

    def factory():
        nonlocal connected
        connected = True
        raise AssertionError("unapproved content must not open Chrome")

    artifacts = _content_review_artifacts(job, pdf)
    Path(artifacts["content_receipt_path"]).write_text("{}", encoding="utf-8")
    try:
        _call(job, pdf, chrome_factory=factory, **artifacts)
    except ATTACH.AttachCvError as exc:
        assert exc.status == "UNVERIFIABLE"
        assert exc.error_code == "CV_CONTENT_REVIEW_BLOCKED"
    else:
        raise AssertionError("tampered content review receipt was accepted")
    assert not connected


def test_profile_change_during_gate_blocks_before_browser(tmp_path):
    job, pdf = _paths(tmp_path)
    artifacts = _content_review_artifacts(job, pdf)
    connected = False
    base_runner = _approval_runner(pdf.resolve())

    def mutating_runner(command, **kwargs):
        result = base_runner(command, **kwargs)
        Path(artifacts["content_cv_base_path"]).write_text("Changed after review\n", encoding="utf-8")
        return result

    def factory():
        nonlocal connected
        connected = True
        raise AssertionError("changed profile must not open Chrome")

    try:
        _call(
            job,
            pdf,
            approval_runner=mutating_runner,
            chrome_factory=factory,
            **artifacts,
        )
    except ATTACH.AttachCvError as exc:
        assert exc.status == "UNVERIFIABLE"
        assert exc.error_code == "CV_CONTENT_REVIEW_CHANGED"
    else:
        raise AssertionError("changed profile was accepted")
    assert not connected
