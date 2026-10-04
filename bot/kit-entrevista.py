#!/usr/bin/env python3
"""G (01/10): interview kit + same-day reminder on Telegram, for any source (G1 Gmail, G3 Gupy, G4 LinkedIn).

  kit-entrevista.py [--dry]      (e.g. cron */30 7-22h; see docs/OPERACAO.md)

For each application in test/interview/next step that the candidate has not marked as done
(acao_feita_em / teste_feito_em): one kit per status change (job, link, how it was sent, CV, event date when a calendar
invite shows it) and, on the event day, one reminder. Marks go through estado.py set-campo
(kit_status, evento_em, lembrete_em), so nothing is sent twice. No LLM, no browser.
"""
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime

BOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _aplicadas_padrao():
    try:
        sys.path.insert(0, BOT_DIR)
        import vagas_filtros
        return vagas_filtros.resolve_paths()["aplicadas"]
    except Exception:
        return os.path.join(BOT_DIR, "aplicadas.json")


# Paths by env (a private install points them at its own files), defaults = this repo's layout.
APLICADAS = os.environ.get("APLICADAS_FILE") or _aplicadas_padrao()
GMAIL = os.environ.get("OV_GMAIL_STATUS") or os.path.join(BOT_DIR, "state", "gmail_status.json")
NOTIFY = os.environ.get("NOTIFY") or os.path.join(os.path.dirname(BOT_DIR), "scripts", "notificar.sh")
ESTADO = os.environ.get("OV_ESTADO_PY") or os.path.join(BOT_DIR, "estado.py")
# status -> (label, which "done" marker closes it). 04/10 (cap 121 A2): the guard used to be
# `acao_feita_em or teste_feito_em`, a disjunction ACROSS statuses. A record that reached "entrevista",
# got its acao_feita_em marked, and then advanced to "etapa_teste" kept the old marker and was skipped
# forever — 88 runs, 0 kits sent. The marker is per status, so the map is per status.
ATIVO = {"etapa_teste": ("📝 TESTE", "teste_feito_em"),
         "entrevista": ("🎤 ENTREVISTA", "acao_feita_em"),
         "proxima_etapa": ("👀 PRÓXIMA ETAPA", "acao_feita_em")}
MESES_EN = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
MESES_PT = {m: i for i, m in enumerate(("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"), 1)}


def load(p, padrao):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def data_evento(trecho, hoje):
    """Calendar invite subject: '... @ Thu Oct 1, 2026' or '... @ qui., 1 de out. de 2026' -> ISO date."""
    t = str(trecho or "").lower()
    if m := re.search(r"@ [a-z]{3}\w* ([a-z]{3})\w* (\d{1,2})\b", t):
        mo, d = MESES_EN.get(m.group(1)), int(m.group(2))
    elif m := re.search(r"@ \w+\.?,? (\d{1,2}) de ([a-z]{3})", t):
        mo, d = MESES_PT.get(m.group(2)), int(m.group(1))
    else:
        return None
    if not mo:
        return None
    try:
        dt = date(hoje.year, mo, d)
        if (hoje - dt).days > 180:   # 'Jan 5' seen in December = next year
            dt = date(hoje.year + 1, mo, d)
    except ValueError:
        return None
    return dt.isoformat()


def kit(a, evento):
    linhas = [f"🧰 {ATIVO[a['status']][0]} — {a.get('empresa')}",
              f"Vaga: {a.get('vaga') or '?'}"]
    if evento:
        linhas.append(f"Quando: {evento[8:]}/{evento[5:7]} (veja o horário no convite do Gmail)")
    if a.get("url"):
        linhas.append(f"Link: {a['url']}")
    linhas.append(f"Como foi enviada: {a.get('como') or '?'} em {a.get('data') or '?'}")
    if a.get("cv"):
        linhas.append(f"CV enviado: {str(a['cv'])[:90]}")
    modelo = os.environ.get("OV_KIT_FEITO") or 'python3 bot/estado.py set-campo {chave} acao_feita_em "AAAA-MM-DD"'
    linhas.append("Ao terminar: " + modelo.format(chave=a.get("chave"), empresa=a.get("empresa")))
    return "\n".join(linhas)


def marcar(chave, campo, valor, dry):
    if not dry:
        subprocess.run([sys.executable, ESTADO, "--file", APLICADAS, "set-campo", chave, campo, json.dumps(valor)],
                       check=False, capture_output=True, timeout=30)


def avisar(msg, dry):
    print(msg + "\n")
    if not dry and os.path.exists(NOTIFY):
        subprocess.run([NOTIFY, msg], check=False, timeout=60)


def main(dry=False, hoje=None, agora_h=None):
    hoje = hoje or date.today()
    agora_h = datetime.now().hour if agora_h is None else agora_h
    trechos = {}
    for f in load(GMAIL, {}).get("achados", []):
        trechos.setdefault(f.get("chave"), []).append(f.get("trecho"))
    n = 0
    for a in load(APLICADAS, {}).get("aplicadas", []):
        if not isinstance(a, dict) or a.get("status") not in ATIVO:
            continue
        if a.get(ATIVO[a["status"]][1]):
            continue          # this status was already closed; a marker from another status does not close this one
        evento = a.get("evento_em") or next((e for e in (data_evento(t, hoje) for t in trechos.get(a.get("chave"), [])) if e), None)
        if evento and evento != a.get("evento_em"):
            marcar(a["chave"], "evento_em", evento, dry)
        if a.get("kit_status") != a["status"]:
            avisar(kit(a, evento), dry)
            marcar(a["chave"], "kit_status", a["status"], dry)
            n += 1
        if evento == hoje.isoformat() and a.get("lembrete_em") != evento and agora_h >= 7:
            avisar(f"⏰ HOJE: {ATIVO[a['status']][0]} — {a.get('empresa')} ({a.get('vaga') or '?'}). "
                   f"Horário no convite do Gmail.", dry)
            marcar(a["chave"], "lembrete_em", evento, dry)
            n += 1
    print(f"kit-entrevista: {n} aviso(s){' (dry)' if dry else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry="--dry" in sys.argv))
