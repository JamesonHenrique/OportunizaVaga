"""Synthetic coverage for the fail-closed Resume-Matcher application-intent gate."""

import hashlib
import importlib.util
import json
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

from bot import job_requirement_review
from bot import cv_content_review
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
STATE_SPEC = importlib.util.spec_from_file_location("ov_estado_cv_test", ROOT / "bot" / "estado.py")
assert STATE_SPEC is not None and STATE_SPEC.loader is not None
STATE = importlib.util.module_from_spec(STATE_SPEC)
STATE_SPEC.loader.exec_module(STATE)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pdf_bytes() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(72, 760, "Synthetic candidate")
    document.drawString(72, 740, "Java and Spring Boot project experience")
    document.save()
    return output.getvalue()


def _script(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(0o700)
    return path


def _requirement_artifacts(tmp_path: Path, announcement: Path, title: str, *, required_status=None):
    profile = {
        "summary": "Synthetic profile for tests.",
        "workExperience": [],
        "personalProjects": [],
        "education": [],
        "additional": {"technicalSkills": [], "languages": [], "certificationsTraining": []},
        "customSections": {},
    }
    profile_bytes = json.dumps(profile, sort_keys=True).encode("utf-8")
    proposal = job_requirement_review.build_proposal(announcement.read_bytes(), title, profile_bytes)
    candidates = proposal["candidates"]
    review_sheet = {
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
        assert candidates
        review_sheet["assessments"][0].update(required=True, status=required_status)
    assessment, receipt = job_requirement_review.approve_review(
        announcement.read_bytes(), profile_bytes, proposal, review_sheet,
    )
    paths = {
        "cv_requirements_profile_path": tmp_path / "requirements-profile.json",
        "cv_requirements_assessment_path": tmp_path / "requirements-assessment.json",
        "cv_requirements_receipt_path": tmp_path / "requirements-receipt.json",
    }
    paths["cv_requirements_profile_path"].write_bytes(profile_bytes)
    paths["cv_requirements_assessment_path"].write_text(json.dumps(assessment), encoding="utf-8")
    paths["cv_requirements_receipt_path"].write_text(json.dumps(receipt), encoding="utf-8")
    for path in paths.values():
        path.chmod(0o600)
    return {key: str(path) for key, path in paths.items()}


def _content_review_artifacts(tmp_path: Path, announcement: Path, attachment: Path):
    cv_base = tmp_path / "cv_base.md"
    cv_base.write_text(
        "Synthetic candidate\nJava and Spring Boot project experience\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate-data.json"
    candidate.write_text(json.dumps({"candidate": "Synthetic"}), encoding="utf-8")
    proposal = cv_content_review.build_proposal(
        job_path=announcement,
        pdf_path=attachment,
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
                "cv_base.md:L0001" if "Synthetic candidate" in claim["text"] else "cv_base.md:L0002"
            ],
        }
        for claim in proposal["claims"]
    ]
    assessment, receipt, result = cv_content_review.approve_review(
        proposal=proposal,
        review=review,
        job_path=announcement,
        pdf_path=attachment,
        cv_base_path=cv_base,
        candidate_data_path=candidate,
    )
    assert result["status"] == "APPROVED"
    paths = {
        "cv_content_cv_base_path": cv_base,
        "cv_content_candidate_data_path": candidate,
        "cv_content_proposal_path": tmp_path / "content-proposal.json",
        "cv_content_assessment_path": tmp_path / "content-assessment.json",
        "cv_content_receipt_path": tmp_path / "content-receipt.json",
    }
    for key, value in (
        ("cv_content_proposal_path", proposal),
        ("cv_content_assessment_path", assessment),
        ("cv_content_receipt_path", receipt),
    ):
        paths[key].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    for path in paths.values():
        path.chmod(0o600)
    return {key: str(path) for key, path in paths.items()}


def _setup(
    tmp_path, monkeypatch, *, browser_status="APPROVED", browser_hash=None,
    recommendation=None, required_status=None,
):
    announcement = tmp_path / "synthetic-job.txt"
    announcement.write_text(
        "Fictitious junior role, remote, minimum 1 year of experience.", encoding="utf-8"
    )
    attachment = tmp_path / "synthetic-resume.pdf"
    attachment.write_bytes(_pdf_bytes())
    expected = _sha(attachment)
    selected = browser_hash or expected

    ready_gate = _script(
        tmp_path / "fake-cv-ready-gate.py",
        """
import hashlib, json, pathlib, sys
announcement, pdf = map(pathlib.Path, sys.argv[1:3])
job_sha = hashlib.sha256(announcement.read_bytes()).hexdigest()
pdf_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
print(json.dumps({
    "status": "APPROVED", "manifest_verified": True,
    "manifest_id": f"{job_sha}-{pdf_sha}",
    "job_description_sha256": job_sha, "pdf_sha256": pdf_sha, "sha256": pdf_sha,
    "resume_matcher_revision": "a" * 40, "verifier_policy_version": 1,
    "verified_at": "synthetic-timestamp"
}))
print("ANEXAR " + str(pdf.resolve()))
""",
    )
    browser_gate = _script(
        tmp_path / "fake-browser-gate.py",
        f"""
import json, sys
expected = sys.argv[sys.argv.index("--expected-sha256") + 1]
selected = {selected!r}
status = {browser_status!r}
print(json.dumps({{
    "status": status, "expected_sha256": expected,
    "selected_sha256": selected, "input_count": 1,
    "selected_file_count": 1, "matching_file_count": 1 if selected == expected else 0,
    "verified_at": "synthetic-timestamp"
}}))
sys.exit(0 if status == "APPROVED" and selected == expected else 1)
""",
    )
    monkeypatch.setenv("OV_CV_READY_GATE", str(ready_gate))
    monkeypatch.setenv("OV_CV_BROWSER_GATE", str(browser_gate))

    job_sha = _sha(announcement)
    reference = {
        "cv_manifest_id": f"{job_sha}-{expected}",
        "cv_job_sha256": job_sha,
        "cv_pdf_sha256": expected,
    }
    info = {
        "empresa": "Ficticia",
        "vaga": "Desenvolvedora Júnior",
        "url": "https://jobs.example.invalid/application/123",
        "cv_job_key": "ficticia_dev_jr_1",
        "cv_job_company": "Ficticia",
        "cv_job_title": "Desenvolvedora Júnior",
        "cv_announcement_path": str(announcement),
        "cv_attachment_path": str(attachment),
        "cv_browser_url_prefix": "https://jobs.example.invalid/application/123",
        "cv_browser_input_selector": 'input[type="file"][name="resume"]',
        **reference,
        **_requirement_artifacts(
            tmp_path, announcement, "Desenvolvedora Júnior", required_status=required_status,
        ),
        **_content_review_artifacts(tmp_path, announcement, attachment),
    }
    if recommendation is not None:
        info["cv_compatibility_recommendation"] = recommendation
    return announcement, attachment, info, reference


def _run(tmp_path, info, state_path=None):
    state_path = state_path or tmp_path / "aplicadas.json"
    if not state_path.exists():
        state_path.write_text('{"aplicadas": []}\n', encoding="utf-8")
    rc = STATE.main_travado(["--file", str(state_path), "intencao", "ficticia_dev_jr_1", json.dumps(info)])
    return rc, state_path


def test_approved_manifest_records_hashes_but_not_paths_or_browser_details(tmp_path, monkeypatch):
    _announcement, _attachment, info, reference = _setup(tmp_path, monkeypatch)

    rc, state_path = _run(tmp_path, info)

    assert rc == 0
    pending = json.loads(state_path.read_text(encoding="utf-8"))["envios_pendentes"]["ficticia_dev_jr_1"]
    assert all(pending[key] == value for key, value in reference.items())
    assert pending["cv_job_key"] == "ficticia_dev_jr_1"
    assert pending["cv_job_company"] == "Ficticia"
    assert pending["cv_job_title"] == "Desenvolvedora Júnior"
    assert pending["cv_requirement_status"] == "APPROVED"
    assert pending["cv_requirement_required_barrier_count"] == 0
    assert pending["cv_content_review_status"] == "APPROVED"
    assert pending["cv_content_claim_count"] == (
        pending["cv_content_supported_claim_count"] + pending["cv_content_non_factual_claim_count"]
    )
    for field in STATE.CV_REQUIREMENT_AUDIT_FIELDS[:4]:
        assert len(pending[field]) == 64
    assert not any(key.startswith("cv_announcement_path") for key in pending)
    assert "cv_attachment_path" not in pending
    assert "cv_browser_url_prefix" not in pending
    assert "cv_browser_input_selector" not in pending
    assert not any(key in pending for key in STATE.CV_REQUIREMENT_REVIEW_PATH_FIELDS)
    assert not any(key in pending for key in STATE.CV_CONTENT_REVIEW_PATH_FIELDS)

    applied = {"chave": "ficticia_dev_jr_1", "empresa": "Ficticia", "vaga": "Desenvolvedora Júnior"}
    assert STATE.main_travado(["--file", str(state_path), "add-aplicada", json.dumps(applied)]) == 0
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert all(saved["aplicadas"][0][key] == value for key, value in reference.items())
    assert saved["aplicadas"][0]["cv_job_key"] == "ficticia_dev_jr_1"
    assert saved["aplicadas"][0]["cv_job_company"] == "Ficticia"
    assert saved["aplicadas"][0]["cv_job_title"] == "Desenvolvedora Júnior"
    assert saved["aplicadas"][0]["cv_requirement_status"] == "APPROVED"
    assert saved["aplicadas"][0]["cv_content_review_status"] == "APPROVED"


def test_wrong_application_identity_is_rejected_before_document_gate(tmp_path, monkeypatch, capsys):
    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch)
    for field, value in (
        ("cv_job_key", "different_application_key"),
        ("cv_job_company", "Other Employer"),
        ("cv_job_title", "Different Junior Role"),
    ):
        candidate = dict(info)
        candidate[field] = value
        rc, state_path = _run(tmp_path, candidate, tmp_path / f"{field}.json")
        assert rc == 2
        assert "envios_pendentes" not in json.loads(state_path.read_text(encoding="utf-8"))


def test_same_round_retry_cannot_drop_an_existing_cv_reference(tmp_path, monkeypatch):
    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("OV_RODADA", "synthetic-round")
    rc, state_path = _run(tmp_path, info)
    assert rc == 0

    retry = dict(info)
    for key in (*STATE.CV_ARTIFACT_PATH_FIELDS, *STATE.CV_BROWSER_FIELDS, *STATE.CV_MANIFEST_FIELDS,
                *STATE.CV_REQUIREMENT_REVIEW_PATH_FIELDS, *STATE.CV_REQUIREMENT_AUDIT_FIELDS,
                *STATE.CV_CONTENT_REVIEW_PATH_FIELDS, *STATE.CV_CONTENT_REVIEW_AUDIT_FIELDS,
                *STATE.CV_JOB_BINDING_FIELDS,
                "cv_compatibility_recommendation"):
        retry.pop(key, None)
    rc = STATE.main_travado([
        "--file", str(state_path), "intencao", "ficticia_dev_jr_1", json.dumps(retry)
    ])

    assert rc == 1
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["envios_pendentes"]["ficticia_dev_jr_1"]["cv_pdf_sha256"] == _reference_from(info)


def _reference_from(info):
    return info["cv_pdf_sha256"]


def test_wrong_browser_file_blocks_intent_without_state_change(tmp_path, monkeypatch):
    wrong = hashlib.sha256(b"different synthetic file").hexdigest()
    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch, browser_hash=wrong)
    state_path = tmp_path / "aplicadas.json"
    original = '{"aplicadas": []}\n'
    state_path.write_text(original, encoding="utf-8")

    rc, _ = _run(tmp_path, info, state_path)

    assert rc == 2
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"aplicadas": []}


def test_missing_browser_selector_and_invalid_reference_fail_closed(tmp_path, monkeypatch):
    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch)
    info.pop("cv_browser_input_selector")
    rc, state_path = _run(tmp_path, info)
    assert rc == 2
    assert "envios_pendentes" not in json.loads(state_path.read_text(encoding="utf-8"))

    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch)
    info["cv_manifest_id"] = "not-a-manifest"
    rc, state_path = _run(tmp_path, info, tmp_path / "invalid.json")
    assert rc == 2
    assert "envios_pendentes" not in json.loads(state_path.read_text(encoding="utf-8"))


def test_paths_without_manifest_and_do_not_prepare_are_rejected(tmp_path, monkeypatch, capsys):
    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch)
    for key in (*STATE.CV_ARTIFACT_PATH_FIELDS, *STATE.CV_BROWSER_FIELDS,
                *STATE.CV_REQUIREMENT_REVIEW_PATH_FIELDS, *STATE.CV_REQUIREMENT_AUDIT_FIELDS,
                *STATE.CV_JOB_BINDING_FIELDS, "cv_compatibility_recommendation", *STATE.CV_MANIFEST_FIELDS):
        info.pop(key, None)
    info["cv_attachment_path"] = "/tmp/synthetic.pdf"
    rc, state_path = _run(tmp_path, info)
    assert rc == 2
    assert "referência completa do CV" in capsys.readouterr().out
    assert "envios_pendentes" not in json.loads(state_path.read_text(encoding="utf-8"))

    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch)
    for key in (*STATE.CV_ARTIFACT_PATH_FIELDS, *STATE.CV_BROWSER_FIELDS, *STATE.CV_MANIFEST_FIELDS,
                *STATE.CV_REQUIREMENT_REVIEW_PATH_FIELDS, *STATE.CV_REQUIREMENT_AUDIT_FIELDS,
                *STATE.CV_JOB_BINDING_FIELDS,
                "cv_compatibility_recommendation"):
        info.pop(key, None)
    info["cv"] = "synthetic-cv.pdf"
    rc, state_path = _run(tmp_path, info, tmp_path / "cv-label-without-manifest.json")
    assert rc == 2
    assert "referência completa do CV" in capsys.readouterr().out
    assert not json.loads(state_path.read_text(encoding="utf-8")).get("envios_pendentes")

    _announcement, _attachment, info, _reference = _setup(tmp_path, monkeypatch, recommendation="DO_NOT_PREPARE")
    rc, state_path = _run(tmp_path, info, tmp_path / "do-not-prepare.json")
    assert rc == 2
    assert "envios_pendentes" not in json.loads(state_path.read_text(encoding="utf-8"))


def test_legacy_intent_without_cv_reference_remains_compatible(tmp_path, monkeypatch):
    monkeypatch.delenv("OV_CV_READY_GATE", raising=False)
    monkeypatch.delenv("OV_CV_BROWSER_GATE", raising=False)
    info = {"empresa": "Legacy", "vaga": "Junior role", "url": "https://jobs.example.invalid/legacy"}

    rc, state_path = _run(tmp_path, info, tmp_path / "legacy.json")

    assert rc == 0
    pending = json.loads(state_path.read_text(encoding="utf-8"))["envios_pendentes"]["ficticia_dev_jr_1"]
    assert pending["empresa"] == "Legacy"
    assert not any(key.startswith("cv_") for key in pending)


def test_artifact_change_after_preflight_blocks_state_write(tmp_path, monkeypatch):
    _announcement, attachment, info, _reference = _setup(tmp_path, monkeypatch)
    state_path = tmp_path / "changed.json"
    state_path.write_text('{"aplicadas": []}\n', encoding="utf-8")

    @contextmanager
    def mutate_between_preflight_and_lock(_path):
        attachment.write_bytes(b"%PDF-1.4\nchanged after preflight\n")
        yield

    monkeypatch.setattr(STATE, "travado", mutate_between_preflight_and_lock)
    rc, _ = _run(tmp_path, info, state_path)

    assert rc == 2
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"aplicadas": []}


def test_required_requirement_barriers_and_invalid_receipts_block_intent(tmp_path, monkeypatch, capsys):
    for required_status, expected_status in (("UNCONFIRMED", "NEEDS_REVIEW"), ("NOT_MET", "REJECTED")):
        case = tmp_path / required_status
        case.mkdir()
        _announcement, _attachment, info, _reference = _setup(
            case, monkeypatch, required_status=required_status,
        )
        rc, state_path = _run(case, info)
        assert rc == 2
        assert not json.loads(state_path.read_text(encoding="utf-8")).get("envios_pendentes")
        assert f"typed requirement review returned {expected_status}" in capsys.readouterr().out

    case = tmp_path / "tampered"
    case.mkdir()
    _announcement, _attachment, info, _reference = _setup(case, monkeypatch)
    Path(info["cv_requirements_receipt_path"]).write_text("{}", encoding="utf-8")
    rc, state_path = _run(case, info)
    assert rc == 2
    assert not json.loads(state_path.read_text(encoding="utf-8")).get("envios_pendentes")
    assert "typed requirement review is unverifiable" in capsys.readouterr().out


def test_missing_or_tampered_final_content_review_blocks_intent(tmp_path, monkeypatch, capsys):
    missing_dir = tmp_path / "missing-content"
    missing_dir.mkdir()
    _announcement, _attachment, info, _reference = _setup(missing_dir, monkeypatch)
    info.pop("cv_content_receipt_path")
    rc, state_path = _run(missing_dir, info)
    assert rc == 2
    assert not json.loads(state_path.read_text(encoding="utf-8")).get("envios_pendentes")
    assert "final factual content review" in capsys.readouterr().out

    tampered_dir = tmp_path / "tampered-content"
    tampered_dir.mkdir()
    _announcement, _attachment, info, _reference = _setup(tampered_dir, monkeypatch)
    Path(info["cv_content_receipt_path"]).write_text("{}", encoding="utf-8")
    rc, state_path = _run(tampered_dir, info)
    assert rc == 2
    assert not json.loads(state_path.read_text(encoding="utf-8")).get("envios_pendentes")
    assert "final factual content review" in capsys.readouterr().out
