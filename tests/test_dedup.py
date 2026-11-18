#!/usr/bin/env python3
"""Tests for bot/dedup.py cross-portal deduplication."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bot"))

import dedup  # noqa: E402


def test_normalizar_titulo_case_accent_and_stopwords():
    t1 = "Desenvolvedor Java Júnior (Remoto)"
    t2 = "DESENVOLVEDORA JAVA JR"
    assert dedup.normalizar_titulo(t1) == dedup.normalizar_titulo(t2) == "java junior"


def test_normalizar_titulo_separates_levels():
    t_jr = "Desenvolvedor Backend Java Jr"
    t_pl = "Desenvolvedor Backend Java Pleno"
    assert dedup.normalizar_titulo(t_jr) != dedup.normalizar_titulo(t_pl)
    assert dedup.normalizar_titulo(t_jr, manter_nivel=False) == dedup.normalizar_titulo(t_pl, manter_nivel=False)


def test_normalizar_empresa():
    e1 = "Acme Tecnologia Ltda"
    e2 = "ACME TECNOLOGIA S/A"
    e3 = "Acme Tecnologia S.A."
    e4 = "Acme Tecnologia"
    assert dedup.normalizar_empresa(e1) == dedup.normalizar_empresa(e2) == dedup.normalizar_empresa(e3) == dedup.normalizar_empresa(e4) == "acme tecnologia"
    # Company with internal 'do' / 'brasil'
    assert dedup.normalizar_empresa("Banco do Brasil S.A.") == "banco do brasil"


def test_gerar_hash_vaga():
    h1 = dedup.gerar_hash_vaga("Acme Ltda", "Dev Java Jr", "São Paulo")
    h2 = dedup.gerar_hash_vaga("ACME", "Java Junior Developer", "São Paulo")
    assert h1 == h2
    assert len(h1) == 12


def test_deduplicar_vagas_prioritizes_gupy_over_others():
    v_li = {"id": "li:100", "fonte": "linkedin", "empresa": "TechCorp Ltda", "titulo": "Java Jr", "url": "https://linkedin.com/jobs/view/100"}
    v_gp = {"id": "gupy:200", "fonte": "gupy", "empresa": "TechCorp", "titulo": "Desenvolvedor Java Júnior", "url": "https://techcorp.gupy.io/jobs/200"}
    v_rm = {"id": "remotar:300", "fonte": "remotar", "empresa": "TechCorp S.A.", "titulo": "Dev Java Jr", "url": "https://remotar.com.br/job/300"}

    # Input has LinkedIn first, then Gupy, then Remotar
    vagas = [v_li, v_gp, v_rm]
    deduped = dedup.deduplicar_vagas(vagas)

    assert len(deduped) == 1
    vencedora = deduped[0]
    assert vencedora["fonte"] == "gupy"
    assert vencedora["id"] == "gupy:200"

    # Alternative sources must be preserved in fontes_alternativas
    alt = vencedora.get("fontes_alternativas") or []
    assert len(alt) == 2
    fontes_alt = {a["fonte"] for a in alt}
    assert fontes_alt == {"linkedin", "remotar"}


def test_deduplicar_vagas_preserves_unique_jobs():
    v1 = {"id": "gupy:1", "fonte": "gupy", "empresa": "Alpha", "titulo": "Java Jr", "url": "http://alpha"}
    v2 = {"id": "gupy:2", "fonte": "gupy", "empresa": "Beta", "titulo": "Java Jr", "url": "http://beta"}
    v3 = {"id": "gupy:3", "fonte": "gupy", "empresa": "", "titulo": "Java Jr", "url": "http://anon"}

    deduped = dedup.deduplicar_vagas([v1, v2, v3])
    assert len(deduped) == 3


if __name__ == "__main__":
    for f in list(locals().values()):
        if callable(f) and f.__name__.startswith("test_"):
            f()
            print(f"PASS: {f.__name__}")
    print("All dedup tests passed successfully!")
