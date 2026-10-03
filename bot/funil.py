#!/usr/bin/env python3
"""Funil de candidatura: contas as etapas a partir de aplicadas.json.

  funil.py [--aplicadas F] [--csv [PATH]] [--json] [--markdown [PATH]]

A etapa de cada candidatura vem do campo `status` (o mesmo que o follow-up grava via
`estado.py status`). As etapas sao cumulativas: quem chegou em entrevista conta tambem
como convidado e como respondida. Por isso o denominador de cada taxa e a etapa
imediatamente anterior, nunca a primeira.

Antes (ate o commit 6e65a20) o funil parava em "respostas", que era "status diferente
de enviada" — e nao de "houve resposta". Isso dava tres numeros que nao batiam com a
intencao:

  - `sem_resposta`, que e justamente ausencia de resposta, contava como resposta;
  - convites e entrevistas viravam o mesmo numero, porque nao eram etapas separadas;
  - a taxa de resposta ficava sempre perto de 100% sempre que quase nada tinha
   Advanced status, o que e o caso comum (quem se candidata em silencio e a maioria).

A semantica de "respondeu" e "avancou" aqui e a mesma do bot/funil-fontes.py, que ja
era o canônico: respondeu = o status passou de `enviada`; avancou = chegou a uma etapa
de processo. Um status desconhecido NAO conta como resposta (fail-closed) e aparece na
lista `status_desconhecidos` do --json, para nao sumir em silencio.
"""

import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta

# Candidato ainda sem resposta ha mais que isso vira "sem resposta" no recorte (mesmo
# corte do bot/funil-fontes.py: nao e o status que diz, e a data).
SEM_RESPOSTA_DIAS = 21

# Estagios do funil, do mais largo ao mais estreito. Cada conjunto contem os status que
# provam que a candidatura chegou naquela etapa; None = etapa sem conjunto de status
# (derivada de contagem). Devem espelhar STATUS_OK do bot/estado.py.
#
#   aplicadas  = toda entrada de aplicadas[] (por definicao, nao por status)
#   respondidas = houve retorno do recrutador (status saiu de `enviada`)
#   convites   = convidado para uma etapa do processo
#   entrevistas= chegou a entrevista
#
# `enviada` NAO entra em respondidas: e o status de quem ainda nao respondeu. `encerrada`
# e `sem_retorno_verificavel` tambem nao: encerrada pode ser vaga fechada pelo
# recrutador, e "sem retorno verificavel" e a ausencia de resposta que o follow-up
# conseguiu registrar como inconclusive.
ETAPAS = [
    ("vistas", None, "listagens vistas (descartes + aplicadas + bloqueadas)"),
    ("aplicadas", None, "candidaturas enviadas"),
    ("respondidas", {"respondida", "em_analise", "etapa_teste", "proxima_etapa",
                     "entrevista", "followup", "sem_resposta"},
     "houve retorno do recrutador, favoravel ou nao"),
    ("convites", {"em_analise", "etapa_teste", "proxima_etapa", "entrevista"},
     "convidado para uma etapa do processo"),
    ("entrevistas", {"entrevista"}, "chegou a entrevista"),
]

# Recorte lateral: das que chegaram a uma etapa de processo, quantas eram remotas.
# Nao entra no grafico nem nas taxas — nao tem ordem no funil.
RECORTE_EXECUCAO = {"em_analise", "etapa_teste", "proxima_etapa", "entrevista"}

# Status que o follow-up pode gravar mas que nao provam retorno do recrutador.
SEM_RETORNO_EQUIVOCADO = {"encerrada", "sem_retorno_verificavel"}


def carregar(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or "aplicadas" not in doc:
        raise ValueError("aplicadas.json sem a chave 'aplicadas'")
    return doc


def contar(doc, hoje=None):
    """Conta as etapas do funil e devolve os diagnosticos junto.

    hoje: usado so para o recorte de "sem resposta ha mais de N dias" (default: hoje).
    """
    hoje = hoje or date.today()
    corte = (hoje - timedelta(days=SEM_RESPOSTA_DIAS)).isoformat()

    apl = doc.get("aplicadas") or []
    bloq = doc.get("bloqueados") or {}
    desc = doc.get("descartes_listagem") or {}

    desc_total = desc.get("total")
    if desc_total is None:
        desc_total = sum(v for v in desc.values()
                         if isinstance(v, (int, float)) and v != "total")

    # Status de cada candidatura; registro antigo sem status = ainda nao respondeu.
    status_de = []
    for a in apl:
        st = (a.get("status") or "enviada").strip() or "enviada"
        status_de.append(st)

    conhecidos = {"enviada"}   # o padrao de registro sem status; nao e "desconhecido"
    for _, sts, _ in ETAPAS:
        if sts:
            conhecidos |= sts
    conhecidos |= SEM_RETORNO_EQUIVOCADO
    desconhecidos = sorted({s for s in status_de if s not in conhecidos})

    # "vistas" nao e um status: e tudo que o robo olhou e decidiu nao seguir em diante,
    # mais o que ja estava registrado (aplicadas + bloqueadas).
    n_vistas = int(desc_total or 0) + len(apl) + len(bloq)

    contagens = {"vistas": n_vistas, "aplicadas": len(apl)}
    for nome, sts, _ in ETAPAS:
        if nome in ("vistas", "aplicadas"):
            continue
        contagens[nome] = sum(1 for s in status_de if s in sts)

    recorte_exec = sum(1 for a, s in zip(apl, status_de)
                       if s in RECORTE_EXECUCAO and a.get("remota"))

    # Encerrada/sem_retorno_verificado sao ambiguos: podem ser retorno do recrutador
    # (vaga fechada) ou falta de retorno (ninguem respondeu). Ficam fora das etapas
    # porque escolher um lado sem evidência inflaria ou zeraria a taxa de resposta.
    equivocados = sum(1 for s in status_de if s in SEM_RETORNO_EQUIVOCADO)

    return {
        "contagens": contagens,
        "status_desconhecidos": desconhecidos,
        "descartes": desc,
        "descartes_total": int(desc_total or 0),
        "bloqueadas": len(bloq),
        "quase_la": len(doc.get("quase_la") or {}),
        "total_aplicadas": len(apl),
        "execucao_remota": recorte_exec,
        # Ainda `enviada` e mais velha que o corte: candidato no silencio, nao rejection.
        "sem_resposta_antiga": sum(1 for a, s in zip(apl, status_de)
                                   if s == "enviada"
                                   and str(a.get("data") or "9999") < corte),
        "retorno_equivocado": equivocados,
    }


def taxas(contagens):
    """Taxa de cada etapa contra a imediatamente anterior (nunca contra a primeira)."""
    out = {}
    anterior = None
    for nome, _, _ in ETAPAS:
        atual = contagens[nome]
        if anterior is not None:
            out[nome] = (100.0 * atual / anterior) if anterior else 0.0
        anterior = atual
    return out


def linhas_texto(res):
    c, tx = res["contagens"], taxas(res["contagens"])
    partes = ["Funil de candidatura"]
    for nome, _, _ in ETAPAS:
        partes.append("  %-12s %d" % (nome, c[nome]))
    for i, (nome, _, _) in enumerate(ETAPAS[1:], start=1):
        anterior = ETAPAS[i - 1][0]
        partes.append("  %s -> %s: %.1f%%" % (anterior, nome, tx[nome]))
    if c["aplicadas"]:
        partes.append("  .execucao remota: %d de %d (%.0f%%)"
                      % (res["execucao_remota"], c["aplicadas"],
                         100.0 * res["execucao_remota"] / c["aplicadas"]))
    if res["sem_resposta_antiga"]:
        partes.append("  .sem resposta ha >%dd: %d (ainda em 'enviada')"
                      % (SEM_RESPOSTA_DIAS, res["sem_resposta_antiga"]))
    if res["retorno_equivocado"]:
        partes.append("  .encerrada/sem_retorno: %d (ambiguo: nao entra em nenhuma etapa)"
                      % res["retorno_equivocado"])
    if res["status_desconhecidos"]:
        partes.append("  .status desconhecidos: %s"
                      % ", ".join(res["status_desconhecidos"]))
    return "\n".join(partes)


def main():
    ap = argparse.ArgumentParser(description="Funil de candidatura")
    ap.add_argument("--aplicadas", default=os.environ.get(
        "BOT_APLICADAS", "bot/aplicadas.json"))
    ap.add_argument("--csv", nargs="?", const="funil.csv", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", nargs="?", const="funil.md", default=None)
    args = ap.parse_args()

    try:
        doc = carregar(args.aplicadas)
    except FileNotFoundError:
        sys.stderr.write("aplicadas.json nao encontrado: %s\n" % args.aplicadas)
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write("aplicadas.json invalido: %s\n" % exc)
        return 1

    res = contar(doc)
    c = res["contagens"]

    if args.json:
        payload = dict(res)
        payload["taxas"] = taxas(c)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(linhas_texto(res))

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["etapa", "quantidade"])
            for nome, _, _ in ETAPAS:
                w.writerow([nome, c[nome]])
        print("CSV exportado: %s" % args.csv)

    if args.markdown:
        tx = taxas(c)
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write("# Funil de candidatura\n\n")
            fh.write("| etapa | quantidade |\n|---|---|\n")
            for nome, _, _ in ETAPAS:
                fh.write("| %s | %d |\n" % (nome, c[nome]))
            fh.write("\n| conversão | taxa |\n|---|---|\n")
            for i, (nome, _, _) in enumerate(ETAPAS[1:], start=1):
                fh.write("| %s -> %s | %.1f%% |\n" % (ETAPAS[i - 1][0], nome, tx[nome]))
        print("Markdown exportado: %s" % args.markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())