#!/usr/bin/env python3
"""bot/sonda-sites.py SITE — is the site reachable in the robot's Chrome, or is it blocking us?

Prints "ok" / "bloqueado <why>" and records it in <state dir>/sonda_sites.json {site: {em, estado, motivo}}.
Why: a portal can start answering HTTP 403 "Solicitação bloqueada" (Cloudflare, by IP) even to the logged-in
session; a whole model session was spent learning that (and it wrote a fake "blocked job" entry).
bot/rodada-portao.py calls this before a round on a probe-able site and skips the site for 12h when blocked.
Needs the Chrome lock (the gate wraps it). Any error prints "ok" (fail-open: never block the robot by accident).
State dir: the folder of APLICADAS_FILE (per profile), else bot/.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(BASE)
ESTADO = os.path.join(os.path.dirname(os.environ.get("APLICADAS_FILE") or os.path.join(BASE, "aplicadas.json")), "sonda_sites.json")
URLS = {"indeed": "https://br.indeed.com/"}
SINAIS = ["Solicitação bloqueada", "O sistema bloqueou você", "Blocked - Indeed", "Additional Verification Required",
          "Verify you are human", "Verifique se você é humano"]


def bloqueio(texto):
    return next((s for s in SINAIS if s.lower() in (texto or "").lower()), "")


def gravar(site, estado, motivo):
    try:
        d = json.load(open(ESTADO))
    except (OSError, ValueError):
        d = {}
    antes = (d.get(site) or {}).get("estado")
    d[site] = {"em": datetime.now().astimezone().isoformat(timespec="seconds"), "estado": estado, "motivo": motivo}
    tmp = ESTADO + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO)
    if estado == "bloqueado" and antes != "bloqueado":
        subprocess.run([os.path.join(ROOT, "scripts", "notificar.sh"), f"🚧 {site} bloqueou o robô ({motivo}); fica fora do rodízio por 12h"])
    elif estado == "ok" and antes == "bloqueado":
        subprocess.run([os.path.join(ROOT, "scripts", "notificar.sh"), f"✅ {site} voltou a responder ao robô"])


def main(argv):
    site = argv[0] if argv else ""
    if site not in URLS:
        print("ok")   # not probe-able: never blocks the round
        return 0
    try:
        sys.path.insert(0, BASE)
        from cdp import Chrome
        ch = Chrome()
        tid, sid = ch.abrir(URLS[site])
        try:
            time.sleep(10)
            _, texto = ch.estado(sid)
        finally:
            ch.fechar(tid)
    except Exception as e:
        print(f"ok (sonda falhou: {e.__class__.__name__})")
        return 0
    m = bloqueio(texto)
    gravar(site, "bloqueado" if m else "ok", m)
    print(f"bloqueado {m}" if m else "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
