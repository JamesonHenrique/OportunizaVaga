"""bot/check_ats.py: whole-word coverage, and an unreadable profile is never an "OK" (10/10)."""
import contextlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import check_ats  # noqa: E402

ANUNCIO = "Requisitos: Java, Spring Boot, PostgreSQL, Docker. Diferencial: Kubernetes."


def _rodar(cv_texto, dados):
    """main() with a fake PDF text and a temp dados_candidato.json (None = file absent)."""
    with tempfile.TemporaryDirectory() as d:
        an, cv, dj = (os.path.join(d, n) for n in ("anuncio.txt", "cv.pdf", "dados.json"))
        open(an, "w", encoding="utf-8").write(ANUNCIO)
        open(cv, "w").close()
        if dados is not None:
            open(dj, "w", encoding="utf-8").write(dados if isinstance(dados, str) else json.dumps(dados))
        antigo_dj, antigo_pdf = check_ats.DADOS_JSON, check_ats._texto_pdf
        check_ats.DADOS_JSON, check_ats._texto_pdf = dj, (lambda _p: cv_texto)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = check_ats.main(["check_ats.py", an, cv])
        finally:
            check_ats.DADOS_JSON, check_ats._texto_pdf = antigo_dj, antigo_pdf
        return rc, out.getvalue()


PERFIL = {"experiencia": {"tecnologias": ["Java", "Spring Boot", "PostgreSQL", "Docker"]}}


def test_presente_e_palavra_inteira():
    assert check_ats.presente("java", "javascript, java e spring")
    assert not check_ats.presente("java", "javascript e typescript")
    assert check_ats.presente("c++", "c++ e c#") and check_ats.presente("node.js", "usei node.js.")


def test_javascript_nao_cobre_java():
    rc, out = _rodar("javascript spring boot postgresql docker", PERFIL)
    falta = next(linha for linha in out.splitlines() if linha.startswith("FALTA no CV"))
    assert "Java" in falta, out   # substring match used to count it as covered


def test_cobertura_completa_aprova():
    rc, out = _rodar("java spring boot postgresql docker", PERFIL)
    assert rc == 0 and "OK" in out, out


def test_cobertura_baixa_reprova():
    rc, out = _rodar("javascript", PERFIL)
    assert rc == 1 and "REPROVADO" in out, out


def test_perfil_ausente_nao_e_ok():
    rc, out = _rodar("java spring boot", None)
    assert rc == 2 and "NAO VERIFICAVEL" in out and "OK" not in out.replace("NAO VERIFICAVEL", ""), out


def test_perfil_corrompido_nao_e_ok():
    rc, out = _rodar("java spring boot", '{"experiencia": ')
    assert rc == 2 and "NAO VERIFICAVEL" in out, out


def test_vaga_sem_termo_do_perfil_reprova():
    rc, out = _rodar("java", {"experiencia": {"tecnologias": ["Cobol"]}})
    assert rc == 1 and "desalinhada" in out, out


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print("ok -", nome)
