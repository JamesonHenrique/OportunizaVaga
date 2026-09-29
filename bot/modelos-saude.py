#!/usr/bin/env python3
"""Adaptive model cascade. The cascade order is hand-written, but free models differ a lot in practice:
in the maintainer's private run (8 days) one model had 1 success in 54 unproductive sessions while another
had 57 successes and 0 failures, and three models never succeeded once. This orders the cascade by each
model's success rate over the last 7 days of loop logs and benches (7 days) the models with 0 successes in
>= 10 attempts.

  modelos-saude.py ordenar M1 M2 ...   -> prints the cascade, one model per line (the loop reads it)
  modelos-saude.py relatorio           -> per-model table (usou / limite / improdutiva / erro)

Success = "rodada usou o modelo X"; failure = "modelo X no limite / encerrou sem navegar / quebrou o formato
de tool-call / morreu apos erro" (the exact lines bot/loop.sh and bot/loop.ps1 write to loop.log*).
Fail-open: any error prints the input order unchanged. Never benches below MIN_ATIVOS models.
Recomputed at most once per REFAZER_H hours. State: $MODELOS_SAUDE_FILE, else <STATE_DIR>/modelos_saude.json,
else bot/state/modelos_saude.json. Logs: loop.log* next to this script (or $MODELOS_SAUDE_LOGS, a glob).
"""
import glob
import gzip
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
SAUDE = (os.environ.get("MODELOS_SAUDE_FILE")
         or os.path.join(os.environ.get("STATE_DIR") or os.path.join(BASE, "state"), "modelos_saude.json"))
JANELA_DIAS = 7
QUARENTENA_DIAS = 7
MIN_TENTATIVAS = 10
MIN_ATIVOS = 2
REFAZER_H = 6

RE_USOU = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) [\d:]+\] rodada usou o modelo (\S+)")
RE_FALHA = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) [\d:]+\] modelo (\S+) (no limite|encerrou sem navegar|quebrou o formato|"
                      r"morreu apos erro)")


def linhas_log():
    padrao = os.environ.get("MODELOS_SAUDE_LOGS") or os.path.join(BASE, "loop.log*")
    for p in sorted(glob.glob(padrao)):
        abrir = gzip.open if p.endswith(".gz") else open
        try:
            with abrir(p, "rt", encoding="utf-8", errors="ignore") as fh:
                yield from fh
        except (OSError, EOFError):
            continue


def estatisticas(agora=None, linhas=None):
    corte = ((agora or datetime.now()) - timedelta(days=JANELA_DIAS)).strftime("%Y-%m-%d")
    st = {}
    for l in (linhas if linhas is not None else linhas_log()):
        m = RE_USOU.match(l)
        tipo = "usou"
        if not m:
            m = RE_FALHA.match(l)
            if not m:
                continue
            tipo = {"no limite": "limite", "morreu apos erro": "erro"}.get(m.group(3), "improdutiva")
        dia, modelo = m.group(1), m.group(2)
        if dia < corte or modelo.startswith("$"):
            continue
        s = st.setdefault(modelo, {"usou": 0, "limite": 0, "improdutiva": 0, "erro": 0})
        s[tipo] += 1
    return st


def nota(s):
    tentativas = sum(s.values())
    return (s["usou"] + 1) / (tentativas + 2)   # smoothed: a model never seen starts at 0.5


def ordenar(modelos, st, quarentena, agora):
    ativos = [m for m in modelos if quarentena.get(m, "") <= agora.isoformat()]
    if len(ativos) < MIN_ATIVOS:
        ativos = list(modelos)
    padrao = {"usou": 0, "limite": 0, "improdutiva": 0, "erro": 0}
    # stable: ties keep the hand-written order (index as tie-breaker)
    return sorted(ativos, key=lambda m: (-nota(st.get(m, padrao)), modelos.index(m)))


def _ler_estado():
    try:
        with open(SAUDE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def recalcular(modelos, agora):
    st = estatisticas(agora)
    estado = _ler_estado()
    quarentena = {m: ate for m, ate in (estado.get("quarentena") or {}).items() if ate > agora.isoformat()}
    for m in modelos:
        s = st.get(m)
        if s and s["usou"] == 0 and sum(s.values()) >= MIN_TENTATIVAS and m not in quarentena:
            ativos_depois = [x for x in modelos if x not in quarentena and x != m]
            if len(ativos_depois) >= MIN_ATIVOS:
                quarentena[m] = (agora + timedelta(days=QUARENTENA_DIAS)).isoformat(timespec="minutes")
    estado = {"calculado_em": agora.isoformat(timespec="minutes"), "janela_dias": JANELA_DIAS,
              "estatisticas": st, "quarentena": quarentena}
    os.makedirs(os.path.dirname(SAUDE) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(SAUDE) or ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, SAUDE)
    return estado


def main(argv):
    agora = datetime.now()
    if argv[:1] == ["ordenar"]:
        modelos = argv[1:]
        try:
            estado = _ler_estado()
            try:
                velho = datetime.fromisoformat(estado["calculado_em"]) < agora - timedelta(hours=REFAZER_H)
            except (KeyError, ValueError):
                velho = True
            if velho:
                estado = recalcular(modelos, agora)
            saida = ordenar(modelos, estado.get("estatisticas", {}), estado.get("quarentena", {}), agora)
        except Exception as e:   # fail-open: the round must never lose its cascade
            print(f"modelos-saude: erro ({type(e).__name__}), ordem original", file=sys.stderr)
            saida = modelos
        print("\n".join(saida))
        return 0
    if argv[:1] == ["relatorio"]:
        st = estatisticas(agora)
        print(f"{'modelo':50} usou limite improd erro  nota")
        for m, s in sorted(st.items(), key=lambda x: -nota(x[1])):
            print(f"{m[:50]:50} {s['usou']:4} {s['limite']:6} {s['improdutiva']:6} {s['erro']:4}  {nota(s):.2f}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
