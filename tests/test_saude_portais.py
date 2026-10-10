"""bot/saude-portais.py: every state comes from evidence; configured-but-silent is never "funcionando"."""
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_spec = importlib.util.spec_from_file_location("saude_portais", os.path.join(ROOT, "bot", "saude-portais.py"))
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

AGORA = datetime(2026, 10, 10, 12, 0).astimezone()
H = lambda h: (AGORA - timedelta(hours=h)).isoformat()   # noqa: E731


def _estado(arquivos):
    with tempfile.TemporaryDirectory() as d:
        for nome, doc in arquivos.items():
            json.dump(doc, open(os.path.join(d, nome), "w"))
        return sp.avaliar(d, AGORA)


def test_cada_estado_com_evidencia():
    r = _estado({
        "aplicadas.json": {"aplicadas": [], "login_checagens": {"portal_login": {"em": H(1), "logado": "nao"},
                                                                 "gmail": {"em": H(1), "logado": "sim"}},
                           "aguardando_login": {"k": {"canal": "portal_espera"}}},
        "sonda_sites.json": {"portal_bloq": {"em": H(2), "estado": "bloqueado", "motivo": "Verify you are human"},
                             "portal_ok": {"em": H(3), "estado": "ok"},
                             "portal_velho": {"em": H(200), "estado": "ok"}},
        "canario_fontes.json": {"portal_parser": {"em": H(5), "ok": False, "falha": "portal_parser: 0 vagas"}},
        "vagas_fila.json": {"ultima_coleta": H(1), "fontes_quebradas": ["portal_coleta"], "stats": {"erros": []}},
        "rodizio_saude.json": {"sites": {"portal_seco": {"pausado_ate": (AGORA + timedelta(hours=10)).isoformat(),
                                                         "vazias_seguidas": 4, "ultima_varredura": H(2)},
                                         "portal_config": {}}},
    })
    e = {k: v["estado"] for k, v in r.items()}
    assert e == {"portal_login": "login_necessario", "portal_espera": "login_necessario",
                 "portal_bloq": "indisponivel", "portal_parser": "falha_recente", "portal_coleta": "falha_recente",
                 "portal_seco": "sem_vagas_compativeis", "portal_ok": "funcionando",
                 "portal_velho": "nao_verificado", "portal_config": "nao_verificado"}, e
    assert "gmail" not in r   # login account, not a job portal


def test_falha_vence_sucesso_e_falha_antiga_expira():
    r = _estado({"sonda_sites.json": {"x": {"em": H(1), "estado": "ok"}},
                 "canario_fontes.json": {"x": {"em": H(2), "ok": False, "falha": "x: 0 vagas"},
                                         "y": {"em": H(100), "ok": False, "falha": "antiga"}}})
    assert r["x"]["estado"] == "falha_recente" and r["y"]["estado"] == "nao_verificado"


def test_sem_arquivos_sem_portais():
    assert _estado({}) == {}


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print("ok -", nome)
