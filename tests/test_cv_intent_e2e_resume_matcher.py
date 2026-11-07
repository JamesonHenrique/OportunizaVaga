"""Synthetic end-to-end test for generation, the pinned parser, and state association."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from bot import job_requirement_review
from bot import cv_content_review

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESUME_MATCHER_CLI = Path(
    os.environ.get(
        "OV_RESUME_MATCHER_CLI",
        str(Path.home() / "tools/Resume-Matcher/apps/backend/.venv/bin/resume-matcher"),
    )
).expanduser()
PINNED_REVISION = "d480551798b7aa97f5b57ba1972ee383bd882238"


def _write_requirement_review(tmp_path: Path, announcement: Path, title: str) -> dict[str, str]:
    profile = {
        "summary": "Synthetic profile for end-to-end verification.",
        "workExperience": [],
        "personalProjects": [],
        "education": [],
        "additional": {"technicalSkills": [], "languages": [], "certificationsTraining": []},
        "customSections": {},
    }
    profile_bytes = json.dumps(profile, sort_keys=True).encode("utf-8")
    proposal = job_requirement_review.build_proposal(announcement.read_bytes(), title, profile_bytes)
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
    assessment, receipt = job_requirement_review.approve_review(
        announcement.read_bytes(), profile_bytes, proposal, sheet,
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


def _write_content_review(
    tmp_path: Path, announcement: Path, pdf: Path, cv_base: Path, candidate: Path,
) -> dict[str, str]:
    proposal = cv_content_review.build_proposal(
        job_path=announcement,
        pdf_path=pdf,
        cv_base_path=cv_base,
        candidate_data_path=candidate,
    )
    review = cv_content_review.build_review_template(proposal)
    review["acknowledgements"] = {name: True for name in cv_content_review.ACKNOWLEDGEMENTS}
    references = proposal["profile_evidence_refs"]
    review["claims"] = [
        {
            "claim_id": claim["id"],
            "decision": "SUPPORTED",
            "evidence_refs": references[: min(3, len(references))],
        }
        for claim in proposal["claims"]
    ]
    assessment, receipt, result = cv_content_review.approve_review(
        proposal=proposal,
        review=review,
        job_path=announcement,
        pdf_path=pdf,
        cv_base_path=cv_base,
        candidate_data_path=candidate,
    )
    assert result["status"] == "APPROVED"
    artifacts = {
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
        artifacts[key].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    for path in artifacts.values():
        path.chmod(0o600)
    return {key: str(path) for key, path in artifacts.items()}


@pytest.mark.skipif(not RESUME_MATCHER_CLI.is_file(), reason="local Resume-Matcher CLI is unavailable")
@pytest.mark.skipif(importlib.util.find_spec("reportlab") is None, reason="ReportLab is unavailable to the test interpreter")
def test_synthetic_generated_pdf_is_verified_and_bound_to_the_application(tmp_path: Path) -> None:
    cv_base = tmp_path / "cv_base.md"
    cv_base.write_text(
        "# Synthetic Candidate\n"
        "Java | Spring Boot | API REST\n"
        "synthetic@example.com | +1 (555) 010-0100 | Recife, PE | https://example.invalid/synthetic\n\n"
        "## Resumo\n"
        "Estudante com prática em Java, Spring Boot e APIs REST por meio de projetos pessoais.\n\n"
        "## Habilidades técnicas\n"
        "### Backend\nJava | Spring Boot | API REST | Docker\n\n"
        "## Experiência\n"
        "### Projeto pessoal de desenvolvimento | 2025 - 2026\n"
        "- Validei endpoints REST em aplicação sintética usando Java e Spring Boot.\n\n"
        "## Projetos\n"
        "### API de estudo | 2024 - 2025\n"
        "- Desenvolvi uma API REST fictícia com Java, Spring Boot e Docker.\n\n"
        "## Formação\n"
        "### Formação sintética em Tecnologia da Informação | 2023 - presente\n"
        "- Curso fictício em andamento.\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "nome": "Synthetic Candidate",
                "email": "synthetic@example.com",
                "telefone": "+1 (555) 010-0100",
                "linkedin": "https://example.invalid/synthetic",
                "local": "Recife, PE",
                "experiencia": {"tecnologias": ["Java", "Spring Boot", "API REST", "Docker"]},
                "palavras_chave_ats": "Java, Spring Boot, API REST, Docker",
            }
        ),
        encoding="utf-8",
    )
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "empresa": "Empresa Sintética",
                "vaga": "Desenvolvedora Backend Júnior",
                "titulo_alvo": "Desenvolvedor Backend Júnior",
                "resumo_custom": (
                    "Estudante com prática em Java, Spring Boot e APIs REST por meio de projetos pessoais."
                ),
                "so_categorias": ["Backend"],
                "secoes_mostrar": ["Habilidades técnicas", "Experiência", "Projetos", "Formação"],
                "palavras_chave_vaga": ["Java", "Spring Boot", "API REST", "Docker"],
            }
        ),
        encoding="utf-8",
    )
    announcement = tmp_path / "announcement.txt"
    announcement.write_text(
        "Requisitos: Java, Spring Boot, API REST e Docker. Vaga júnior remota.\n", encoding="utf-8"
    )
    requirement_paths = _write_requirement_review(
        tmp_path, announcement, "Desenvolvedora Backend Júnior",
    )
    pdf = tmp_path / "synthetic-resume.pdf"
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"aplicadas": [], "rodizio": {"proximo": "synthetic"}}), encoding="utf-8")
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(mode=0o700)
    data_dir = tmp_path / "resume-matcher-data"
    data_dir.mkdir(mode=0o700)

    browser_gate = tmp_path / "fake-browser-gate.py"
    browser_gate.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "expected = sys.argv[sys.argv.index('--expected-sha256') + 1]\n"
        "print(json.dumps({'status':'APPROVED','expected_sha256':expected,'selected_sha256':expected,"
        "'input_count':1,'selected_file_count':1,'matching_file_count':1,'verified_at':'synthetic'}))\n",
        encoding="utf-8",
    )
    browser_gate.chmod(0o700)

    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "LANG": "C.UTF-8",
        "CV_BASE_FILE": str(cv_base),
        "DADOS_CANDIDATO_FILE": str(candidate),
        "OV_ATS_LOG": str(tmp_path / "ats.log"),
        "OV_RESUME_MATCHER_REQUIRED": "1",
        "OV_RESUME_MATCHER_CLI": str(RESUME_MATCHER_CLI),
        "OV_RESUME_MATCHER_REVISION": os.environ.get("OV_RESUME_MATCHER_REVISION", PINNED_REVISION),
        "OV_RESUME_MATCHER_DATA_DIR": str(data_dir),
        "OV_RESUME_MATCHER_MANIFEST_DIR": str(manifest_dir),
    }

    generated = subprocess.run(
        [sys.executable, str(ROOT / "bot" / "gerar_cv.py"), str(spec), str(pdf)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=safe_env,
        check=False,
        timeout=60,
    )
    assert generated.returncode == 0, generated.stderr

    gate = subprocess.run(
        [str(ROOT / "bot" / "cv-pronto.sh"), str(announcement), str(pdf)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=safe_env,
        check=False,
        timeout=120,
    )
    gate_records = []
    for line in gate.stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "status" in record:
            gate_records.append(record)
    assert gate.returncode == 0, gate.stderr
    assert len(gate_records) == 1
    approved = gate_records[0]
    assert approved["status"] == "APPROVED"
    assert approved["manifest_verified"] is True
    assert approved["page_count"] == 1
    assert approved["overall_score"] >= 80
    assert not approved["failed_checks"]
    assert not approved["warning_checks"]
    assert f"ANEXAR {pdf}" in gate.stdout.splitlines()

    content_paths = _write_content_review(tmp_path, announcement, pdf, cv_base, candidate)

    intent = {
        "empresa": "Empresa Sintética",
        "vaga": "Desenvolvedora Backend Júnior",
        "url": "https://jobs.example.invalid/application/123",
        "como": "synthetic",
        "cv_job_key": "synthetic_backend_jr_1",
        "cv_job_company": "Empresa Sintética",
        "cv_job_title": "Desenvolvedora Backend Júnior",
        "cv_manifest_id": approved["manifest_id"],
        "cv_job_sha256": approved["job_description_sha256"],
        "cv_pdf_sha256": approved["pdf_sha256"],
        "cv_announcement_path": str(announcement),
        "cv_attachment_path": str(pdf),
        "cv_browser_url_prefix": "https://jobs.example.invalid/application/123",
        "cv_browser_input_selector": "input[type=file][name=resume]",
        **requirement_paths,
        **content_paths,
    }
    intent_env = dict(safe_env, OV_CV_BROWSER_GATE=str(browser_gate))
    pending = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bot" / "estado.py"),
            "--file",
            str(state_file),
            "intencao",
            "synthetic_backend_jr_1",
            json.dumps(intent),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(intent_env, OV_RODADA="synthetic-e2e"),
        check=False,
        timeout=120,
    )
    assert pending.returncode == 0, pending.stdout + pending.stderr
    state = json.loads(state_file.read_text(encoding="utf-8"))
    pending_record = state["envios_pendentes"]["synthetic_backend_jr_1"]
    expected_hashes = {
        "cv_manifest_id": approved["manifest_id"],
        "cv_job_sha256": approved["job_description_sha256"],
        "cv_pdf_sha256": approved["pdf_sha256"],
    }
    assert all(pending_record.get(key) == value for key, value in expected_hashes.items())
    assert pending_record["cv_requirement_status"] == "APPROVED"
    assert pending_record["cv_requirement_required_barrier_count"] == 0
    assert pending_record["cv_content_review_status"] == "APPROVED"
    assert pending_record["cv_content_claim_count"] == (
        pending_record["cv_content_supported_claim_count"]
        + pending_record["cv_content_non_factual_claim_count"]
    )
    assert all(len(pending_record[key]) == 64 for key in (
        "cv_requirement_review_sha256", "cv_requirement_assessment_sha256",
        "cv_requirement_receipt_sha256", "cv_requirement_profile_sha256",
    ))
    assert not any(
        key in pending_record
        for key in (
            "cv_announcement_path",
            "cv_attachment_path",
            "cv_browser_url_prefix",
            "cv_browser_input_selector",
            *requirement_paths,
            *content_paths,
        )
    )

    confirmed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bot" / "estado.py"),
            "--file",
            str(state_file),
            "add-aplicada",
            json.dumps(
                {
                    "chave": "synthetic_backend_jr_1",
                    "empresa": "Empresa Sintética",
                    "vaga": "Desenvolvedora Backend Júnior",
                    "status": "enviada",
                }
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=intent_env,
        check=False,
        timeout=30,
    )
    assert confirmed.returncode == 0, confirmed.stdout + confirmed.stderr
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert all(state["aplicadas"][0].get(key) == value for key, value in expected_hashes.items())
    assert state["aplicadas"][0]["cv_requirement_status"] == "APPROVED"
    assert state["aplicadas"][0]["cv_content_review_status"] == "APPROVED"
    assert "envios_pendentes" not in state

    assert hashlib.sha256(announcement.read_bytes()).hexdigest() == approved["job_description_sha256"]
