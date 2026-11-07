"""Synthetic regression tests for the one-page default and explicit two-page exception."""

import json
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "bot" / "gerar_cv.py"


def _inputs(tmp_path: Path, max_pages: object = ...) -> tuple[Path, Path, Path, dict[str, str]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    cv_base = tmp_path / "cv_base.md"
    items = "".join(
        f"- Synthetic project evidence item {index:03d} is preserved in the source profile.\n"
        for index in range(100)
    )
    cv_base.write_text(
        "# Synthetic Candidate\n"
        "Candidato a Desenvolvedor Júnior\n"
        "synthetic@example.invalid | +1 (555) 010-0100 | Recife, PE\n\n"
        "## Resumo\n"
        "Experiência sintética de demonstração para validar paginação de PDF.\n\n"
        "## Habilidades técnicas\n"
        "### Backend\n"
        "Java | Spring Boot\n\n"
        "## Experiência\n"
        "### Synthetic QA fixture | 2024 - 2025\n"
        "- Validated a fictitious document pipeline with deterministic test data.\n\n"
        "## Projetos\n"
        "### Projeto sintético de demonstração | 2025 - 2026\n"
        + items
        + "\n## Formação\n"
        "### Curso sintético de Tecnologia da Informação | 2023 - presente\n"
        "- Formação fictícia usada somente neste teste.\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "nome": "Synthetic Candidate",
                "email": "synthetic@example.invalid",
                "telefone": "+1 (555) 010-0100",
                "local": "Recife, PE",
                "experiencia": {"tecnologias": []},
                "palavras_chave_ats": [],
            }
        ),
        encoding="utf-8",
    )
    spec_data = {
        "secoes_mostrar": ["Habilidades técnicas", "Experiência", "Projetos", "Formação"],
        "so_categorias": ["Backend"],
    }
    if max_pages is not ...:
        spec_data["max_paginas"] = max_pages
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(spec_data), encoding="utf-8")
    pdf = tmp_path / "synthetic-cv.pdf"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "PYTHONIOENCODING": "utf-8",
        "CV_BASE_FILE": str(cv_base),
        "DADOS_CANDIDATO_FILE": str(candidate),
    }
    return spec, pdf, candidate, env


def _page_count(pdf: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        result = subprocess.run(
            [pdfinfo, str(pdf)], capture_output=True, text=True, check=True, timeout=10
        )
        match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
        assert match, result.stdout
        return int(match.group(1))
    pytest.skip("pdfinfo is required for a direct page-count assertion")


def test_two_pages_require_explicit_spec_and_preserve_final_content(tmp_path: Path) -> None:
    default_spec, default_pdf, _, env = _inputs(tmp_path / "default")
    default = subprocess.run(
        [sys.executable, str(GENERATOR), str(default_spec), str(default_pdf)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=60,
    )
    assert default.returncode != 0
    assert "max_paginas=1" in default.stderr

    two_page_dir = tmp_path / "two-page"
    two_page_dir.mkdir()
    spec, pdf, _, env = _inputs(two_page_dir, max_pages=2)
    generated = subprocess.run(
        [sys.executable, str(GENERATOR), str(spec), str(pdf)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=60,
    )
    assert generated.returncode == 0, generated.stderr
    assert "2 paginas" in generated.stdout
    assert _page_count(pdf) == 2

    extracted = subprocess.run(
        ["pdftotext", str(pdf), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    assert extracted.returncode == 0, extracted.stderr
    assert "Synthetic project evidence item 099" in extracted.stdout


@pytest.mark.parametrize("value", [True, 0, 3, "2", None])
def test_invalid_page_limits_fail_before_writing_pdf(tmp_path: Path, value: object) -> None:
    spec, pdf, _, env = _inputs(tmp_path, max_pages=value)
    result = subprocess.run(
        [sys.executable, str(GENERATOR), str(spec), str(pdf)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=30,
    )
    assert result.returncode == 2
    assert "max_paginas deve ser 1 ou 2" in result.stderr
    assert not pdf.exists()


@pytest.mark.parametrize("unreadable_text", [None, ""])
def test_unextractable_pdf_text_is_not_approved(
    monkeypatch: pytest.MonkeyPatch, unreadable_text: object
) -> None:
    module_spec = importlib.util.spec_from_file_location("public_cv_generator_under_test", GENERATOR)
    assert module_spec and module_spec.loader
    generator_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(generator_module)
    monkeypatch.setattr(generator_module, "_extrair_texto", lambda _path: unreadable_text)

    problems = generator_module._checar_texto("synthetic.pdf", "Synthetic Candidate", {})

    assert problems == ["texto do PDF nao pode ser extraido; verificacao automatica inconclusiva"]
