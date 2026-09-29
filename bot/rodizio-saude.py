#!/usr/bin/env python3
"""Adaptive rotation: pauses for 48h a site that goes PAUSE_AFTER rounds in a row without any
new application, so rounds are not wasted re-scanning dry sites. Deterministic, no LLM.

  rodizio-saude.py pre  [APLICADAS] [--perfil PERFIL]   before the round: skip paused sites in
                                     rodizio.proximo (and, with --perfil, sites outside the profile's area)
  rodizio-saude.py pos  [APLICADAS]   after a successful round: update the site's streak

Once a day (first `pre`; recorded in rodizio.ordem_calculada_em) the order is recomputed by each
site's yield: same number of slots, >=1 per site, the rest proportional to a smoothed score
(applications per round + positive replies), interleaved so a site does not repeat back to back.
Disable with OV_RODIZIO_REORDENAR=0.

State: rodizio_saude.json next to APLICADAS (same state dir as the profile, so each
profile's site-health tracking stays isolated); also read by the monitor.
Optional notifications: scripts/notificar.sh (Telegram), only if the script exists.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from jsonlock import gravar, travado  # noqa: E402
DEFAULT_APLICADAS = SCRIPT_DIR / "aplicadas.json"
NOTIFICAR_SH = SCRIPT_DIR.parent / "scripts" / "notificar.sh"
PAUSE_AFTER = 4
PAUSE_HOURS = 48
REORDENAR = os.environ.get("OV_RODIZIO_REORDENAR", "1") != "0"   # daily yield-based reorder (0 = keep the order as is)


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    gravar(str(p), d, indent=1)   # jsonlock.py: unique tmp + atomic replace


def notify(msg):
    if not NOTIFICAR_SH.exists():
        return
    try:
        subprocess.run([str(NOTIFICAR_SH), msg], timeout=30)
    except Exception:
        pass


def paused(site_info, now):
    until = site_info.get("pausado_ate")
    return bool(until) and datetime.fromisoformat(until) > now


POSITIVOS = {"etapa_teste", "proxima_etapa", "entrevista"}


def nota_site(site, info, aplicadas):
    """Yield score: smoothed applications per round + 2 per positive reply whose `como` names the
    site. Smoothing keeps new/rare sites alive instead of zeroing them."""
    resp = sum(1 for a in aplicadas if (a.get("status") or "") in POSITIVOS
               and site.split(".")[0] in str(a.get("como", "")).lower())
    return (info.get("aplicadas", 0) + 2 * resp + 1) / (info.get("rodadas", 0) + 3)


def reordenar(ordem, sites, aplicadas):
    """Same slot count as the current order, >=1 slot per site, the rest by yield (largest
    remainder), interleaved with smooth weighted round-robin so a site never runs twice in a row
    if avoidable. Deterministic. Returns (new_order, scores)."""
    nomes = list(dict.fromkeys(ordem))
    if len(nomes) < 2:
        return ordem, {}
    total = max(len(ordem), len(nomes))
    notas = {s: nota_site(s, sites.get(s, {}), aplicadas) for s in nomes}
    livres = total - len(nomes)
    soma = sum(notas.values()) or 1
    cotas = {s: livres * notas[s] / soma for s in nomes}
    slots = {s: 1 + int(cotas[s]) for s in nomes}
    for s in sorted(nomes, key=lambda x: cotas[x] - int(cotas[x]), reverse=True)[:total - sum(slots.values())]:
        slots[s] += 1
    atual = {s: 0 for s in nomes}
    nova = []
    for _ in range(total):
        for s in nomes:
            atual[s] += slots[s]
        cands = sorted(nomes, key=lambda x: -atual[x])
        esc = next((c for c in cands if not nova or c != nova[-1]), cands[0])
        atual[esc] -= total
        nova.append(esc)
    return nova, notas


def sites_fora_do_perfil(perfil_path):
    if not perfil_path:
        return set()
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import perfil_render
        return set(perfil_render.resolver(perfil_render.carregar(perfil_path))["sites_pular"])
    except Exception:
        return set()


def main(cmd, aplicadas_path, perfil_path=None):
    now = datetime.now()
    saude_path = Path(aplicadas_path).resolve().parent / "rodizio_saude.json"
    saude = load(saude_path, {"sites": {}})
    sites = saude.setdefault("sites", {})
    d = load(aplicadas_path, None)
    if d is None:
        print("rodizio-saude: aplicadas ilegivel, nada feito")
        return 0
    rod = d.get("rodizio", {})
    ordem = rod.get("ordem") or []

    if cmd == "pre" and ordem and REORDENAR and rod.get("ordem_calculada_em") != now.strftime("%Y-%m-%d"):
        # Once a day, before the first round: the order follows each site's yield.
        nova, notas = reordenar(ordem, sites, d.get("aplicadas", []))
        if nova != ordem:
            prox = rod.get("proximo")
            rod["ordem"] = nova
            rod["pos"] = nova.index(prox) if prox in nova else 0
            print("rodizio-saude: ordem por rendimento -> " + ",".join(nova) + " | notas "
                  + ", ".join(f"{k}={v:.2f}" for k, v in sorted(notas.items(), key=lambda x: -x[1])))
        rod["ordem_calculada_em"] = now.strftime("%Y-%m-%d")
        d["rodizio"] = rod
        save(aplicadas_path, d)
        ordem = rod["ordem"]

    if cmd == "pre":
        atual = rod.get("proximo")
        pos = rod.get("pos")
        if not (isinstance(pos, int) and 0 <= pos < len(ordem) and ordem[pos] == atual):
            pos = ordem.index(atual) if atual in ordem else 0
        pulados = []
        fora = sites_fora_do_perfil(perfil_path)
        for _ in range(len(ordem)):
            if not paused(sites.get(ordem[pos], {}), now) and ordem[pos] not in fora:
                break
            pulados.append(ordem[pos])
            pos = (pos + 1) % len(ordem)
        else:
            pulados = []  # everything paused: keep original, do not starve the loop
            pos = ordem.index(atual) if atual in ordem else 0
        if pulados and ordem:
            rod["proximo"], rod["pos"] = ordem[pos], pos
            save(aplicadas_path, d)
            print(f"rodizio-saude: pulando {','.join(pulados)} (pausados/fora da area), rodada vai em {ordem[pos]}")
        q = d.get("quase_la") or {}
        saude["rodada_atual"] = {"site": rod.get("proximo"), "pos": rod.get("pos"), "aplicadas_antes": len(d.get("aplicadas", [])),
                                 "quase_la_antes": sorted(q) if isinstance(q, dict) else []}
    elif cmd == "pos":
        cur = saude.pop("rodada_atual", None)
        if cur and cur.get("site"):
            s = sites.setdefault(cur["site"], {"rodadas": 0, "vazias_seguidas": 0, "aplicadas": 0, "pausado_ate": None})
            novas = len(d.get("aplicadas", [])) - int(cur.get("aplicadas_antes", 0))
            for a in d.get("aplicadas", [])[len(d.get("aplicadas", [])) - max(novas, 0):] if novas > 0 else []:
                notify(f"✅ Candidatura enviada: {a.get('empresa')} — {a.get('vaga')} ({a.get('como')})")
            q = d.get("quase_la") or {}
            for k in (sorted(set(q) - set(cur.get("quase_la_antes", []))) if isinstance(q, dict) else []):
                notify(f"⚠️ Vaga quase lá, falta um dado seu: {k} — {json.dumps(q[k], ensure_ascii=False)[:250]}")
            s["rodadas"] += 1
            # The loop owns the rotation (the agent may have already advanced it at the
            # START of the round and then done the next site). Advance only if it did not.
            if ordem and rod.get("proximo") == cur["site"]:
                p0 = cur.get("pos")
                if not (isinstance(p0, int) and 0 <= p0 < len(ordem) and ordem[p0] == cur["site"]):
                    p0 = ordem.index(cur["site"]) if cur["site"] in ordem else -1
                p1 = (p0 + 1) % len(ordem)
                rod["proximo"], rod["pos"] = ordem[p1], p1
                rod["ultima_rodada"] = now.strftime("%Y-%m-%d")
                save(aplicadas_path, d)
            if novas > 0:
                s["aplicadas"] += novas
                s["vazias_seguidas"] = 0
            else:
                s["vazias_seguidas"] += 1
                if s["vazias_seguidas"] >= PAUSE_AFTER:
                    s["pausado_ate"] = (now + timedelta(hours=PAUSE_HOURS)).isoformat(timespec="minutes")
                    s["vazias_seguidas"] = 0
                    print(f"rodizio-saude: {cur['site']} pausado ate {s['pausado_ate']} ({PAUSE_AFTER} rodadas sem aplicar)")
                    notify(f"⏸️ Site {cur['site']} pausado por {PAUSE_HOURS}h: {PAUSE_AFTER} rodadas seguidas sem candidatura")
    saude["atualizado"] = now.isoformat(timespec="minutes")
    save(saude_path, saude)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("pre", "pos"):
        print(__doc__)
        sys.exit(2)
    args = sys.argv[2:]
    perfil = None
    if "--perfil" in args:
        i = args.index("--perfil")
        perfil = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    _ap = args[0] if args else str(DEFAULT_APLICADAS)
    with travado(_ap):   # same exclusive lock as estado.py
        sys.exit(main(sys.argv[1], _ap, perfil))
