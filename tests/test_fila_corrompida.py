"""bot/vagas_filtros.salvar_fila: an unreadable queue is kept aside, never silently replaced (19/10)."""
import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import vagas_filtros as vf  # noqa: E402


def test_fila_corrompida_e_guardada_antes_de_regravar():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "vagas_fila.json")
        open(p, "w").write('{"vagas": {"a": ')          # truncated write
        vf.salvar_fila(p, {}, {"vagas": {"b": {"status": "nova"}}})
        lados = glob.glob(p + ".corrompido-*")
        assert len(lados) == 1 and open(lados[0]).read() == '{"vagas": {"a": '
        assert json.load(open(p)) == {"vagas": {"b": {"status": "nova"}}}


def test_fila_ausente_e_criada():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "vagas_fila.json")
        vf.salvar_fila(p, {}, {"vagas": {}})
        assert json.load(open(p)) == {"vagas": {}} and not glob.glob(p + ".corrompido-*")
