#!/usr/bin/env python3
"""I4 (01/10): funnel per source and per path, from aplicadas.json (read only, no LLM).

  funil-fontes.py [APLICADAS] [--curto]

Per source: sent -> answered (any status past 'enviada') -> advanced (test/interview/next step),
plus 'sem resposta' = still 'enviada' after SEM_RESPOSTA_DIAS. The status itself is never changed:
G1/G3 only upgrade, so a derived number keeps them simple. Per path: caminho=fila|rodizio (F1).
"""
import json
import os
import sys
from datetime import date, timedelta

SEM_RESPOSTA_DIAS = 21
AVANCO = {"etapa_teste", "entrevista", "proxima_etapa"}
FONTES = ("gupy", "linkedin", "indeed", "infojobs", "inhire", "e-mail", "email", "telegram")


def fonte(a):
    t = f"{a.get('como') or ''} {a.get('url') or ''} {a.get('chave') or ''}".lower()
    for f in FONTES:
        if f in t:
            return "e-mail" if f == "email" else f
    return "outro"


def funil(ap, hoje=None):
    hoje = hoje or date.today()
    corte = (hoje - timedelta(days=SEM_RESPOSTA_DIAS)).isoformat()
    por = {}
    for a in ap:
        if not isinstance(a, dict):
            continue
        st = a.get("status") or "enviada"
        for chave in (("fonte", fonte(a)), ("caminho", a.get("caminho"))):
            if chave[1] is None:
                continue
            c = por.setdefault(chave, {"envios": 0, "respostas": 0, "avancos": 0, "sem_resposta": 0})
            c["envios"] += 1
            c["respostas"] += st != "enviada"
            c["avancos"] += st in AVANCO
            c["sem_resposta"] += st == "enviada" and str(a.get("data") or "9999") < corte
    return por


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else (os.environ.get("APLICADAS_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "aplicadas.json"))
    try:
        ap = json.load(open(path, encoding="utf-8")).get("aplicadas", [])
    except (OSError, ValueError) as e:
        print(f"funil-fontes: aplicadas ilegivel ({type(e).__name__})")
        return 1
    por = funil(ap)
    fontes = sorted(((k[1], v) for k, v in por.items() if k[0] == "fonte"), key=lambda x: -x[1]["envios"])
    if "--curto" in sys.argv:
        sem = sum(v["sem_resposta"] for _, v in fontes)
        print("funil: " + " | ".join(f"{f} {v['envios']}→{v['respostas']}→{v['avancos']}" for f, v in fontes[:4])
              + f" (envio→resposta→avanço) | sem resposta >{SEM_RESPOSTA_DIAS}d: {sem}")
        return 0
    for f, v in fontes:
        taxa = v["respostas"] * 100 // v["envios"]
        print(f"{f}: {v['envios']} envios, {v['respostas']} com retorno ({taxa}%), {v['avancos']} avanços, "
              f"{v['sem_resposta']} sem resposta >{SEM_RESPOSTA_DIAS}d")
    cam = {k[1]: v for k, v in por.items() if k[0] == "caminho"}
    if cam:
        print("caminho (desde 01/10): " + ", ".join(f"{k} {v['envios']} envios/{v['respostas']} respostas"
                                                   for k, v in sorted(cam.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
