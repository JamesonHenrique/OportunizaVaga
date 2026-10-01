#!/usr/bin/env python3
"""Adaptive rotation: pauses a DRY site — PAUSE_AFTER rounds in a row without registering any new job
(application, block, quase_la or aguardando_login). A site that shows jobs the robot discards is alive,
not dry (a "no application" rule once paused every site at the same time). Pause is 12h, doubling per
repeat up to 48h, and never leaves fewer than MIN_ATIVOS sites active. Deterministic, no LLM.

  rodizio-saude.py pre  [APLICADAS] [--perfil PERFIL]   before the round: skip paused sites in
                                     rodizio.proximo (and, with --perfil, sites outside the profile's area)
  rodizio-saude.py pos  [APLICADAS]   after a successful round: update the site's streak (+ ultima_varredura)
  rodizio-saude.py pos-so-fila [APLICADAS]  after a queue-only round (rodada-portao.py): notifications only,
                                      the site was not scanned (no streak, no advance)

Once a day (first `pre`; recorded in rodizio.ordem_calculada_em; RODIZIO_RECALCULAR=1 forces it) the order
is recomputed. With rodizio_produtivos in the sites config: productive (+ promoted) sites twice each,
weighted by yield, + ONE explorer of the day from rodizio_exploracao (an explorer with an application in
the last PROMOCAO_DIAS days counts as productive). Without it: the current order reweighted by yield
(applications per round + positive replies). Disable reordering with OV_RODIZIO_REORDENAR=0.

Paths (env, read at call time): OV_RODIZIO_SAUDE (state file; default rodizio_saude.json next to
APLICADAS), OV_SITES_CONFIG (sites config with rodizio_produtivos/rodizio_exploracao; default
bot/sites_permitidos.json when present), NOTIFY (notifier; default scripts/notificar.sh when present),
OV_NOTIFY_RESUMO=1 (the notifier understands --resumo: non-urgent alerts go to the daily digest).
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
PAUSE_HOURS = 12          # first pause; doubles on each consecutive pause of the same site
PAUSE_MAX_HOURS = 48
MIN_ATIVOS = 3            # never pause below this many active sites
PROMOCAO_DIAS = 7
POSITIVOS = {"etapa_teste", "proxima_etapa", "entrevista"}


def reordenar_ligado():
    return os.environ.get("OV_RODIZIO_REORDENAR", "1") != "0"


def saude_path(aplicadas_path):
    return Path(os.environ.get("OV_RODIZIO_SAUDE") or Path(aplicadas_path).resolve().parent / "rodizio_saude.json")


def chaves_vistas(d):
    """Every job key the robot has registered anywhere (new key = the site had a new job)."""
    ks = {a.get("chave") for a in d.get("aplicadas", []) if isinstance(a, dict)}
    for sec in ("bloqueados", "quase_la", "aguardando_login", "bloqueados_arquivados"):
        v = d.get(sec)
        if isinstance(v, dict):
            ks |= set(v)
    return ks


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    gravar(str(p), d, indent=1)   # jsonlock.py: unique tmp + atomic replace


def notify(msg, resumo=False):
    """resumo=True: not urgent (sent, paused) — goes to the daily digest when the notifier supports it."""
    cmd = os.environ.get("NOTIFY") or (str(NOTIFICAR_SH) if NOTIFICAR_SH.exists() else "")
    if not cmd:
        return
    try:
        subprocess.run([cmd] + (["--resumo"] if resumo and os.environ.get("OV_NOTIFY_RESUMO") == "1" else []) + [msg],
                       timeout=30)
    except Exception:
        pass


def paused(site_info, now):
    until = site_info.get("pausado_ate")
    return bool(until) and datetime.fromisoformat(until) > now


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


def config_rodizio():
    """(rodizio_produtivos, rodizio_exploracao) from the sites config; ([], []) = plain yield reorder."""
    p = os.environ.get("OV_SITES_CONFIG") or str(SCRIPT_DIR / "sites_permitidos.json")
    c = load(p, {})
    return c.get("rodizio_produtivos") or [], c.get("rodizio_exploracao") or []


def promovidos(exploracao, sites, now):
    """An exploration site that produced an application in the last PROMOCAO_DIAS days acts as productive
    (twice a day in the order, productive interval in the gate) until the streak runs out."""
    out = []
    for x in exploracao:
        u = (sites.get(x) or {}).get("ultima_aplicada")
        try:
            if u and (now - datetime.fromisoformat(u)).days < PROMOCAO_DIAS:
                out.append(x)
        except ValueError:
            pass
    return out


def ordem_do_dia(produtivos, exploracao, sites, aplicadas, now):
    """Productive (+ promoted) sites twice each, weighted by yield, + the day's explorer (skips paused ones)."""
    prom = promovidos(exploracao, sites, now)
    base, notas = reordenar((produtivos + prom) * 2, sites, aplicadas)
    livres = [x for x in exploracao if x not in prom and not paused(sites.get(x, {}), now)] or [x for x in exploracao if x not in prom]
    if livres:
        exp = livres[now.toordinal() % len(livres)]
        base = base[:len(base) // 2] + [exp] + base[len(base) // 2:]
    return base, notas


def sites_fora_do_perfil(perfil_path):
    if not perfil_path:
        return set()
    try:
        import perfil_render
        return set(perfil_render.resolver(perfil_render.carregar(perfil_path))["sites_pular"])
    except Exception:
        return set()


def main(cmd, aplicadas_path, perfil_path=None):
    now = datetime.now()
    sp = saude_path(aplicadas_path)
    saude = load(sp, {"sites": {}})
    sites = saude.setdefault("sites", {})
    d = load(aplicadas_path, None)
    if d is None:
        print("rodizio-saude: aplicadas ilegivel, nada feito")
        return 0
    rod = d.get("rodizio", {})
    ordem = rod.get("ordem") or []

    forcar = os.environ.get("RODIZIO_RECALCULAR") == "1"   # recompute today's order now (config changed)
    if cmd == "pre" and ordem and reordenar_ligado() and (forcar or rod.get("ordem_calculada_em") != now.strftime("%Y-%m-%d")):
        # Once a day, before the first round: the order follows each site's yield.
        produtivos, exploracao = config_rodizio()
        if produtivos:
            nova, notas = ordem_do_dia(produtivos, exploracao, sites, d.get("aplicadas", []), now)
        else:
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
                                 "quase_la_antes": sorted(q) if isinstance(q, dict) else [],
                                 "chaves_antes": len(chaves_vistas(d))}
    elif cmd == "pos-so-fila":
        # queue-only round (rodada-portao.py): notifications only — the site was NOT scanned (no streak, no advance)
        cur = saude.pop("rodada_atual", None) or {}
        for a in d.get("aplicadas", [])[int(cur.get("aplicadas_antes", len(d.get("aplicadas", [])))):]:
            if not a.get("registro_retroativo"):
                notify(f"✅ Candidatura enviada: {a.get('empresa')} — {a.get('vaga')} ({a.get('como')})", resumo=True)
    elif cmd == "pos":
        cur = saude.pop("rodada_atual", None)
        if cur and cur.get("site"):
            s = sites.setdefault(cur["site"], {"rodadas": 0, "vazias_seguidas": 0, "aplicadas": 0, "pausado_ate": None})
            # appended since pre, minus applications found later by gupy-status (not sent this round)
            novas_lista = [x for x in d.get("aplicadas", [])[int(cur.get("aplicadas_antes", 0)):] if not x.get("registro_retroativo")]
            novas = len(novas_lista)
            for a in novas_lista:
                notify(f"✅ Candidatura enviada: {a.get('empresa')} — {a.get('vaga')} ({a.get('como')})", resumo=True)
            q = d.get("quase_la") or {}
            for k in (sorted(set(q) - set(cur.get("quase_la_antes", []))) if isinstance(q, dict) else []):
                notify(f"⚠️ Vaga quase lá, falta um dado seu: {k} — {json.dumps(q[k], ensure_ascii=False)[:250]}")
            s["rodadas"] += 1
            s["ultima_varredura"] = now.isoformat(timespec="minutes")   # read by rodada-portao.py (interval)
            # The loop owns the rotation (the agent may have already advanced it at the START of the
            # round and then done the next site). Advance only if it did not.
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
                s["ultima_aplicada"] = now.isoformat(timespec="minutes")   # promotion of exploration sites
            # Old state files have no chaves_antes: treat as "had news" instead of guessing dry.
            teve_vaga = novas > 0 or "chaves_antes" not in cur or len(chaves_vistas(d)) > int(cur["chaves_antes"])
            if teve_vaga:
                s["vazias_seguidas"] = 0
                s["pausas_seguidas"] = 0
            else:
                s["vazias_seguidas"] += 1
                if s["vazias_seguidas"] >= PAUSE_AFTER:
                    ativos = [x for x in set(ordem) if x != cur["site"] and not paused(sites.get(x, {}), now)]
                    s["vazias_seguidas"] = 0
                    if len(ativos) < MIN_ATIVOS:
                        print(f"rodizio-saude: {cur['site']} seco, mas NAO pausado (so {len(ativos)} outros sites ativos)")
                    else:
                        horas = min(PAUSE_MAX_HOURS, PAUSE_HOURS * 2 ** int(s.get("pausas_seguidas", 0)))
                        s["pausas_seguidas"] = int(s.get("pausas_seguidas", 0)) + 1
                        s["pausado_ate"] = (now + timedelta(hours=horas)).isoformat(timespec="minutes")
                        print(f"rodizio-saude: {cur['site']} pausado ate {s['pausado_ate']} ({PAUSE_AFTER} rodadas sem vaga nova)")
                        notify(f"⏸️ Site {cur['site']} pausado por {horas}h: {PAUSE_AFTER} rodadas seguidas sem nenhuma vaga nova",
                               resumo=True)
    saude["atualizado"] = now.isoformat(timespec="minutes")
    save(sp, saude)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("pre", "pos", "pos-so-fila"):
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
