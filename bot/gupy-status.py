#!/usr/bin/env python3
"""bot/gupy-status.py — status of every Gupy application read BY SCRIPT from "Minhas candidaturas" (no LLM).

  gupy-status.py [--dry]    reads https://portal.gupy.io/my/applications (the 3 tabs) in the robot's Chrome and
                            updates aplicadas.json via `estado.py status` (never downgrades, respects status_manual)

Seen live (logged in): tabs are role=tab buttons "Em andamento" / "Em banco de talentos" / "Finalizadas";
each card has #company-name-<id> (aria-label "Empresa X"), #job-name-<id> (title) and "Seu Progresso k/n".
  Em andamento k=1 -> em_analise · k>=2 -> proxima_etapa · banco de talentos / Finalizadas -> encerrada
Replaces the LLM follow-up for Gupy (the weekly follow-up skips Gupy while this read is fresh).
Needs the Chrome lock and a Gupy session in the robot's Chrome:
  bot/chrome-lock.sh gupy alta 600 -- python3 bot/gupy-status.py      (see config/crontab.example)
State: gupy_status.json next to APLICADAS_FILE (last read, cards not matched to any registered application).
Applications found on Gupy but not registered (made by hand) are recorded as registro_retroativo.
Exit: 0 ok · 1 not logged in / page changed (nothing written).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.realpath(__file__))
APLICADAS = os.environ.get("APLICADAS_FILE", os.path.join(BASE, "aplicadas.json"))
URL = "https://portal.gupy.io/my/applications"
ABAS = ["Em andamento", "Em banco de talentos", "Finalizadas"]
ORDEM = {"enviada": 0, "sem_resposta": 0, "sem_retorno_verificavel": 0, "em_analise": 1, "proxima_etapa": 2,
         "etapa_teste": 2, "entrevista": 3, "encerrada": 4}   # same as gmail-status.py


def _mod(nome, arquivo):
    s = importlib.util.spec_from_file_location(nome, os.path.join(BASE, arquivo))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


estado = _mod("estado", "estado.py")


def classe(aba, progresso):
    if aba != "Em andamento":
        return "encerrada"
    m = re.match(r"(\d+)\s*/\s*(\d+)", progresso or "")
    return "proxima_etapa" if m and int(m.group(1)) >= 2 else "em_analise"


def nota(a, empresa, vaga, job_id=None):
    """Same company and share of the card's title words (>=0.5 counts as the same job)."""
    e, ea = estado._norm(empresa), estado._norm(a.get("empresa"))
    if not e or not ea or not (e in ea or ea in e):
        return 0.0
    # a Gupy job id (in the card title, e.g. "12345678 - DESENVOLVEDOR JUNIOR", or read from the application
    # page for ambiguous cards) that is in the key/url = same job
    ids = set(re.findall(r"\d{6,}", vaga or "")) | ({job_id} if job_id else set())
    if ids and any(i in str(a.get("chave", "")) + str(a.get("url", "")) for i in ids):
        return 2.0
    tt = {w for w in estado._norm(vaga).split() if len(w) >= 3 and w not in estado._STOP}
    ta = {w for w in estado._norm(a.get("vaga")).split() if len(w) >= 3 and w not in estado._STOP}
    # over the SHORTER title: the card often carries a longer title than the one registered
    return len(tt & ta) / min(len(tt), len(ta)) if tt and ta else 0.0


def casar_todos(aplicadas, cartoes):
    """One application per card, most certain cards first (identical titles of one company used to hit ONE record).
    If the best score ties between 2+ free applications the card is 'ambiguo' and nothing is written (no guessing)."""
    melhor = lambda i: max((nota(a, cartoes[i]["empresa"], cartoes[i]["vaga"], cartoes[i].get("job_id")) for a in aplicadas), default=0)
    par, ambiguos, usados = {}, set(), set()
    for i in sorted(range(len(cartoes)), key=melhor, reverse=True):
        c = cartoes[i]
        notas = [(nota(a, c["empresa"], c["vaga"], c.get("job_id")), j) for j, a in enumerate(aplicadas) if j not in usados]
        topo = max((s for s, _ in notas), default=0)
        if topo < 0.5:
            continue
        empatados = [j for s, j in notas if s == topo]
        if len(empatados) > 1:
            ambiguos.add(i)
            continue
        par[i] = aplicadas[empatados[0]]
        usados.add(empatados[0])
    return par, ambiguos


LER_CARTOES = r"""JSON.stringify([...document.querySelectorAll('[id^="job-name-"]')].map(h => {
  const id = h.id.replace('job-name-', '');
  const emp = document.getElementById('company-name-' + id);
  let c = h; for (let i = 0; i < 8 && c.parentElement; i++) { c = c.parentElement; if ((c.innerText || '').includes('Seu Progresso')) break; }
  const m = (c.innerText || '').match(/Seu Progresso\s*(\d+\s*\/\s*\d+)/);
  const ap = c.querySelector('a[href*="/candidates/applications/"]');
  return {id, app: ap ? ap.href : '', empresa: ((emp && emp.getAttribute('aria-label')) || '').replace(/^Empresa\s+/, ''),
          vaga: (h.innerText || '').trim(), progresso: m ? m[1] : ''};
}))"""


def ler(ch):
    tid, sid = ch.abrir(URL)
    try:
        time.sleep(12)
        url, texto = ch.estado(sid)
        if "/my/applications" not in url or "Minhas candidaturas" not in texto:
            return None, f"pagina inesperada ({url[:60]}): deslogado ou layout mudou"
        cartoes = []
        for aba in ABAS:
            if not ch.clicar(sid, aba):
                return None, f"aba '{aba}' nao achada (layout mudou?)"
            time.sleep(6)
            for _ in range(4):   # lazy lists: scroll to the end a few times
                ch.js(sid, "window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
            for c in json.loads(ch.js(sid, LER_CARTOES) or "[]"):
                c["aba"] = aba
                cartoes.append(c)
        return cartoes, ""
    finally:
        ch.fechar(tid)


def job_ids(ch, cartoes, indices):
    """Job id of each ambiguous card, from its application page (the "clique aqui" link -> /jobs/<id>)."""
    for i in indices:
        if not cartoes[i].get("app"):
            continue
        tid, sid = ch.abrir(cartoes[i]["app"])
        try:
            time.sleep(8)
            m = re.search(r"/jobs/(\d{6,})", ch.js(sid, "document.documentElement.innerHTML") or "")
            if m:
                cartoes[i]["job_id"] = m.group(1)
        finally:
            ch.fechar(tid)


def aplicar(cartoes, dry, ch=None):
    d = json.load(open(APLICADAS))
    ap = d.get("aplicadas", [])
    mudou, iguais, sem_registro = [], 0, []
    cartoes = list({c["id"]: c for c in cartoes}.values())   # a card seen in 2 tabs: last tab wins
    par, ambiguos = casar_todos(ap, cartoes)
    if ambiguos and ch:
        job_ids(ch, cartoes, ambiguos)
        par, ambiguos = casar_todos(ap, cartoes)
    for i, c in enumerate(cartoes):
        a = par.get(i)
        if not a:
            sem_registro.append(f"{c['empresa']} — {c['vaga']} ({c['aba']})" + (" [ambiguo: mais de um registro igual]" if i in ambiguos else ""))
            if i not in ambiguos and not dry:
                registrar_retroativo(c)
            continue
        novo, atual = classe(c["aba"], c["progresso"]), a.get("status") or "enviada"
        if a.get("status_manual") or ORDEM.get(novo, 0) <= ORDEM.get(atual, 0):
            iguais += 1
            continue
        det = f"Gupy: {c['aba'].lower()}" + (f", progresso {c['progresso']}" if c["progresso"] else "")
        mudou.append(f"{a['chave']}: {atual} -> {novo} ({det})")
        if not dry:
            subprocess.run(["python3", os.path.join(BASE, "estado.py"), "--file", APLICADAS, "status", a["chave"], novo, det],
                           stdout=subprocess.DEVNULL, check=False)
    return mudou, iguais, sem_registro


def registrar_retroativo(c):
    """Application made OUTSIDE the robot (found on Gupy): recorded so stats and dedupe see it. Send date unknown ->
    registro_retroativo (no date is invented; the rotation does not count it as a send of the round)."""
    rec = {"chave": f"gupy_{c['id']}", "empresa": c["empresa"], "vaga": c["vaga"][:160], "registro_retroativo": True,
           "como": "Gupy (feita fora do robo; registrada pelo gupy-status)", "url": c.get("app") or None,
           "status": classe(c["aba"], c["progresso"])}
    subprocess.run(["python3", os.path.join(BASE, "estado.py"), "--file", APLICADAS, "add-aplicada", json.dumps(rec, ensure_ascii=False)],
                   stdout=subprocess.DEVNULL, check=False)


def main(argv):
    dry = "--dry" in argv
    sys.path.insert(0, BASE)
    from cdp import Chrome
    ch = Chrome()
    cartoes, erro = ler(ch)
    if cartoes is None:
        print(f"gupy-status: {erro}; nada gravado")
        return 1
    mudou, iguais, sem = aplicar(cartoes, dry, ch)
    print(f"gupy-status: {len(cartoes)} cartoes, {len(mudou)} status atualizados, {iguais} sem mudanca, "
          f"{len(sem)} no Gupy sem registro" + (" (dry)" if dry else ""))
    for m in mudou:
        print("  " + m)
    if not dry:
        with open(os.path.join(os.path.dirname(os.path.abspath(APLICADAS)), "gupy_status.json"), "w") as f:
            json.dump({"atualizado": datetime.now().astimezone().isoformat(timespec="seconds"), "cartoes": len(cartoes),
                       "mudancas": mudou, "sem_registro": sem}, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
