#!/usr/bin/env python3
"""Daily canary of the portal parsers. bot/descobrir.py reads public pages whose markup the portals change
without notice; without this, a broken parser just means "0 new jobs" forever. This runs each parser LIVE once
and alerts (scripts/notificar.sh|ps1, Telegram) when one returns nothing usable.

  canario-fontes.py          live check (cron / Task Scheduler, once a day); exit 0 ok, 2 = some parser broke

Contract checked, per source enabled in descoberta.json "fontes" (the same contract tests/test_canario_fontes.sh
checks OFFLINE against the fixtures in tests/fixtures/):
  - linkedin search   -> >= 1 job with id, titulo and url
  - linkedin job page -> non-empty description AND the official experience level
  - gupy search API   -> >= 1 job with id, titulo and url, and a description
  - each job board in descoberta.json "boards" -> >= 1 job with titulo and url (robots.txt honoured)
The fixtures are SYNTHETIC: they pin the markup this project assumes, so a green offline test does not prove the
portal still serves it. Only this live canary detects drift. It costs 2-3 requests a day (see docs/USO-ETICO.md).
The search term is the first of the active profile; env NOTIFY overrides the notifier (tests).
"""
import os
import sys

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)
import descobrir as d  # noqa: E402


_notificar = d.notificar


def checar(ctx=None, termo=None):
    """List of failure descriptions ([] = every enabled parser produced usable data)."""
    ctx = ctx or d.Ctx()
    # Gupy gets its own short terms: a long LinkedIn-style term ("desenvolvedor java spring boot") can
    # legitimately return 0 jobs there, and that was a false "parser broken" alert (01/10).
    termo_gupy = termo or (ctx.gupy_termos[0] if ctx.gupy_termos else ctx.termos[0])
    termo = termo or ctx.termos[0]
    falhas = []
    if "linkedin" in ctx.cfg["fontes"]:
        try:
            li = [v for v in d.linkedin(ctx, termo) if v.get("titulo") and v.get("url")]
            if not li:
                falhas.append("LinkedIn busca: 0 vagas")
        except Exception as e:
            li = []
            falhas.append(f"LinkedIn busca: {type(e).__name__}")
        if li:
            try:
                texto, nivel = d.linkedin_detalhe(li[0]["id"].split(":", 1)[1])
                if not texto.strip():
                    falhas.append("LinkedIn vaga: descricao vazia")
                if not nivel:
                    falhas.append("LinkedIn vaga: sem nivel de experiencia oficial")
            except Exception as e:
                falhas.append(f"LinkedIn vaga: {type(e).__name__}")
    if "gupy" in ctx.cfg["fontes"]:
        try:
            gp = [v for v in d.gupy(ctx, termo_gupy) if v.get("titulo") and v.get("url")]
            if not gp:
                falhas.append("Gupy busca: 0 vagas")
            elif not any((v.get("_descricao") or "").strip() for v in gp):
                falhas.append("Gupy busca: sem descricao")
        except Exception as e:
            falhas.append(f"Gupy busca: {type(e).__name__}")
    # 05/10: job boards collected by script (descoberta.json "boards", bot/fontes_boards.py) — HTML/Next.js parsers
    # break on any redesign; 1-3 requests per board a day.
    bt = (ctx.cfg.get("board_termos") or ["desenvolvedor junior"])[0]
    for b in ctx.cfg.get("boards") or []:
        try:
            vs = [v for v in d.board(b)(ctx, bt) if v.get("titulo") and v.get("url")]
            if not vs:
                falhas.append(f"{b}: 0 vagas")
        except Exception as e:
            falhas.append(f"{b}: {type(e).__name__}")
    return falhas


def registrar(ctx, falhas):
    """<state dir>/canario_fontes.json {fonte: {em, ok, falha}}: evidence for bot/saude-portais.py (10/10).
    Before, a result lived only in the Telegram alert; "working" could not be told from "never checked"."""
    fontes = [f for f in ("linkedin", "gupy") if f in ctx.cfg["fontes"]] + list(ctx.cfg.get("boards") or [])
    em = d.agora().isoformat(timespec="seconds")
    doc = {}
    for f in fontes:
        prefixo = {"linkedin": "LinkedIn", "gupy": "Gupy"}.get(f, f) + " "
        minhas = [x for x in falhas if x.startswith(prefixo) or x.startswith(f + ":")]
        doc[f] = {"em": em, "ok": not minhas, "falha": "; ".join(minhas)[:200]}
    try:
        d.vf.save_json(os.path.join(ctx.paths["state_dir"], "canario_fontes.json"), doc)
    except OSError:
        pass   # the alert below still goes out


def main():
    ctx = d.Ctx()
    falhas = checar(ctx)
    registrar(ctx, falhas)
    if falhas:
        msg = ("[CANARIO] Parser de portal quebrado: " + "; ".join(falhas)
               + " (o portal mudou? ver bot/descobrir.py e bot/vaga_check.py)")
        print(msg)
        _notificar(msg)
        return 2
    print("canario-fontes: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
