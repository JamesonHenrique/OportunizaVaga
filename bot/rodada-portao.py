#!/usr/bin/env python3
"""bot/rodada-portao.py — decides, WITHOUT an LLM, whether the next round is worth a model session (opt-in: OV_PORTAO=1).

  rodada-portao.py [APLICADAS]   prints one line "MODO motivo" and exits 0:
     completa  the rotation site is due for a scan (rodizio_intervalo_h since its last scan) -> normal round
     so_fila   nothing to scan, but there is queued work (pre-filtered jobs, quase_la/retentar not rechecked
               in 6h) -> round WITHOUT the site scan (step b)
     pular     nothing to do -> no model session at all; the loop sleeps and asks again

Why: every round is a model session with ~20k tokens of fixed context; measured on a real instance, most rounds
re-scanned sites seen minutes before (~12M context tokens per application). A site is due again after
rodizio_intervalo_h[site] hours (config/sites_permitidos.json; default OV_PORTAO_INTERVALO_H, 4). When the due
site is not rodizio.proximo, it moves the rotation to it (estado.py rodizio-avancar). A site that is blocking
the robot (bot/sonda-sites.py) is not due for 12h.
State (next to APLICADAS_FILE): portao.json, rodizio_saude.json, vagas_fila.json, sonda_sites.json.
Fail-open: any error prints "completa".
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(BASE)
PENDENCIAS_H = 6
SONDAVEIS = {"indeed"}      # sites bot/sonda-sites.py knows how to probe (Indeed: 403 by IP seen in practice)
BLOQUEIO_H = 12
SONDA_VALE_H = 2
SCORE_MIN = 2


def carregar(p, padrao):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def horas_desde(iso, now):
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo:
            t = t.astimezone().replace(tzinfo=None)
        return (now - t).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def site_vencido(site, cfg, saude, now, sonda=None):
    produtivos = list(cfg.get("rodizio_produtivos") or [])
    inter = cfg.get("rodizio_intervalo_h") or {}
    padrao = float(os.environ.get("OV_PORTAO_INTERVALO_H", "4"))
    h = inter.get(site, padrao if (site in produtivos or not produtivos) else inter.get("_exploracao", 24))
    s = (sonda or {}).get(site) or {}
    if s.get("estado") == "bloqueado" and (horas_desde(s.get("em"), now) or 99) < BLOQUEIO_H:
        return False   # the site is blocking the robot: no model session until the block is old
    info = saude.get("sites", {}).get(site, {})
    pausa = info.get("pausado_ate")
    if pausa and (horas_desde(pausa, now) or 0) < 0:
        return False
    desde = horas_desde(info.get("ultima_varredura"), now)
    return desde is None or desde >= h


def trabalho(d, fila, portao, now):
    """Queued work a round can do without scanning a site: [reasons]."""
    out = []
    novas = [v for v in (fila.get("vagas") or {}).values()
             if v.get("status") == "nova" and (v.get("score") or 0) >= SCORE_MIN]
    if novas:
        out.append(f"fila {len(novas)} vaga(s) score>={SCORE_MIN}")
    velha = (horas_desde(portao.get("pendencias_em"), now) or 99) >= PENDENCIAS_H
    if velha and d.get("quase_la"):
        out.append(f"quase_la {len(d['quase_la'])} (recheck {PENDENCIAS_H}h)")
    ret = [k for k, v in (d.get("bloqueados") or {}).items() if isinstance(v, dict) and v.get("retentar")]
    if velha and ret:
        out.append(f"retentar {len(ret)} (recheck {PENDENCIAS_H}h)")
    return out


def decidir(d, fila, cfg, saude, portao, now, sonda=None):
    """(modo, motivo, site_to_move_to_or_None)."""
    rod = d.get("rodizio") or {}
    ordem = rod.get("ordem") or []
    prox = rod.get("proximo")
    t = trabalho(d, fila, portao, now)
    if prox and site_vencido(prox, cfg, saude, now, sonda):
        return "completa", f"varrer {prox}" + (f" + {', '.join(t)}" if t else ""), None
    for s in list(dict.fromkeys(ordem)):
        if s != prox and site_vencido(s, cfg, saude, now, sonda):
            return "completa", f"varrer {s} (rodizio movido de {prox})" + (f" + {', '.join(t)}" if t else ""), s
    if t:
        return "so_fila", ", ".join(t), None
    return "pular", "nada a fazer: nenhum site vencido e fila vazia", None


def mover_rodizio(alvo, ordem, aplicadas):
    for _ in range(len(ordem)):
        d = carregar(aplicadas, {})
        if (d.get("rodizio") or {}).get("proximo") == alvo:
            return
        subprocess.run(["python3", os.path.join(BASE, "estado.py"), "--file", aplicadas, "rodizio-avancar"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv):
    aplicadas = argv[0] if argv else os.environ.get("APLICADAS_FILE") or os.path.join(BASE, "aplicadas.json")
    now = datetime.now()
    try:
        d = carregar(aplicadas, None)
        if d is None:
            raise ValueError("aplicadas ilegivel")
        sdir = os.path.dirname(os.path.abspath(aplicadas))
        fila = carregar(os.path.join(sdir, "vagas_fila.json"), {})
        cfg = carregar(os.path.join(ROOT, "config", "sites_permitidos.json"), {})
        saude = carregar(os.path.join(sdir, "rodizio_saude.json"), {})
        pp = os.path.join(sdir, "portao.json")
        portao = carregar(pp, {})
        sp = os.path.join(sdir, "sonda_sites.json")
        sonda = carregar(sp, {})
        modo, motivo, mover = decidir(d, fila, cfg, saude, portao, now, sonda)
        alvo = mover or (d.get("rodizio") or {}).get("proximo")
        # probe a blockable site right before spending a model session on it (under the Chrome lock)
        if modo == "completa" and alvo in SONDAVEIS and (horas_desde((sonda.get(alvo) or {}).get("em"), now) or 99) >= SONDA_VALE_H:
            subprocess.run([os.path.join(BASE, "chrome-lock.sh"), "sonda", "alta", "120", "--", "python3",
                            os.path.join(BASE, "sonda-sites.py"), alvo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=200, env=dict(os.environ, APLICADAS_FILE=aplicadas))
            sonda = carregar(sp, {})
            modo, motivo, mover = decidir(d, fila, cfg, saude, portao, now, sonda)
        if mover:
            mover_rodizio(mover, (d.get("rodizio") or {}).get("ordem") or [], aplicadas)
        if modo != "pular" and ("quase_la" in motivo or "retentar" in motivo):
            portao["pendencias_em"] = now.isoformat(timespec="minutes")
            with open(pp + ".tmp", "w") as f:
                json.dump(portao, f)
            os.replace(pp + ".tmp", pp)
    except Exception as e:   # never block the robot because of the gate
        modo, motivo = "completa", f"portao falhou ({e.__class__.__name__}): rodada normal"
    print(f"{modo} {motivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
