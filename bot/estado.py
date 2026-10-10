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
  estado.py [--file F] intencao CHAVE JSON        BEFORE the final submit click: envios_pendentes[CHAVE] (empresa, vaga, url);
                                                  exit 1 = already applied or unknown result from an earlier round: do NOT submit
  estado.py [--file F] cancelar-intencao CHAVE MOTIVO  the pending send verifiably did NOT go out (form error, no confirmation)
  estado.py [--file F] add-bloqueado CHAVE JSON   set bloqueados[CHAVE] (JSON object or plain motivo)
  estado.py [--file F] set-quase-la CHAVE JSON    set quase_la[CHAVE]; JSON=null removes it
  estado.py [--file F] descartes N N N               increments descartes_listagem (nivel modelo stack), e.g. 3 1 2
  estado.py [--file F] status CHAVE ST [MSG] [EMAIL_DATA]   follow-up: em_analise/entrevista/encerrada/sem_resposta/sem_retorno_verificavel
  estado.py [--file F] conta SITE JSON            set contas_criadas[SITE]
  estado.py [--file F] rodizio-avancar            rodizio.proximo -> next in ordem; ultima_rodada=today
  estado.py [--file F] set-campo CHAVE CAMPO VALOR  fix/add one field of an aplicada (VALOR: JSON or text)
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


def vencidos(d, hoje=None):
    """[(chave, rec)] of bloqueados with a due "retentar" (02/10). The prompt used to make the model walk all ~200
    bloqueados every round looking for text patterns; 13 matched and every round re-rejected all 13. Only an
    explicit retentar (date <= today, or no date) brings a block back now.

    Ported 04/10 (cap 121 H2) so prompt_cond.py can evaluate <!--se:vencidos--> from the public writer too. It lived
    only in the private copy, so the public block condition had no way to ask the question at all."""
    hoje = hoje or datetime.now().strftime("%Y-%m-%d")
    out = []
    for k, rec in (d.get("bloqueados") or {}).items():
        r = rec.get("retentar") if isinstance(rec, dict) else None
        if r and not (re.match(r"\d{4}-\d\d-\d\d", str(r)) and str(r)[:10] > hoje):
            out.append((k, rec))
    return out


EVENTOS_MAX = 2 * 1024 * 1024   # bytes; one rotated generation (eventos.jsonl.1) is kept


def registrar_evento(path, ev):
    """Append one structured line to eventos.jsonl next to the state file (10/10).
    Who changed what, when, in which round/cascade attempt: the history used to live only in free-text logs
    (loop.log, 20 round logs) that rotate away. Keys and statuses only -- no free text, no candidate data.
    Best effort: a failure here never undoes the state write that already happened."""
    arq = os.path.join(os.path.dirname(os.path.abspath(path)), "eventos.jsonl")
    ev = {"em": _agora(), "rodada": os.environ.get("OV_RODADA") or None,
          "tentativa": os.environ.get("OV_TENTATIVA") or None, **ev}
    try:
        if os.path.exists(arq) and os.path.getsize(arq) > EVENTOS_MAX:
            os.replace(arq, arq + ".1")
        with open(arq, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: v for k, v in ev.items() if v is not None}, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"aviso: evento nao registrado ({e})", file=sys.stderr)


def _agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def pendentes(d):
    """envios_pendentes as a dict (absent or malformed in old state files = none)."""
    p = d.get("envios_pendentes")
    return p if isinstance(p, dict) else {}


def resumo(d):
    out = []
    # 10/10: a send whose result is unknown (process died between the submit click and add-aplicada).
    # Listed first: re-sending it blindly is the duplicate application this record exists to prevent.
    pend = pendentes(d)
    if pend:
        out.append(f"ENVIOS COM RESULTADO DESCONHECIDO ({len(pend)}) — NAO reenvie: verifique no portal/e-mail se a "
                   "candidatura saiu; saiu = add-aplicada, nao saiu = cancelar-intencao CHAVE MOTIVO:")
        for k, v in pend.items():
            v = v if isinstance(v, dict) else {}
            out.append(f"  {k} | {v.get('empresa', '?')} | {v.get('vaga', '?')} | {v.get('url', '-')} | desde {v.get('em', '?')}")
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
    for sec in ("envios_pendentes", "aplicadas", "quase_la", "bloqueados", "bloqueados_arquivados"):
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
    achados.sort(key=lambda x: (x[1] != "envios_pendentes", -x[0]))   # unknown-result sends always first
    linhas = []
    for score, sec, k, rec in achados[:6]:
        tag = "MESMA VAGA provavel" if tt and score >= 0.5 else "mesma empresa"
        if sec == "envios_pendentes":
            tag = "ENVIO COM RESULTADO DESCONHECIDO (NAO reenvie; verifique)"
        linhas.append(f"{tag} | {sec} | {k} | {str(rec.get('vaga') or '')[:50]} | {short(rec)[:90]}")
    return linhas


STATUS_OK = {"enviada", "em_analise", "etapa_teste", "proxima_etapa", "entrevista", "encerrada",
             "respondida", "sem_resposta", "sem_retorno_verificavel", "followup"}

# Status levels, in the WRITER. 04/10 (cap 121 A1/F2): gmail-status.py and gupy-status.py each carried
# their own copy of this ranking, and `status` accepted any value in STATUS_OK, so the fossil
# `construmarket-dev-jr-gupy-12212597` really did go entrevista -> etapa_teste. Two copies drift; one copy
# next to the data cannot. "respondida" is an alias of "em_analise" (rank 1): a reply means the process
# started, never that it ended.
ORDEM = {"enviada": 0, "sem_resposta": 0, "sem_retorno_verificavel": 0, "em_analise": 1, "respondida": 1,
         "proxima_etapa": 2, "etapa_teste": 2, "entrevista": 3, "followup": 3, "encerrada": 4}

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
    forcar = False
    while argv and argv[0].startswith("--"):
        if argv[0] == "--forcar":
            forcar = True
        argv = argv[1:]
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    ev = {"cmd": cmd}   # filled by the write commands below; appended to eventos.jsonl after the save
    # A refusal message that teaches a flag nobody can type is a trap: the flag is accepted in any
    # position, including after the record and the status, because that is where a reader puts it.
    if "--forcar" in args:
        forcar = True
        args = [a for a in args if a != "--forcar"]
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
        for sec in ("aplicadas", "envios_pendentes", "bloqueados", "quase_la", "bloqueados_arquivados"):
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
        ev.update(chave=rec["chave"], para=rec["status"])
        if os.environ.get("OV_RODADA") and not rec.get("rodada"):
            rec["rodada"] = os.environ["OV_RODADA"]   # which loop round wrote it (logs/rodada-<id>.log)
        medir_ats(rec)
        d["aplicadas"].append(rec)
        intencao = pendentes(d).pop(rec["chave"], None)   # the unknown result is now a confirmed send
        if intencao is not None and not d["envios_pendentes"]:
            d.pop("envios_pendentes")
        (d.get("bloqueados") or {}).pop(rec["chave"], None)
        if isinstance(d.get("quase_la"), dict):
            d["quase_la"].pop(rec["chave"], None)
    elif cmd == "intencao":
        # 10/10: written right BEFORE the final submit click. If the process dies between the click and
        # add-aplicada, this record survives and the next round (any model of the cascade) sees an unknown
        # result instead of a fresh job -- the gap that turned a killed round into a duplicate application.
        k = args[0]
        info = parse(args[1]) if len(args) > 1 else {}
        info = info if isinstance(info, dict) else {"vaga": str(info)}
        if any(a.get("chave") == k for a in d.get("aplicadas", [])):
            print(f"ja existe em aplicadas: {k} -- NAO envie de novo")
            return 1
        rodada = os.environ.get("OV_RODADA") or ""
        # owner = the cascade attempt (loop.sh OV_TENTATIVA): the next model of the same round must not
        # inherit a killed attempt's click. Without the loop (manual runs) the owner is empty = always "other".
        dono = os.environ.get("OV_TENTATIVA") or rodada
        atual = pendentes(d).get(k)
        if isinstance(atual, dict) and (not dono or atual.get("tentativa", atual.get("rodada")) != dono):
            print(f"resultado desconhecido desde {atual.get('em')} (rodada {atual.get('rodada') or '?'}): {k} -- NAO "
                  "envie; verifique no portal/e-mail. Saiu = add-aplicada; nao saiu = cancelar-intencao CHAVE MOTIVO")
            return 1
        ev["chave"] = k
        if atual is None:   # same round calling again (retry of the click) keeps the first timestamp
            rec = {c: str(info[c])[:300] for c in ("empresa", "vaga", "url", "como") if info.get(c)}
            rec.update(em=_agora(), rodada=rodada, tentativa=dono)
            d.setdefault("envios_pendentes", {})[k] = rec
    elif cmd == "cancelar-intencao":
        k, motivo = args[0], args[1]
        rec = pendentes(d).pop(k, None)
        if rec is None:
            print(f"nao existe em envios_pendentes: {k}")
            return 1
        ev["chave"] = k
        if not d["envios_pendentes"]:
            d.pop("envios_pendentes")
        # kept (bounded) so a wrong cancel can be traced; never counted as an application
        hist = d.setdefault("envios_cancelados", [])
        hist.append(dict(rec, chave=k, cancelada_em=_agora(), motivo=motivo[:200]))
        del hist[:-100]
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
        # Monotonicity, in the writer (see ORDEM). Callers still check first -- this is the backstop for
        # the next caller, which is exactly the one that caused the fossil. status_manual is the per-record
        # override; --forcar is the per-call one.
        atual = rec.get("status") or "enviada"
        if (not forcar and not rec.get("status_manual")
                and ORDEM.get(st, 0) < ORDEM.get(atual, 0)):
            print(f"status nao regragiu: {k} esta em '{atual}' (nivel {ORDEM.get(atual, 0)}) e "
                  f"'{st}' e nivel {ORDEM.get(st, 0)} -- recuo nao gravado. "
                  f"use --forcar se a empresa reabriu o processo, ou marque status_manual.")
            return 3
        ev.update(chave=k, de=rec.get("status") or "enviada", para=st)
        if rec.get("status") != st:
            h = {"de": rec.get("status"), "para": st, "em": datetime.now().astimezone().isoformat(timespec="seconds")}
            if len(args) > 3 and args[3]:
                h["email_data"], h["fonte"] = args[3][:10], "gmail"
            rec.setdefault("historico_status", []).append(h)
        rec["status"] = st
        rec["followup_em"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if len(args) > 2 and args[2]:
            rec["followup_msg"] = args[2][:400]
    elif cmd == "set-campo":
        k, campo, val = args[0], args[1], parse(args[2])
        rec = next((a for a in d.get("aplicadas", []) if a.get("chave") == k), None)
        if rec is None:
            print(f"nao existe em aplicadas: {k}")
            return 1
        ev.update(chave=k, campo=campo)
        if campo == "status":   # set-campo bypasses the status rules: leave a trace of it
            ev.update(de=rec.get("status"), para=val if isinstance(val, str) else None)
        rec[campo] = val
    elif cmd == "del-aplicada":
        # archived, not deleted: aplicadas_removidas keeps the record + why, so it can be restored by hand
        k, motivo = args[0], args[1]
        rec = next((a for a in d.get("aplicadas", []) if a.get("chave") == k), None)
        if rec is None:
            print(f"nao existe em aplicadas: {k}")
            return 1
        ev["chave"] = k
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
    if cmd in ("add-bloqueado", "set-quase-la", "conta"):
        ev["chave"] = args[0]
    save(path, d)
    registrar_evento(path, ev)
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
