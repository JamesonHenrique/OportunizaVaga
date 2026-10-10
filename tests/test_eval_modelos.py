"""scripts/eval-modelos.py: scoring and recording with a fake opencode (no real provider is ever called)."""
import importlib.util
import json
import os
import re
import stat
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_spec = importlib.util.spec_from_file_location("eval_modelos", os.path.join(ROOT, "scripts", "eval-modelos.py"))
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)
ESPERADOS = {c["id"]: c["esperado"] for c in ev.casos()}


def _resposta(certas=True, pular=(), extra=""):
    linhas = []
    for i, e in ESPERADOS.items():
        if i in pular:
            continue
        d = e if certas else ("descartar" if e == "aplicar" else "aplicar")
        linhas.append(json.dumps({"id": i, "decisao": d, "motivo": "x"}))
    return "texto solto do modelo\n" + "\n".join(linhas) + extra


def test_golden_sintetico_e_coerente():
    cs = ev.casos()
    assert len({c["id"] for c in cs}) == len(cs) >= 10
    assert {c["esperado"] for c in cs} == {"aplicar", "descartar"}
    texto = json.dumps(cs, ensure_ascii=False)
    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}|@[\w-]+\.(com|br)|\(\d{2}\)\s?\d{4,5}-\d{4}", texto)   # no CPF/e-mail/phone


def test_tudo_certo():
    r = ev.pontuar(_resposta(), ESPERADOS)
    assert r["acertos"] == r["total"] == r["respondidas"] and r["invalidas"] == 0 and r["precisao_respondidas"] == 1


def test_disponibilidade_e_qualidade_separadas():
    falta = list(ESPERADOS)[:3]
    r = ev.pontuar(_resposta(pular=falta, extra='\n{"id":"x_inexistente","decisao":"aplicar"}\n{"id":"%s","decisao":"talvez"}' % falta[0]), ESPERADOS)
    assert r["respondidas"] == r["total"] - 3 and r["faltando"] == sorted(falta)
    assert r["invalidas"] == 2 and r["precisao_respondidas"] == 1   # answered ones are all right


def test_primeira_resposta_vale():
    i = next(iter(ESPERADOS))
    errada = "descartar" if ESPERADOS[i] == "aplicar" else "aplicar"
    r = ev.pontuar('{"id":"%s","decisao":"%s"}\n{"id":"%s","decisao":"%s"}' % (i, errada, i, ESPERADOS[i]), ESPERADOS)
    assert r["errados"] == [i]


def test_execucao_com_opencode_falso_registra():
    with tempfile.TemporaryDirectory() as d:
        resp = os.path.join(d, "resp.txt")
        open(resp, "w").write(_resposta())
        fake = os.path.join(d, "opencode")
        open(fake, "w").write("#!/bin/sh\ncat '%s'\n" % resp)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        os.environ["OPENCODE_BIN"] = fake
        reg = os.path.join(d, "eval.jsonl")
        antigo, ev.REGISTRO = ev.REGISTRO, reg
        try:
            assert ev.main(["--modelos", "fake/modelo-a,fake/modelo-b"]) == 0
        finally:
            ev.REGISTRO = antigo
            del os.environ["OPENCODE_BIN"]
        linhas = [json.loads(x) for x in open(reg)]
        assert [x["modelo"] for x in linhas] == ["fake/modelo-a", "fake/modelo-b"]
        assert all(x["rc"] == 0 and x["acertos"] == len(ESPERADOS) and x["prompt"] for x in linhas)


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print("ok -", nome)
