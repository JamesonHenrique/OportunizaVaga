#!/usr/bin/env python3
"""Semantic sanity check of aplicadas.json (complements validate.sh, which checks the schema).

Read-only, quiet on success. Exit 0 = ok, 1 = at least one [FALHA] line printed.
Checks: duplicate keys, local (non-UTC) timestamps coherent with `data`, reencounter-suffix noise in
bloqueados, rodizio.proximo inside rodizio.ordem, descartes_listagem.total == nivel+modelo+stack.

  validate-rodada.py [ARQUIVO]     default: $APLICADAS_FILE, else the active profile's state, else bot/aplicadas.json
Set OV_ALLOW_UTC=1 if you really keep UTC timestamps.
"""
import json
import os
import re
import sys
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent.parent / "bot"


def default_path():
    if os.environ.get("APLICADAS_FILE"):
        return os.environ["APLICADAS_FILE"]
    perfil = os.environ.get("BOT_PERFIL") or (str(BOT_DIR / "perfil.json") if (BOT_DIR / "perfil.json").exists() else "")
    if perfil and os.path.exists(perfil):
        try:
            nome = json.load(open(perfil, encoding="utf-8")).get("nome_perfil", "")
        except Exception:
            nome = ""
        slug = re.sub(r"[^a-z0-9]+", "-", str(nome).lower()).strip("-")[:48]
        if slug:
            return str(BOT_DIR / "state" / slug / "aplicadas.json")
    return str(BOT_DIR / "aplicadas.json")


def check(ap, allow_utc=False):
    falhas = []
    apl = ap.get("aplicadas", []) or []
    chaves = [str(a.get("chave") or a.get("vaga")) for a in apl if isinstance(a, dict)]
    dup = sorted({c for c in chaves if chaves.count(c) > 1})
    if dup:
        falhas.append("aplicadas com chave duplicada: %s" % dup)
    for a in apl:
        if not isinstance(a, dict):
            continue
        c, data, ee = a.get("chave"), str(a.get("data") or ""), str(a.get("enviada_em") or "")
        if a.get("registro_retroativo") and not data:
            continue   # found later by bot/gupy-status.py: send date unknown on purpose (never invented)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
            falhas.append("%s: campo 'data' fora do formato YYYY-MM-DD: %r" % (c, data))
        if not allow_utc and (ee.endswith("Z") or ee.endswith("+00:00")):
            falhas.append("%s: 'enviada_em' em UTC, use a hora local com offset: %r" % (c, ee))
        elif data and ee and not ee.startswith(data):
            falhas.append("%s: 'data' (%s) diverge de 'enviada_em' (%s)" % (c, data, ee))
    bloq = ap.get("bloqueados", {}) or {}
    ruido = [k for k in bloq if re.search(r"_\d+[b-z]$", str(k))]
    if ruido:
        falhas.append("bloqueados com sufixo de reencontro (ruido; nao crie chave nova, veja o prompt): %s" % ruido[:10])
    rod = ap.get("rodizio", {}) or {}
    ordem = rod.get("ordem")
    if ordem and rod.get("proximo") not in ordem:
        falhas.append("rodizio.proximo invalido: %r" % rod.get("proximo"))
    d = ap.get("descartes_listagem", {}) or {}
    if d:
        tot = sum(int(d.get(k) or 0) for k in ("nivel", "modelo", "stack"))
        if int(d.get("total") or 0) != tot:
            falhas.append("descartes_listagem.total (%s) != nivel+modelo+stack (%d)" % (d.get("total"), tot))
    return falhas


def main(argv):
    path = argv[1] if len(argv) > 1 else default_path()
    if not os.path.exists(path):
        print("  [pq] %s ausente — nada a validar." % path)
        return 0
    try:
        ap = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print("  [FALHA] JSON invalido: %s" % e)
        return 1
    falhas = check(ap, os.environ.get("OV_ALLOW_UTC") == "1")
    for f in falhas:
        print("  [FALHA] " + f)
    if falhas:
        print("validate-rodada: FALHOU (veja itens [FALHA] acima).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
