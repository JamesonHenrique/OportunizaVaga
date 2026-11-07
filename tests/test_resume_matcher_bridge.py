"""Safety contract for the optional local Resume-Matcher bridge."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resume_matcher_bridge", ROOT / "bot" / "resume_matcher_bridge.py"
)
bridge = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bridge)


def _report(status="pass", severity="high", extractability="full", score=96, pages=1):
    return {
        "extractability": extractability,
        "overall_score": score,
        "page_count": pages,
        "checks": [{"id": "text_layer", "status": status, "severity": severity}],
    }


def test_clean_full_parse_is_approved():
    verdict = bridge._evaluate_report(_report(), "a" * 64, 10)
    assert verdict["status"] == bridge.APPROVED
    assert verdict["heuristic_only"] is True


def test_high_severity_failure_is_rejected():
    verdict = bridge._evaluate_report(_report(status="fail"), "a" * 64, 10)
    assert verdict["status"] == bridge.REJECTED


def test_warnings_require_review():
    verdict = bridge._evaluate_report(_report(status="warn", severity="medium"), "a" * 64, 10)
    assert verdict["status"] == bridge.NEEDS_REVIEW


def test_partial_or_low_score_never_auto_approves():
    assert bridge._evaluate_report(_report(extractability="partial"), "a" * 64, 10)["status"] == bridge.NEEDS_REVIEW
    assert bridge._evaluate_report(_report(score=79), "a" * 64, 10)["status"] == bridge.NEEDS_REVIEW


def test_missing_extraction_is_unverifiable():
    verdict = bridge._evaluate_report(_report(extractability="none"), "a" * 64, 10)
    assert verdict["status"] == bridge.UNVERIFIABLE


def test_malformed_report_fails_closed():
    try:
        bridge._evaluate_report({"extractability": "full", "overall_score": 99}, "a" * 64, 10)
    except bridge.BridgeError:
        pass
    else:
        raise AssertionError("incomplete report must not be accepted")


def test_command_environment_does_not_forward_credentials(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("OV_RESUME_MATCHER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OV_RESUME_MATCHER_CLI", "/bin/true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-value")
    env = bridge._safe_environment(bridge._data_dir())
    assert "OPENAI_API_KEY" not in env
    assert env["DATA_DIR"] == str(data_dir.resolve())


def test_score_draft_uses_structured_resume_and_job_keywords(monkeypatch, tmp_path):
    resume_file = tmp_path / "resume.json"
    keywords_file = tmp_path / "keywords.json"
    resume_file.write_text(json.dumps({"summary": "Java developer"}), encoding="utf-8")
    keywords_file.write_text(json.dumps({"required_skills": ["Java"]}), encoding="utf-8")

    def fake_run(tool, arguments, timeout):
        assert tool == "score_resume"
        assert f"resume_data:=@{resume_file}" in arguments
        assert f"keywords:=@{keywords_file}" in arguments
        return {
            "overall_score": 88.0,
            "keyword_match_percentage": 100.0,
            "sub_scores": {"keyword_match": 100.0},
            "missing_keywords": [],
            "injectable_keywords": [],
            "recommendations": [],
        }

    monkeypatch.setattr(bridge, "_run_tool", fake_run)
    result = bridge.score_draft(str(resume_file), str(keywords_file))
    assert result["heuristic_only"] is True
    assert result["overall_score"] == 88.0


def _make_manifest(monkeypatch, tmp_path):
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfictitious candidate resume\n")
    job = tmp_path / "synthetic-job.txt"
    job.write_text("Fictitious Java role; no real applicant data.", encoding="utf-8")
    manifest_dir = tmp_path / "private-manifests"
    manifest_dir.mkdir(mode=0o700)
    manifest_dir.chmod(0o700)
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "c" * 40)
    monkeypatch.setattr(
        bridge,
        "_run_tool",
        lambda tool, arguments, timeout: _report(),
    )
    result = bridge.parse_check(str(pdf), str(job), str(manifest_dir))
    return pdf, job, manifest_dir, result


def test_approved_manifest_binds_exact_job_and_pdf_hashes(monkeypatch, tmp_path):
    pdf, job, manifests, result = _make_manifest(monkeypatch, tmp_path)
    assert result["status"] == bridge.APPROVED
    assert len(result["manifest_id"]) == 129
    assert len(list(manifests.glob("*.json"))) == 1
    record = json.loads(next(manifests.glob("*.json")).read_text(encoding="utf-8"))
    assert "Fictitious Java role" not in json.dumps(record)
    assert "fictitious candidate resume" not in json.dumps(record)
    assert bridge.verify_manifest(str(pdf), str(job), str(manifests))["manifest_id"] == result["manifest_id"]


def test_manifest_is_idempotent_for_the_same_approved_hash_pair(monkeypatch, tmp_path):
    pdf, job, manifests, first = _make_manifest(monkeypatch, tmp_path)
    second = bridge.parse_check(str(pdf), str(job), str(manifests))
    assert second["manifest_id"] == first["manifest_id"]
    assert len(list(manifests.glob("*.json"))) == 1


def test_manifest_rejects_changed_job_or_pdf(monkeypatch, tmp_path):
    pdf, job, manifests, _ = _make_manifest(monkeypatch, tmp_path)
    job.write_text("Different fictitious vacancy", encoding="utf-8")
    try:
        bridge.verify_manifest(str(pdf), str(job), str(manifests))
    except bridge.BridgeError:
        pass
    else:
        raise AssertionError("changed job must not reuse an old approval")

    job.write_text("Fictitious Java role; no real applicant data.", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4\nchanged fictitious resume\n")
    try:
        bridge.verify_manifest(str(pdf), str(job), str(manifests))
    except bridge.BridgeError:
        pass
    else:
        raise AssertionError("changed PDF must not reuse an old approval")


def test_manifest_rejects_a_different_resume_matcher_revision(monkeypatch, tmp_path):
    pdf, job, manifests, _ = _make_manifest(monkeypatch, tmp_path)
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d" * 40)
    try:
        bridge.verify_manifest(str(pdf), str(job), str(manifests))
    except bridge.BridgeError:
        pass
    else:
        raise AssertionError("an approval from another configured revision must not be reused")


def test_manifest_requires_a_pinned_revision(monkeypatch, tmp_path):
    pdf, job, manifests, _ = _make_manifest(monkeypatch, tmp_path)
    monkeypatch.delenv("OV_RESUME_MATCHER_REVISION")
    try:
        bridge.verify_manifest(str(pdf), str(job), str(manifests))
    except bridge.BridgeError:
        pass
    else:
        raise AssertionError("manifest verification must require an exact upstream commit")
