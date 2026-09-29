#!/usr/bin/env python3
"""Compact read/write CLI for aplicadas.json so the agent never has to Read the whole file
(large state files can dominate tool-output tokens). Every write is atomic and prints one
short line.

  estado.py [--file F] resumo                     compact state (injected into the prompt)
  estado.py [--file F] get CHAVE                  full record of one aplicada/bloqueado/quase_la
  estado.py [--file F] tem CHAVE                  "sim <secao>" / "nao"
  estado.py [--file F] ja-visto EMPRESA [TITULO]  applied/blocked records of a company ("MESMA VAGA provavel" first)
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
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jsonlock import gravar, travado  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT = str(SCRIPT_DIR / "aplicadas.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, d):
    gravar(path, d)   # unique tmp + fsync + atomic replace (jsonlock.py)


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
    # Token diet: the full blocked list with reasons was ~18 KB of EVERY prompt. The model only
    # needs "did I see this company already?" -> company names + counts here, and
    # `ja-visto EMPRESA [TITULO]` for the detail of one job.
    ap = d.get("aplicadas", [])
    out.append(f"aplicadas ({len(ap)}) — empresa | vaga (NAO reenvie):")
    for a in ap:
        out.append(f"  {a.get('empresa')} | {str(a.get('vaga'))[:50]}")
    vistos = {}
    for sec in ("bloqueados", "bloqueados_arquivados"):
        v = d.get(sec) or {}
        for k, rec in (v.items() if isinstance(v, dict) else enumerate(v)):
            emp = (rec.get("empresa") if isinstance(rec, dict) else None) or str(k).split("_")[0]
            vistos[emp] = vistos.get(emp, 0) + 1
    out.append(f"bloqueados+arquivados ({sum(vistos.values())}) por empresa — ANTES de abrir vaga de empresa listada, rode "
               f"`estado.py ja-visto \"<empresa>\" \"<titulo>\"`:")
    out.append("  " + ", ".join(f"{e}({n})" if n > 1 else str(e) for e, n in sorted(vistos.items(), key=lambda x: str(x[0]).lower())))
    return "\n".join(out)


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


_STOP = {"de", "da", "do", "e", "em", "para", "com", "a", "o", "the", "and", "remoto", "remote", "home", "office",
         "vaga", "100", "br", "brasil", "pessoa", "desenvolvedora"}


def ja_visto(d, empresa, titulo=""):
    """Lines describing applied/blocked/archived records of this company (best match first)."""
    e = _norm(empresa)
    tt = {w for w in _norm(titulo).split() if len(w) >= 3 and w not in _STOP}
    achados = []
    for sec in ("aplicadas", "quase_la", "bloqueados", "bloqueados_arquivados"):
        v = d.get(sec) or {}
        for k, rec in (v.items() if isinstance(v, dict) else ((x.get("chave") if isinstance(x, dict) else x, x) for x in v)):
            rec = rec if isinstance(rec, dict) else {"motivo": str(rec)}
            re_ = _norm(rec.get("empresa") or "")
            ch = _norm(k)
            # also compare without spaces: "Zeta Soft" x "ZetaSoft" is the same company
            e2, re2, ch2 = e.replace(" ", ""), re_.replace(" ", ""), ch.replace(" ", "")
            if not e2 or not (e2 in re2 or (re2 and re2 in e2) or e2 in ch2):
                continue
            rt = {w for w in _norm(rec.get("vaga") or k).split() if len(w) >= 3 and w not in _STOP}
            score = len(tt & rt) / len(tt) if tt else 0
            achados.append((score, sec, k, rec))
    achados.sort(key=lambda x: -x[0])
    linhas = []
    for score, sec, k, rec in achados[:6]:
        tag = "MESMA VAGA provavel" if tt and score >= 0.5 else "mesma empresa"
        linhas.append(f"{tag} | {sec} | {k} | {str(rec.get('vaga') or '')[:50]} | {short(rec)[:90]}")
    return linhas


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
    if cmd == "ja-visto":
        linhas = ja_visto(d, args[0] if args else "", args[1] if len(args) > 1 else "")
        print("\n".join(linhas) if linhas else "nao visto: pode avaliar")
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


LEITURA = {"resumo", "get", "tem", "ja-visto"}


def main_travado(argv):
    """Writes hold the exclusive state lock for the whole load -> modify -> save; reads take none."""
    com_file = argv[:1] == ["--file"] and len(argv) > 1
    path = argv[1] if com_file else os.environ.get("APLICADAS_FILE", DEFAULT)
    resto = argv[2:] if com_file else argv
    if not resto or resto[0] in LEITURA:
        return main(argv)
    with travado(path):
        return main(argv)


if __name__ == "__main__":
    sys.exit(main_travado(sys.argv[1:]))
