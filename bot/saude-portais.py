#!/usr/bin/env python3
"""saude-portais.py — one evidence-based state per portal, from the files the robot already writes (10/10).

  saude-portais.py            table;  --json  machine output;  --gravar  also writes <state>/saude_portais.json
  --dir DIR / --aplicadas F   explicit locations (default: the active profile's state dir, as the loop resolves it).
                              A private install keeps aplicadas.json at its root and the side files in state/.

States (first match wins, each with its evidence and date):
  login_necessario       last login check of the channel said "nao", or compatible jobs wait for its login
  indisponivel           the reachability probe saw a block page (sonda_sites.json) in the last JANELA_H hours
  falha_recente          the parser canary (canario_fontes.json) or the last collection (vagas_fila.json
                         fontes_quebradas / stats.erros) failed in the last JANELA_H hours
  sem_vagas_compativeis  the rotation paused the site for dryness (rodizio_saude.json pausado_ate): it WORKS,
                         it just had no new job — never reported as a failure
  funcionando            some recent (JANELA_H) positive evidence: probe ok, canary ok, scan or application
  nao_verificado         no evidence, or only evidence older than JANELA_H ("aguardando verificacao")
A portal is never "funcionando" just because it is configured. Read-only except --gravar; no personal data
(portal names, states, dates and short technical reasons only).
"""
import json
import os
import sys
from datetime import datetime, timedelta

BOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT)
import vagas_filtros as vf  # noqa: E402

JANELA_H = 48
ESTADOS = ("login_necessario", "indisponivel", "falha_recente", "sem_vagas_compativeis", "funcionando", "nao_verificado")


def _quando(v):
    try:
        t = datetime.fromisoformat(str(v))
        return t if t.tzinfo else t.astimezone()
    except (TypeError, ValueError):
        return None


def avaliar(state_dir, agora=None, aplicadas_path=None):
    agora = agora or datetime.now().astimezone()
    recente = lambda t: t is not None and agora - t <= timedelta(hours=JANELA_H)   # noqa: E731
    ler = lambda nome: vf.load_json(os.path.join(state_dir, nome), {}) or {}        # noqa: E731
    ap = vf.load_json(aplicadas_path, {}) if aplicadas_path else ler("aplicadas.json")
    sonda, canario, fila, rod = ler("sonda_sites.json"), ler("canario_fontes.json"), ler("vagas_fila.json"), ler("rodizio_saude.json")
    sites_rod = rod.get("sites") if isinstance(rod.get("sites"), dict) else {}
    login = ap.get("login_checagens") if isinstance(ap.get("login_checagens"), dict) else {}
    espera = {}
    for v in (ap.get("aguardando_login") or {}).values():
        if isinstance(v, dict) and v.get("canal"):
            espera[str(v["canal"])] = espera.get(str(v["canal"]), 0) + 1
    coleta_em = _quando(fila.get("ultima_coleta"))
    quebradas = set(fila.get("fontes_quebradas") or [])
    erros = {e.split(":", 1)[0] for e in ((fila.get("stats") or {}).get("erros") or []) if isinstance(e, str)}
    # A name seen ONLY in login_checagens is not enough to call it a portal: that map also keeps account logins
    # (gmail/google) and fossils of misspelled channels written by a model (03/10: "solids").
    nomes = set(sonda) | set(canario) | set(sites_rod) | set(espera) | quebradas
    out = {}
    for p in sorted(nomes):
        cands = []   # (state, evidence, when)
        lg = login.get(p) if isinstance(login.get(p), dict) else {}
        if lg.get("logado") == "nao":
            cands.append(("login_necessario", "ultima checagem de login: nao", _quando(lg.get("em"))))
        if espera.get(p):
            cands.append(("login_necessario", f"{espera[p]} vaga(s) compativel(is) aguardando login", None))
        s = sonda.get(p) if isinstance(sonda.get(p), dict) else {}
        if s.get("estado") == "bloqueado" and recente(_quando(s.get("em"))):
            cands.append(("indisponivel", f"sonda: {str(s.get('motivo'))[:80]}", _quando(s.get("em"))))
        c = canario.get(p) if isinstance(canario.get(p), dict) else {}
        if c and not c.get("ok") and recente(_quando(c.get("em"))):
            cands.append(("falha_recente", f"canario: {str(c.get('falha'))[:80]}", _quando(c.get("em"))))
        if (p in quebradas or p in erros) and recente(coleta_em):
            cands.append(("falha_recente", "ultima coleta: busca falhou ou voltou vazia", coleta_em))
        r = sites_rod.get(p) if isinstance(sites_rod.get(p), dict) else {}
        pausa = _quando(r.get("pausado_ate"))
        if pausa and pausa > agora:
            cands.append(("sem_vagas_compativeis",
                          f"{r.get('vazias_seguidas', '?')} rodadas sem vaga nova; pausado ate {r.get('pausado_ate')}", None))
        positivos = [(f"sonda ok", _quando(s.get("em"))) if s.get("estado") == "ok" else None,
                     ("canario ok", _quando(c.get("em"))) if c.get("ok") else None,
                     ("varredura do robo", _quando(r.get("ultima_varredura"))),
                     ("candidatura enviada", _quando(r.get("ultima_aplicada"))),
                     ("login ok", _quando(lg.get("em"))) if lg.get("logado") == "sim" else None]
        positivos = [x for x in positivos if x and recente(x[1])]
        if positivos:
            ev, t = max(positivos, key=lambda x: x[1])
            cands.append(("funcionando", ev, t))
        if not cands:
            ultimo = max([t for t in (_quando(s.get("em")), _quando(c.get("em")), _quando(r.get("ultima_varredura")),
                                      _quando(lg.get("em"))) if t] or [None], key=lambda t: t or agora - timedelta(days=9999))
            cands.append(("nao_verificado", "sem evidencia nas ultimas %dh" % JANELA_H, ultimo))
        estado, ev, t = min(cands, key=lambda x: ESTADOS.index(x[0]))
        out[p] = {"estado": estado, "evidencia": ev, "em": t.isoformat(timespec="minutes") if t else None}
    return out


def _opcao(argv, nome):
    return argv[argv.index(nome) + 1] if nome in argv and argv.index(nome) + 1 < len(argv) else None


def main(argv):
    aplicadas = _opcao(argv, "--aplicadas")
    state_dir = _opcao(argv, "--dir")
    if not state_dir:
        aplicadas = aplicadas or vf.resolve_paths()["aplicadas"]
        state_dir = os.path.dirname(aplicadas)
    res = avaliar(state_dir, aplicadas_path=aplicadas)
    if "--gravar" in argv:
        vf.save_json(os.path.join(state_dir, "saude_portais.json"),
                     {"atualizado": datetime.now().astimezone().isoformat(timespec="minutes"), "portais": res})
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for p, v in res.items():
            print(f"{p:<18} {v['estado']:<22} {v['evidencia']}" + (f" ({v['em']})" if v["em"] else ""))
        if not res:
            print("nenhum portal com evidencia ainda (normal antes das primeiras rodadas)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
