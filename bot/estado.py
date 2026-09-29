#!/usr/bin/env python3
"""Compact read/write CLI for aplicadas.json so the agent never has to Read the whole file
(large state files can dominate tool-output tokens). Every write is atomic and prints one
short line.

  estado.py [--file F] resumo                     compact state (injected into the prompt)
  estado.py [--file F] get CHAVE                  full record of one aplicada/bloqueado/quase_la
  estado.py [--file F] tem CHAVE                  "sim <secao>" / "nao"
  estado.py [--file F] add-aplicada JSON          append to aplicadas (needs "chave")
  estado.py [--file F] add-bloqueado CHAVE JSON   set bloqueados[CHAVE] (JSON object or plain motivo)
  estado.py [--file F] set-quase-la CHAVE JSON    set quase_la[CHAVE]; JSON=null removes it
  estado.py [--file F] descartes NIVEL MODELO STACK   increments descartes_listagem counters
  estado.py [--file F] status CHAVE ST [MSG] [EMAIL_DATA]   follow-up: em_analise/entrevista/encerrada/sem_resposta/sem_retorno_verificavel
  estado.py [--file F] conta SITE JSON            set contas_criadas[SITE]
  estado.py [--file F] rodizio-avancar            rodizio.proximo -> next in ordem; ultima_rodada=today

Default file: aplicadas.json next to this script, unless overridden by --file or the
APLICADAS_FILE environment variable (bot/loop.sh exports it per active profile).
"""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT = str(SCRIPT_DIR / "aplicadas.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def parse(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def short(v, n=70):
    s = v.get("motivo", "") if isinstance(v, dict) else str(v)
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def resumo(d):
    out = []
    rod = d.get("rodizio", {})
    out.append(f"rodizio.proximo={rod.get('proximo')} ultima_rodada={rod.get('ultima_rodada')} ordem={','.join(rod.get('ordem', []))}")
    out.append(f"pular_empresas={json.dumps(d.get('pular_empresas', []), ensure_ascii=False)}")
    out.append(f"pular_tipos={json.dumps(d.get('pular_tipos', []), ensure_ascii=False)}")
    out.append(f"descartes_listagem={json.dumps(d.get('descartes_listagem', {}))}")
    out.append(f"contas_criadas (sites)={','.join(d.get('contas_criadas', {}) or [])}")
    q = d.get("quase_la") or {}
    out.append(f"quase_la ({len(q)}):")
    for k, v in (q.items() if isinstance(q, dict) else enumerate(q)):
        out.append(f"  {k} | {json.dumps(v, ensure_ascii=False)[:200]}")
    ap = d.get("aplicadas", [])
    out.append(f"aplicadas ({len(ap)}) — chave | empresa | vaga | data:")
    for a in ap:
        out.append(f"  {a.get('chave')} | {a.get('empresa')} | {str(a.get('vaga'))[:60]} | {a.get('data')}")
    b = d.get("bloqueados", {})
    out.append(f"bloqueados ({len(b)}) — chave | data | motivo (curto; detalhe: estado.py get CHAVE):")
    for k, v in (b.items() if isinstance(b, dict) else enumerate(b)):
        dt = v.get("data", "") if isinstance(v, dict) else ""
        out.append(f"  {k} | {dt} | {short(v)}")
    arq = d.get("bloqueados_arquivados")
    if arq:
        keys = list(arq) if isinstance(arq, dict) else [str(x.get("chave", x))[:40] if isinstance(x, dict) else str(x)[:40] for x in arq]
        out.append(f"bloqueados_arquivados (só chaves, {len(keys)}): {', '.join(map(str, keys))}")
    return "\n".join(out)


def main(argv):
    path = os.environ.get("APLICADAS_FILE", DEFAULT)
    if len(argv) > 1 and argv[0] == "--file":
        path, argv = argv[1], argv[2:]
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    d = load(path)
    if cmd == "resumo":
        print(resumo(d))
        return 0
    if cmd in ("get", "tem"):
        k = args[0]
        for sec in ("aplicadas", "bloqueados", "quase_la", "bloqueados_arquivados"):
            v = d.get(sec)
            hit = None
            if isinstance(v, dict) and k in v:
                hit = v[k]
            elif isinstance(v, list):
                hit = next((x for x in v if isinstance(x, dict) and x.get("chave") == k), None)
            if hit is not None:
                print(f"sim {sec}" if cmd == "tem" else json.dumps({sec: hit}, ensure_ascii=False, indent=1))
                return 0
        # Fallback: dotted path into any JSON (rodizio.proximo, experiencia.tecnologias...).
        # Weak models call `get` this way, also on dados_candidato.json.
        cur, ok = d, True
        for part in k.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
                cur = cur[int(part)]
            else:
                ok = False
                break
        if ok:
            if cmd == "tem":
                print("sim caminho")
                return 0
            s = cur if isinstance(cur, str) else json.dumps(cur, ensure_ascii=False, indent=1)
            if len(s) > 4000:
                s = s[:4000] + f"\n… (truncado; {len(s)} chars — o RESUMO DO ESTADO no prompt já lista isso)"
            print(s)
            return 0
        print(f"nao (chaves de topo: {', '.join(d) if isinstance(d, dict) else '-'})")
        return 1
    if cmd == "add-aplicada":
        rec = parse(args[0])
        if not isinstance(rec, dict) or not rec.get("chave"):
            print("erro: JSON precisa ser objeto com 'chave'")
            return 2
        if any(a.get("chave") == rec["chave"] for a in d.setdefault("aplicadas", [])):
            print(f"ja existe em aplicadas: {rec['chave']}")
            return 1
        d["aplicadas"].append(rec)
        (d.get("bloqueados") or {}).pop(rec["chave"], None)
        if isinstance(d.get("quase_la"), dict):
            d["quase_la"].pop(rec["chave"], None)
    elif cmd == "add-bloqueado":
        k, v = args[0], parse(args[1])
        if not isinstance(v, dict):
            v = {"motivo": str(v)}
        v.setdefault("data", date.today().isoformat())
        d.setdefault("bloqueados", {})[k] = v
    elif cmd == "set-quase-la":
        k, v = args[0], parse(args[1])
        q = d.get("quase_la")
        if not isinstance(q, dict):
            q = d["quase_la"] = {}
        if v is None or v == "null":
            q.pop(k, None)
        else:
            q[k] = v
    elif cmd == "descartes":
        dl = d.setdefault("descartes_listagem", {})
        for name, n in zip(("nivel", "modelo", "stack"), args):
            dl[name] = int(dl.get(name, 0)) + int(n)
        dl["total"] = sum(int(dl.get(x, 0)) for x in ("nivel", "modelo", "stack"))
    elif cmd == "status":
        # status CHAVE STATUS [FOLLOWUP_MSG] [EMAIL_DATA] — used by the weekly follow-up and gmail-status.py.
        # EMAIL_DATA (YYYY-MM-DD) = date of the e-mail that caused the change, shown by the monitor.
        k, st = args[0], args[1]
        rec = next((a for a in d.get("aplicadas", []) if a.get("chave") == k), None)
        if rec is None:
            print(f"nao existe em aplicadas: {k}")
            return 1
        if rec.get("status") != st:
            h = {"de": rec.get("status"), "para": st, "em": datetime.now().astimezone().isoformat(timespec="seconds")}
            if len(args) > 3 and args[3]:
                h["email_data"], h["fonte"] = args[3][:10], "gmail"
            rec.setdefault("historico_status", []).append(h)
        rec["status"] = st
        rec["followup_em"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if len(args) > 2 and args[2]:
            rec["followup_msg"] = args[2][:400]
    elif cmd == "conta":
        d.setdefault("contas_criadas", {})[args[0]] = parse(args[1])
    elif cmd == "rodizio-avancar":
        rod = d.setdefault("rodizio", {})
        ordem = rod.get("ordem") or []
        if ordem:
            # ordem pode ter duplicatas (site de alto retorno 2-3x): rastreia a posicao,
            # index() sozinho ficaria preso alternando entre as duas ocorrencias.
            atual, pos = rod.get("proximo"), rod.get("pos")
            if not (isinstance(pos, int) and 0 <= pos < len(ordem) and ordem[pos] == atual):
                pos = ordem.index(atual) if atual in ordem else -1
            pos = (pos + 1) % len(ordem)
            rod["proximo"], rod["pos"] = ordem[pos], pos
        rod["ultima_rodada"] = date.today().isoformat()
    else:
        print(f"comando desconhecido: {cmd}")
        return 2
    save(path, d)
    print(f"ok {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
