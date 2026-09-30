#!/usr/bin/env python3
"""Compact read/write CLI for aplicadas.json so the agent never has to Read the whole file
(large state files can dominate tool-output tokens). Every write is atomic and prints one
short line.

  estado.py [--file F] resumo                     compact state (injected into the prompt)
  estado.py [--file F] get CHAVE                  full record of one aplicada/bloqueado/quase_la
  estado.py [--file F] tem CHAVE                  "sim <secao>" / "nao"
  estado.py [--file F] ja-visto EMPRESA [TITULO]  applied/blocked records of a company ("MESMA VAGA provavel" first)
  estado.py [--file F] add-aplicada JSON          append to aplicadas (needs "chave"); also records "ats" coverage
                                                  when "cv" names a CV_*.pdf and the posting saved in step c1 is fresh
  estado.py [--file F] add-bloqueado CHAVE JSON   set bloqueados[CHAVE] (JSON object or plain motivo)
  estado.py [--file F] set-quase-la CHAVE JSON    set quase_la[CHAVE]; JSON=null removes it
  estado.py [--file F] descartes N N N               increments descartes_listagem (nivel modelo stack), e.g. 3 1 2
  estado.py [--file F] status CHAVE ST [MSG] [EMAIL_DATA]   follow-up: em_analise/entrevista/encerrada/sem_resposta/sem_retorno_verificavel
  estado.py [--file F] conta SITE JSON            set contas_criadas[SITE]
  estado.py [--file F] rodizio-avancar            rodizio.proximo -> next in ordem; ultima_rodada=today
  estado.py [--file F] del-aplicada CHAVE MOTIVO  move a WRONG record (e.g. a duplicate) to aplicadas_removidas (kept, not lost)
  estado.py dado CAMPO[.SUB]                       one field of dados_candidato.json (e.g. respostas_padrao_gupy.pretensao)
  estado.py resumo-candidato                      compact candidate digest injected into the prompt (bot/loop.sh)

Default file: aplicadas.json next to this script, unless overridden by --file or the
APLICADAS_FILE environment variable (bot/loop.sh exports it per active profile).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jsonlock import gravar, travado  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT = str(SCRIPT_DIR / "aplicadas.json")


ANUNCIO = os.environ.get("ANUNCIO_FILE") or os.path.join(tempfile.gettempdir(), "anuncio.txt")


def medir_ats(rec, max_idade_s=1200):
    """Records rec["ats"] = {"geral": %, "perfil": %|None} so the value of the per-job CV is measurable
    (before, it only existed when the model remembered to write it down). Deterministic: runs
    check_ats.py on the posting the model saved in step c1 (ANUNCIO_FILE, default <tmp>/anuncio.txt) and
    the CV named in rec["cv"], only if that file is fresh (< 20 min), so another job's text is never used.
    Best effort: any failure leaves the record untouched."""
    if rec.get("ats") is not None:
        return
    m = re.search(r"(CV_[\w.-]+\.pdf)", str(rec.get("cv") or ""))
    base = str(SCRIPT_DIR)
    if not m:
        return
    cv = next((c for c in (str(rec.get("cv")), os.path.join(base, m.group(1))) if os.path.isfile(c)), None)
    try:
        fresco = time.time() - os.path.getmtime(ANUNCIO) < max_idade_s
    except OSError:
        fresco = False
    if not (cv and fresco):
        return
    script = os.environ.get("OV_CHECK_ATS") or os.path.join(base, "check_ats.py")
    try:
        r = subprocess.run([sys.executable, script, ANUNCIO, cv], capture_output=True, text=True, timeout=60)
        g = re.search(r"cobertura geral do CV: (\d+)%", r.stdout)
        p = re.search(r"cobertura dos termos DO PERFIL: (\d+)%", r.stdout)
        if g:
            rec["ats"] = {"geral": int(g.group(1)), "perfil": int(p.group(1)) if p else None}
    except Exception:
        pass


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
    # One "empresa | vaga" line per application grew with every send (~3 KB at 50); the model only needs the
    # company name to trigger `ja-visto`, which has the per-job detail.
    ap = d.get("aplicadas", [])
    por_emp = {}
    for a in ap:
        por_emp[a.get("empresa")] = por_emp.get(a.get("empresa"), 0) + 1
    out.append(f"aplicadas ({len(ap)}) por empresa — NAO reenvie; empresa listada = rode ja-visto antes de abrir:")
    out.append("  " + ", ".join(f"{e}({n})" if n > 1 else str(e) for e, n in sorted(por_emp.items(), key=lambda x: str(x[0]).lower())))
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


STATUS_OK = {"enviada", "em_analise", "etapa_teste", "proxima_etapa", "entrevista", "encerrada",
             "respondida", "sem_resposta", "sem_retorno_verificavel", "followup"}

# Candidate digest for the prompt: the model used to read the whole dados_candidato.json (~10 KB) in about half
# of the sessions and kept it in context for every later call. Anything outside the digest: `estado.py dado CAMPO`.
RESUMO_CAMPOS = ["nome", "email", "email_contas", "regra_emails", "telefone", "linkedin", "github", "local", "endereco",
                 "formacao", "idiomas", "disponibilidade", "preferencias", "situacao_profissional",
                 "experiencia.cargo_atual", "experiencia.empresa_atual", "experiencia.inicio_cargo_atual",
                 "experiencia.tecnologias", "experiencia.portfolio"]


def arquivo_dados():
    return os.environ.get("DADOS_CANDIDATO_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_candidato.json")


def campo_dados(dados, caminho):
    v = dados
    for parte in caminho.split("."):
        if not isinstance(v, dict) or parte not in v:
            return None
        v = v[parte]
    return v


def resumo_candidato(dados):
    linhas = []
    for c in RESUMO_CAMPOS:
        v = campo_dados(dados, c)
        if v in (None, "", [], {}):
            continue
        linhas.append(f"{c}: " + (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(",", ":"))))
    topo = {c.split(".")[0] for c in RESUMO_CAMPOS}
    fora = [k for k in dados if k not in topo and not k.startswith("_")]
    exp = [k for k in (dados.get("experiencia") or {}) if f"experiencia.{k}" not in RESUMO_CAMPOS]
    linhas.append("fora do resumo (use `estado.py dado CAMPO` so se um formulario pedir): " + ", ".join(fora)
                  + (" | experiencia: " + ", ".join(exp) if exp else ""))
    return "\n".join(linhas)


def comandos():
    return sorted({m.group(1) for m in re.finditer(r"estado\.py (?:\[--file F\] )?([a-z][a-z-]+)", __doc__ or "")})


def uso(cmd):
    """Usage line of ONE command: after a traceback weak models ran --help over and over."""
    linhas = [l.strip() for l in (__doc__ or "").splitlines() if re.search(rf"estado\.py (?:\[--file F\] )?{re.escape(cmd)}\b", l)]
    return "\n".join(linhas) or f"comando desconhecido: {cmd}. Comandos: " + ", ".join(comandos())


def main(argv):
    path = os.environ.get("APLICADAS_FILE", DEFAULT)
    if len(argv) > 1 and argv[0] == "--file":
        path, argv = argv[1], argv[2:]
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd in ("dado", "resumo-candidato"):   # read-only, candidate data (not the state file)
        dados = json.load(open(arquivo_dados(), encoding="utf-8"))
        if cmd == "resumo-candidato":
            print(resumo_candidato(dados))
            return 0
        v = campo_dados(dados, args[0]) if args else None
        if v is None:
            print(f"campo inexistente: {args[0] if args else '(faltou CAMPO)'}; campos: {', '.join(k for k in dados if not k.startswith('_'))}")
            return 1
        print(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1))
        return 0
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
        # a free-text status ("enviada - pendente validacao...") breaks every report and follow-up
        if rec.get("status") is not None and rec.get("status") not in STATUS_OK:
            print(f"erro: status '{str(rec.get('status'))[:40]}' desconhecido (use {', '.join(sorted(STATUS_OK))}; detalhe vai em 'obs'); NADA gravado")
            return 2
        rec.setdefault("status", "enviada")   # without it the funnel/monitor miscount the application
        medir_ats(rec)
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
        # Models copy the placeholders ("descartes NIVEL MODELO STACK") or write "nivel 1 modelo 2 stack 3": labels
        # are accepted; anything that is not a number gets the usage line instead of a ValueError traceback.
        nums = [x.split("=", 1)[-1] for x in args
                if x.lower().strip("=:") not in ("nivel", "modelo", "stack", "level", "model")]
        if not nums or len(nums) > 3 or not all(x.isdigit() for x in nums):
            print("erro: use numeros: descartes N_NIVEL N_MODELO N_STACK (ex.: descartes 3 1 2); nada gravado")
            return 2
        dl = d.setdefault("descartes_listagem", {})
        for name, n in zip(("nivel", "modelo", "stack"), nums):
            dl[name] = int(dl.get(name, 0)) + int(n)
        dl["total"] = sum(int(dl.get(x, 0)) for x in ("nivel", "modelo", "stack"))
    elif cmd == "status":
        # status CHAVE STATUS [FOLLOWUP_MSG] [EMAIL_DATA] — used by the weekly follow-up and gmail-status.py.
        # EMAIL_DATA (YYYY-MM-DD) = date of the e-mail that caused the change, shown by the monitor.
        k, st = args[0], args[1]
        if st not in STATUS_OK:
            print(f"erro: status '{st}' desconhecido; use um de: {', '.join(sorted(STATUS_OK))}")
            return 2
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
    elif cmd == "del-aplicada":
        # archived, not deleted: aplicadas_removidas keeps the record + why, so it can be restored by hand
        k, motivo = args[0], args[1]
        rec = next((a for a in d.get("aplicadas", []) if a.get("chave") == k), None)
        if rec is None:
            print(f"nao existe em aplicadas: {k}")
            return 1
        d["aplicadas"] = [a for a in d["aplicadas"] if a.get("chave") != k]
        d.setdefault("aplicadas_removidas", []).append(
            dict(rec, removida_em=datetime.now().astimezone().isoformat(timespec="seconds"), motivo_remocao=motivo[:200]))
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
        print(f"comando desconhecido: {cmd}. Comandos: " + ", ".join(comandos()))
        return 2
    save(path, d)
    print(f"ok {cmd}")
    return 0


LEITURA = {"resumo", "get", "tem", "ja-visto", "dado", "resumo-candidato"}


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
    try:
        sys.exit(main_travado(sys.argv[1:]))
    except IndexError:   # missing argument: show only this command's usage, not a traceback
        _a = sys.argv[3:] if sys.argv[1:2] == ["--file"] else sys.argv[1:]
        print("erro: faltou argumento. Uso:\n" + uso(_a[0] if _a else ""))
        sys.exit(2)
