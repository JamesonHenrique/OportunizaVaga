#!/usr/bin/env python3
"""bot/tempo-rodada.py — elapsed time of the current round, for the model (prompt rule 7d). Portable (Linux/Windows).

bot/loop.sh writes <state dir>/rodada_inicio (epoch) when each attempt starts; the hard kill is RUN_TIMEOUT. Rounds
that ran past it left applications half done, so the model stops starting new work at NOVA_MAX minutes.
State dir: STATE_DIR (exported by the loop), else the folder of APLICADAS_FILE, else bot/.
"""
import os
import sys
import time

NOVA_MAX = int(os.environ.get("OV_RELOGIO_NOVA_MAX", "12"))
ENCERRAR = int(os.environ.get("OV_RELOGIO_ENCERRAR", "15"))


def main():
    base = os.path.dirname(os.path.realpath(__file__))
    sdir = os.environ.get("STATE_DIR") or (os.path.dirname(os.environ["APLICADAS_FILE"]) if os.environ.get("APLICADAS_FILE") else base)
    try:
        ini = int(open(os.path.join(sdir, "rodada_inicio")).read().strip())
    except (OSError, ValueError):
        print("relogio indisponivel: siga a META DE TEMPO")
        return 0
    m = int((time.time() - ini) // 60)
    if m >= ENCERRAR:
        print(f"{m} min — ENCERRE AGORA: registre o que falta, limpeza e resposta final")
    elif m >= NOVA_MAX:
        print(f"{m} min — NAO comece vaga nova: termine a atual (ou registre em quase_la) e encerre")
    else:
        print(f"{m} min — ok (nova vaga permitida ate {NOVA_MAX} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
