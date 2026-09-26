#!/usr/bin/env python3
"""Adaptive rotation: pauses for 48h a site that goes PAUSE_AFTER rounds in a row without any
new application, so rounds are not wasted re-scanning dry sites. Deterministic, no LLM.

  rodizio-saude.py pre  [APLICADAS] [--perfil PERFIL]   before the round: skip paused sites in
                                     rodizio.proximo (and, with --perfil, sites outside the profile's area)
  rodizio-saude.py pos  [APLICADAS]   after a successful round: update the site's streak

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
DEFAULT_APLICADAS = SCRIPT_DIR / "aplicadas.json"
NOTIFICAR_SH = SCRIPT_DIR.parent / "scripts" / "notificar.sh"
PAUSE_AFTER = 4
PAUSE_HOURS = 48


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


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
    sys.exit(main(sys.argv[1], args[0] if args else str(DEFAULT_APLICADAS), perfil))
