from __future__ import annotations

import json
import os
import subprocess
import sys
import copy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "bot"
sys.path.insert(0, str(BOT))

import compatibilidade_fila as compatibility
import descobrir
import job_requirement_review


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fixture(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700, parents=True)
    queue_path = state / "vagas_fila.json"
    job_key = "synthetic:job-1"
    job_text = "Requisitos obrigatórios: Python. Diferencial: Docker. Vaga remota para pessoa desenvolvedora júnior.\n"
    cache_id, job_sha = compatibility.cache_job_description(state, job_key, job_text)
    job = {
        "id": job_key,
        "status": "nova",
        "titulo": "Pessoa Desenvolvedora Júnior",
        "url": "https://jobs.example.invalid/jobs/123",
        "desc_checada": True,
        "job_description_id": cache_id,
        "job_description_sha256": job_sha,
    }
    queue_path.write_text(json.dumps({"vagas": {job_key: job}}, ensure_ascii=False), encoding="utf-8")
    catalog_bytes = json.dumps({"technology_categories": {"backend": [
        {"name": "Python"}, {"name": "Docker"},
    ]}}).encode("utf-8")
    proposal = compatibility.job_keyword_proposal.build_proposal(
        job_text.encode("utf-8"), job["titulo"], catalog_bytes,
    )
    candidates = {candidate["term"]: candidate for candidate in proposal["candidates"]}
    review = {
        "proposal_sha256": proposal["proposal_sha256"],
        "source_job_sha256": proposal["source_job_sha256"],
        "reviewed_candidate_ids": [candidate["id"] for candidate in proposal["candidates"]],
        "selected": [
            {"candidate_id": candidates["Python"]["id"], "field": "required_skills"},
            {"candidate_id": candidates["Docker"]["id"], "field": "preferred_skills"},
        ],
        "manual_terms": [],
    }
    keywords, receipt = compatibility.job_keyword_proposal.approve_review(
        job_text.encode("utf-8"), catalog_bytes, proposal, review,
    )
    keywords_path = tmp_path / "keywords.json"
    keywords_path.write_text(json.dumps(keywords, ensure_ascii=False), encoding="utf-8")
    receipt_path = tmp_path / "review.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    profile_path = tmp_path / "resume-data.json"
    profile_bytes = json.dumps({
        "summary": "Synthetic junior developer with Python practice.",
        "workExperience": [{
            "id": 1, "title": "Synthetic internship", "company": "",
            "years": "", "description": ["Validated synthetic integrations."],
        }],
        "personalProjects": [{
            "id": 1, "name": "Synthetic API", "role": "",
            "years": "", "description": ["Built a fictional REST API in Python."],
        }],
        "education": [],
        "additional": {
            "technicalSkills": ["Python"], "languages": [],
            "certificationsTraining": [], "awards": [],
        },
        "customSections": {},
    }).encode()
    profile_path.write_bytes(profile_bytes)
    if os.name == "posix":
        profile_path.chmod(0o600)
    return queue_path, job_key, job, keywords_path, receipt_path, profile_path


def _score(_resume_path: str, _keywords_path: str) -> dict:
    return {
        "heuristic_only": True,
        "keyword_match_percentage": 67.5,
        "sub_scores": {"skills_coverage": 50.0},
        "missing_keywords": ["Python", "Docker"],
    }


def _requirement_review_files(
    tmp_path: Path, queue: Path, key: str, profile: Path,
) -> tuple[Path, Path]:
    job_path = compatibility.description_path_for(queue, key)
    job_bytes = job_path.read_bytes()
    profile_bytes = profile.read_bytes()
    job = json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]
    proposal = job_requirement_review.build_proposal(job_bytes, job["titulo"], profile_bytes)
    review = copy.deepcopy(proposal["review_template"])
    review["reviewed_candidate_ids"] = [candidate["id"] for candidate in proposal["candidates"]]
    review["assessments"] = [
        {
            "candidate_id": candidate["id"],
            "required": True,
            "status": "UNCONFIRMED",
            "evidence_refs": [],
        }
        for candidate in proposal["candidates"]
    ]
    assessment, receipt = job_requirement_review.approve_review(job_bytes, profile_bytes, proposal, review)
    assessment_path = tmp_path / "requirements.json"
    receipt_path = tmp_path / "requirements-receipt.json"
    assessment_path.write_bytes(_canonical(assessment))
    receipt_path.write_bytes(_canonical(receipt))
    if os.name == "posix":
        assessment_path.chmod(0o600)
        receipt_path.chmod(0o600)
    return assessment_path, receipt_path


def test_analysis_persists_only_advisory_hash_bound_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OV_DISCOVERY_PROFILE_SHA256", raising=False)
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)

    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt), persist=True, score_runner=_score,
    )

    current_queue = json.loads(queue.read_text(encoding="utf-8"))
    job = current_queue["vagas"][key]
    assert report["status"] == "ANALYZED"
    assert report["recommendation"] == "REVIEW_PROFILE_GAPS"
    assert report["required_gaps"] == ["Python"]
    assert report["preferred_gaps"] == ["Docker"]
    assert report["requirements_review"]["status"] == "NOT_REVIEWED"
    assert report["requirements_review"]["recommendation"] == "REVIEW_REQUIRED"
    assert report["evidence_match_method"] == "literal_normalized_terms"
    assert report["evidence_by_keyword"]["Python"] == ["summary", "personalProjects#1", "additional.technicalSkills"]
    assert report["evidence_by_keyword"]["Docker"] == []
    assert compatibility.report_is_current(queue, key, job, report)
    assert "RM heurístico 67.5%" in descobrir.compatibilidade_resume_matcher(job, queue)
    assert "requisitos sem revisão" in descobrir.compatibilidade_resume_matcher(job, queue)
    assert not any("resume-data" in value for value in report.values() if isinstance(value, str))
    assert "synthetic project" not in json.dumps(job[compatibility.REPORT_FIELD])


def test_hash_bound_requirement_review_is_included_and_required_barriers_override_recommendation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OV_DISCOVERY_PROFILE_SHA256", raising=False)
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    assessment, requirement_receipt = _requirement_review_files(tmp_path, queue, key, profile)
    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt),
        requirements_value=str(assessment), requirements_receipt_value=str(requirement_receipt),
        persist=True, score_runner=_score,
    )
    assert report["requirements_review"]["status"] == "APPROVED"
    assert report["requirements_review"]["required_barrier_count"] == len(
        job_requirement_review.build_proposal(
            compatibility.description_path_for(queue, key).read_bytes(),
            _job["titulo"], profile.read_bytes(),
        )["candidates"]
    )
    assert report["recommendation"] == "REVIEW_POSSIBLE_BARRIER"
    assert str(assessment) not in json.dumps(report)
    assert "Vaga remota" not in json.dumps(report)
    assert compatibility.report_is_current(queue, key, json.loads(queue.read_text())["vagas"][key], report)
    assert "possíveis barreiras obrigatórias" in descobrir.compatibilidade_resume_matcher(
        json.loads(queue.read_text())["vagas"][key], queue,
    )


def test_stale_or_partial_requirement_review_blocks_scoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    assessment, requirement_receipt = _requirement_review_files(tmp_path, queue, key, profile)
    with pytest.raises(compatibility.QueueCompatibilityError, match="supplied together"):
        compatibility.analyze_queue_job(
            queue_path_value=str(queue), key=key, resume_data_value=str(profile),
            keywords_value=str(keywords), receipt_value=str(receipt),
            requirements_value=str(assessment), score_runner=_score,
        )
    modified_assessment = json.loads(assessment.read_text(encoding="utf-8"))
    modified_assessment["limitations"].append("tampered")
    assessment.write_text(json.dumps(modified_assessment), encoding="utf-8")
    with pytest.raises(compatibility.QueueCompatibilityError, match="stale, incomplete, or invalid"):
        compatibility.analyze_queue_job(
            queue_path_value=str(queue), key=key, resume_data_value=str(profile),
            keywords_value=str(keywords), receipt_value=str(receipt),
            requirements_value=str(assessment), requirements_receipt_value=str(requirement_receipt),
            score_runner=_score,
        )


def test_requirement_review_file_change_hides_persisted_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    assessment, requirement_receipt = _requirement_review_files(tmp_path, queue, key, profile)
    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt),
        requirements_value=str(assessment), requirements_receipt_value=str(requirement_receipt),
        persist=True, score_runner=_score,
    )
    assessment_path = compatibility._sidecar_path(queue, key)
    job = json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]
    assert compatibility.report_is_current(queue, key, job, report)
    modified = json.loads(assessment.read_text(encoding="utf-8"))
    modified["limitations"].append("stale")
    assessment.write_text(json.dumps(modified), encoding="utf-8")
    assert not compatibility.report_is_current(queue, key, job, report)
    assert "stale" not in assessment_path.read_text(encoding="utf-8")


def test_requirement_review_change_during_score_discards_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    assessment, requirement_receipt = _requirement_review_files(tmp_path, queue, key, profile)

    def mutate_review(_resume_path: str, _keywords_path: str) -> dict:
        value = json.loads(assessment.read_text(encoding="utf-8"))
        value["limitations"].append("changed during scoring")
        assessment.write_text(json.dumps(value), encoding="utf-8")
        return _score(_resume_path, _keywords_path)

    with pytest.raises(compatibility.QueueCompatibilityError, match="stale, incomplete, or invalid"):
        compatibility.analyze_queue_job(
            queue_path_value=str(queue), key=key, resume_data_value=str(profile),
            keywords_value=str(keywords), receipt_value=str(receipt),
            requirements_value=str(assessment), requirements_receipt_value=str(requirement_receipt),
            persist=True, score_runner=mutate_review,
        )
    assert compatibility.REPORT_FIELD not in json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]


def test_profile_change_invalidates_persisted_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OV_DISCOVERY_PROFILE_SHA256", raising=False)
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt), persist=True, score_runner=_score,
    )
    profile.write_text('{"skills":["Python","Rust"]}', encoding="utf-8")
    if os.name == "posix":
        profile.chmod(0o600)
    job = json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]
    assert not compatibility.report_is_current(queue, key, job, report)
    assert descobrir.compatibilidade_resume_matcher(job, queue) == ""


def test_job_description_change_invalidates_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt), persist=True, score_runner=_score,
    )
    cached = compatibility.description_path_for(queue, key)
    cached.write_text("Updated synthetic posting text.", encoding="utf-8")
    job = json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]
    assert not compatibility.report_is_current(queue, key, job, report)


@pytest.mark.skipif(os.name != "posix", reason="POSIX owner-only directory permissions")
def test_non_private_sidecar_directory_hides_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt), persist=True, score_runner=_score,
    )
    sidecar_dir = compatibility._sidecar_path(queue, key).parent
    sidecar_dir.chmod(0o755)
    job = json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]
    assert not compatibility.report_is_current(queue, key, job, report)


def test_queue_identity_change_during_scoring_prevents_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)

    def change_queue(_resume_path: str, _keywords_path: str) -> dict:
        value = json.loads(queue.read_text(encoding="utf-8"))
        value["vagas"][key]["titulo"] = "Different synthetic title"
        queue.write_text(json.dumps(value), encoding="utf-8")
        return _score(_resume_path, _keywords_path)

    with pytest.raises(compatibility.QueueCompatibilityError, match="changed while"):
        compatibility.analyze_queue_job(
            queue_path_value=str(queue), key=key, resume_data_value=str(profile),
            keywords_value=str(keywords), receipt_value=str(receipt), persist=True, score_runner=change_queue,
        )
    assert compatibility.REPORT_FIELD not in json.loads(queue.read_text(encoding="utf-8"))["vagas"][key]


def test_review_receipt_and_private_profile_are_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    receipt.write_text('{"status":"APPROVED","source_job_sha256":"wrong","keywords_sha256":"wrong"}')
    with pytest.raises(compatibility.QueueCompatibilityError, match="receipt"):
        compatibility.analyze_queue_job(
            queue_path_value=str(queue), key=key, resume_data_value=str(profile),
            keywords_value=str(keywords), receipt_value=str(receipt), score_runner=_score,
        )

    # Rebuild the fixture to isolate the private-file permission check.
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path / "second")
    if os.name == "posix":
        profile.chmod(0o644)
        with pytest.raises(compatibility.QueueCompatibilityError, match="only by the current user"):
            compatibility.analyze_queue_job(
                queue_path_value=str(queue), key=key, resume_data_value=str(profile),
                keywords_value=str(keywords), receipt_value=str(receipt), score_runner=_score,
            )


def test_analysis_uses_installed_pinned_resume_matcher_on_synthetic_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = Path.home() / "tools" / "Resume-Matcher" / "apps" / "backend" / ".venv" / "bin" / "resume-matcher"
    if not cli.is_file():
        pytest.skip("Pinned local Resume-Matcher CLI is unavailable")
    monkeypatch.setenv("OV_RESUME_MATCHER_CLI", str(cli))
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    data_dir = tmp_path / "matcher-data"
    data_dir.mkdir(mode=0o700)
    monkeypatch.setenv("OV_RESUME_MATCHER_DATA_DIR", str(data_dir))
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)

    report = compatibility.analyze_queue_job(
        queue_path_value=str(queue), key=key, resume_data_value=str(profile),
        keywords_value=str(keywords), receipt_value=str(receipt), persist=True,
    )

    assert report["status"] == "ANALYZED"
    assert report["heuristic_only"] is True
    assert report["resume_matcher_revision"] == "d480551798b7aa97f5b57ba1972ee383bd882238"
    assert 0 <= report["score"]["keyword_match_percentage"] <= 100
    assert compatibility.report_is_current(
        queue, key, json.loads(queue.read_text(encoding="utf-8"))["vagas"][key], report,
    )


def test_batch_is_sequential_isolated_and_continues_after_unverifiable_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, first_key, first_job, keywords, receipt, profile = _fixture(tmp_path)
    requirement_assessment, requirement_receipt = _requirement_review_files(
        tmp_path, queue, first_key, profile,
    )
    queue_data = json.loads(queue.read_text(encoding="utf-8"))
    jobs = queue_data["vagas"]
    jobs["synthetic:job-2"] = {**first_job, "id": "synthetic:job-2", "status": "enviada"}
    third_key = "synthetic:job-3"
    description = compatibility.description_path_for(queue, first_key).read_text(encoding="utf-8")
    description_id, description_sha = compatibility.cache_job_description(queue.parent, third_key, description)
    jobs[third_key] = {
        **first_job,
        "id": third_key,
        "url": "https://jobs.example.invalid/jobs/789",
        "job_description_id": description_id,
        "job_description_sha256": description_sha,
    }
    queue.write_text(json.dumps(queue_data, ensure_ascii=False), encoding="utf-8")

    manifest_path = tmp_path / "batch.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "jobs": [
        {
            "key": first_key, "resume_data": str(profile), "keywords": str(keywords),
            "review_receipt": str(receipt), "requirements": str(requirement_assessment),
            "requirements_receipt": str(requirement_receipt),
        },
        {"key": "synthetic:job-2", "resume_data": str(profile), "keywords": str(keywords), "review_receipt": str(receipt)},
        {
            "key": third_key, "resume_data": str(profile), "keywords": str(keywords),
            "review_receipt": str(receipt), "requirements": str(requirement_assessment),
            "requirements_receipt": str(requirement_receipt),
        },
    ]}), encoding="utf-8")
    if os.name == "posix":
        manifest_path.chmod(0o600)

    calls = 0

    def counted_score(resume_path: str, keywords_path: str) -> dict:
        nonlocal calls
        calls += 1
        return _score(resume_path, keywords_path)

    result = compatibility.analyze_queue_batch(
        queue_path_value=str(queue), manifest_value=str(manifest_path),
        persist=True, score_runner=counted_score,
    )

    assert result["status"] == "PARTIAL"
    assert result["sequential"] is True
    assert result["analyzed_count"] == 2
    assert result["unverifiable_count"] == 1
    assert [item["status"] for item in result["jobs"]] == ["ANALYZED", "UNVERIFIABLE", "ANALYZED"]
    assert calls == 2
    saved = json.loads(queue.read_text(encoding="utf-8"))["vagas"]
    assert compatibility.REPORT_FIELD in saved[first_key]
    assert compatibility.REPORT_FIELD not in saved["synthetic:job-2"]
    assert compatibility.REPORT_FIELD in saved[third_key]
    assert result["jobs"][0]["report"]["requirements_review"]["status"] == "APPROVED"
    assert result["jobs"][2]["report"]["recommendation"] == "REVIEW_POSSIBLE_BARRIER"
    assert str(profile) not in json.dumps(result)


def test_batch_rejects_duplicate_keys_before_scoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    entry = {"key": key, "resume_data": str(profile), "keywords": str(keywords), "review_receipt": str(receipt)}
    manifest_path = tmp_path / "batch.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "jobs": [entry, entry]}), encoding="utf-8")
    if os.name == "posix":
        manifest_path.chmod(0o600)
    calls = 0

    def unexpected_score(_resume_path: str, _keywords_path: str) -> dict:
        nonlocal calls
        calls += 1
        return _score(_resume_path, _keywords_path)

    with pytest.raises(compatibility.QueueCompatibilityError, match="duplicate queue keys"):
        compatibility.analyze_queue_batch(
            queue_path_value=str(queue), manifest_value=str(manifest_path), score_runner=unexpected_score,
        )
    assert calls == 0


def test_batch_requires_requirement_assessment_and_receipt_as_a_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OV_RESUME_MATCHER_REVISION", "d480551798b7aa97f5b57ba1972ee383bd882238")
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    manifest_path = tmp_path / "batch.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "jobs": [{
        "key": key, "resume_data": str(profile), "keywords": str(keywords),
        "review_receipt": str(receipt), "requirements": str(tmp_path / "missing-requirements.json"),
    }]}), encoding="utf-8")
    if os.name == "posix":
        manifest_path.chmod(0o600)
    calls = 0

    def unexpected_score(_resume_path: str, _keywords_path: str) -> dict:
        nonlocal calls
        calls += 1
        return _score(_resume_path, _keywords_path)

    with pytest.raises(compatibility.QueueCompatibilityError, match="both requirement review files"):
        compatibility.analyze_queue_batch(
            queue_path_value=str(queue), manifest_value=str(manifest_path), score_runner=unexpected_score,
        )
    assert calls == 0


def test_batch_cli_runs_pinned_matcher_on_synthetic_inputs(tmp_path: Path) -> None:
    cli = Path.home() / "tools" / "Resume-Matcher" / "apps" / "backend" / ".venv" / "bin" / "resume-matcher"
    if not cli.is_file():
        pytest.skip("Pinned local Resume-Matcher CLI is unavailable")
    queue, key, job, keywords, receipt, profile = _fixture(tmp_path)
    queue_data = json.loads(queue.read_text(encoding="utf-8"))
    queue_data["vagas"]["synthetic:already-sent"] = {
        **job, "id": "synthetic:already-sent", "status": "enviada",
    }
    queue.write_text(json.dumps(queue_data, ensure_ascii=False), encoding="utf-8")
    manifest_path = tmp_path / "batch.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "jobs": [{
        "key": key,
        "resume_data": str(profile),
        "keywords": str(keywords),
        "review_receipt": str(receipt),
    }, {
        "key": "synthetic:already-sent",
        "resume_data": str(profile),
        "keywords": str(keywords),
        "review_receipt": str(receipt),
    }]}), encoding="utf-8")
    data_dir = tmp_path / "matcher-data"
    data_dir.mkdir(mode=0o700)
    if os.name == "posix":
        manifest_path.chmod(0o600)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(Path.home()),
        "OV_RESUME_MATCHER_CLI": str(cli),
        "OV_RESUME_MATCHER_REVISION": "d480551798b7aa97f5b57ba1972ee383bd882238",
        "OV_RESUME_MATCHER_DATA_DIR": str(data_dir),
        "PYTHONIOENCODING": "utf-8",
    }

    completed = subprocess.run(
        [sys.executable, str(BOT / "compatibilidade_fila.py"), "analyze-batch",
         "--queue", str(queue), "--manifest", str(manifest_path)],
        check=False, capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )

    assert completed.returncode == 1, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "PARTIAL"
    assert result["analyzed_count"] == 1
    assert result["unverifiable_count"] == 1
    assert result["jobs"][0]["report"]["resume_matcher_revision"] == env["OV_RESUME_MATCHER_REVISION"]
    assert result["jobs"][0]["report"]["heuristic_only"] is True
    assert result["jobs"][1]["status"] == "UNVERIFIABLE"
    assert str(profile) not in completed.stdout


def test_missing_revision_pin_blocks_before_scoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OV_RESUME_MATCHER_REVISION", raising=False)
    queue, key, _job, keywords, receipt, profile = _fixture(tmp_path)
    calls = 0

    def unexpected_score(_resume_path: str, _keywords_path: str) -> dict:
        nonlocal calls
        calls += 1
        return _score(_resume_path, _keywords_path)

    with pytest.raises(compatibility.QueueCompatibilityError, match="pinned 40-character"):
        compatibility.analyze_queue_job(
            queue_path_value=str(queue), key=key, resume_data_value=str(profile),
            keywords_value=str(keywords), receipt_value=str(receipt), score_runner=unexpected_score,
        )
    assert calls == 0


def test_evidence_references_do_not_match_substrings_or_return_profile_text() -> None:
    profile = {
        "summary": "Built a synthetic JavaScript interface.",
        "personalProjects": [{
            "name": "Synthetic project",
            "description": ["Documented software testing."],
        }],
        "customSections": {
            "private custom heading that must not be copied": {
                "sectionType": "stringList", "strings": ["Uses Java in a synthetic fixture."],
            },
        },
    }
    references = compatibility._evidence_references(
        profile,
        {"required_skills": ["Java", "JavaScript"], "preferred_skills": ["testing"], "keywords": []},
    )
    assert references == {
        "Java": ["customSections#1"],
        "JavaScript": ["summary"],
        "testing": ["personalProjects#1"],
    }
    assert "private custom heading" not in json.dumps(references)
    assert not any("synthetic" in value.casefold() for values in references.values() for value in values)
