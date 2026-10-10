#!/usr/bin/env python3
"""Reads recruiter replies from Gmail (robot's Chrome, deterministic, no LLM) and records the
status of each application. The LLM follow-up often cannot read e-mail at all
("sem_retorno_verificavel"), so applications would stay "enviada" forever.

  gmail-status.py          search Gmail, match rows to applied companies, write status via estado.py
  gmail-status.py --dry    same, but only print what it would record

Only moves status forward (enviada/em_analise -> entrevista/encerrada), never back, and never
overwrites a status set by hand. Saves only the matches (company, class, subject excerpt) in
state/gmail_status.json — never the mailbox content.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta

BOT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_DIR = os.path.join(BOT_ROOT, "bot")
NODE = os.environ.get("NODE_BIN") or shutil.which("node") or "node"
CHROME_LOCK = os.environ.get("CHROME_LOCK_SH") or os.path.join(BOT_DIR, "chrome-lock.sh")   # single owner of the Chrome lock protocol
ESTADO = os.environ.get("OV_ESTADO_PY") or os.path.join(BOT_DIR, "estado.py")
DADOS = os.environ.get("DADOS_FILE", os.path.join(BOT_DIR, "dados_candidato.json"))
APLICADAS = os.environ.get("APLICADAS_FILE", os.path.join(BOT_DIR, "aplicadas.json"))
SAIDA = os.environ.get("OV_GMAIL_STATUS") or os.path.join(BOT_DIR, "state", "gmail_status.json")
NOTIFICAR = os.environ.get("OV_NOTIFY") or os.path.join(BOT_ROOT, "scripts", "notificar.ps1" if os.name == "nt" else "notificar.sh")
QUERY = ("newer_than:30d (candidatura OR candidato OR \"processo seletivo\" OR vaga OR entrevista "
         "OR gupy OR inhire OR recrutamento OR selecao)")

# Order matters: first match wins (a rejection e-mail often also says "candidatura").
CLASSES = [
    ("encerrada", re.compile(r"infelizmente|n[aã]o (seguiremos|seguir|avan[cç]ar)|outros? candidat|n[aã]o foi selecionad|"
                             r"optamos por|decidimos (seguir|prosseguir)|vaga (foi )?(encerrada|preenchida)|"
                             r"n[aã]o (poderemos|vamos) (dar )?continuidade|reprovad|perfil (n[aã]o )?(est[aá] )?alinhad")),
    # Tests (Gupy "etapa de testes" = Fit Cultural etc.) are NOT interviews: checked before "entrevista".
    ("etapa_teste", re.compile(r"etapa de testes?|fit cultural|teste (online|t[eé]cnico|de perfil|comportamental|l[oó]gico)|"
                               r"desafio t[eé]cnico|case t[eé]cnico|avalia[cç][aã]o (online|comportamental|t[eé]cnica)")),
    # "entrevista" only when the e-mail really talks about an interview / scheduling one.
    ("entrevista", re.compile(r"entrevista|agendar|agendamento|bate[- ]papo|conversa com")),
    # Vague progress ("próxima etapa", "parabéns"): real signal, but no interview named.
    ("proxima_etapa", re.compile(r"pr[oó]xima etapa|avan[cç]ou|parab[eé]ns|selecionad[oa] para")),
    ("em_analise", re.compile(r"recebemos (a |sua )?candidatura|candidatura (foi )?(recebida|realizada|enviada|confirmada)|"
                              r"obrigad[oa] por (se candidatar|sua candidatura|participar)|inscri[cç][aã]o (recebida|confirmada)")),
]
# The monotonic order comes from the WRITER, not from a copy kept here. 04/10 (cap 121 A1/F2): this
# dict and gupy-status.py each carried one while estado.py status accepted any value, so the fossil
# "entrevista -> etapa_teste" got written and nothing complained. The writer refuses the downgrade now;
# importing the table here just avoids spawning a subprocess per application. None disables the
# early-out and says so out loud. That matters: the empty dict this replaced was the opposite of what
# its comment claimed -- with {}, ORDEM.get(x, 0) <= ORDEM.get(y, 0) is 0 <= 0 for EVERY pair, so every
# match hit `continue` and this script silently stopped advancing any status at all.
try:
    _st = importlib.util.spec_from_file_location("estado_ordem", ESTADO)
    _est = importlib.util.module_from_spec(_st)
    _st.loader.exec_module(_est)
    ORDEM = _est.ORDEM
except Exception as _e2:
    ORDEM = None
    print(f"gmail-status: estado.py nao importavel ({_e2.__class__.__name__}); sem early-out, "
          "a monotonicidade fica so no escritor", file=sys.stderr)
sys.path.insert(0, BOT_DIR)
import meses   # single owner of the month tables; 04/10 (cap 121 C3/F3)
MESES, MESES_EN = meses.PT, meses.EN


def data_email(texto_n, hoje=None):
    """Date shown in a Gmail list row: '11:29' (today), '17 de set.', 'Sep 17' or '17/09/2026'."""
    hoje = hoje or datetime.now().date()
    if m := re.search(r"\b(\d{1,2}) (\d{1,2}) (\d{4})\b", texto_n):   # 17/09/2026 after norm()
        d, mo, y = map(int, m.groups())
    elif m := re.search(r"\b(\d{1,2}) de (%s)\b" % "|".join(MESES), texto_n):
        d, mo, y = int(m.group(1)), MESES[m.group(2)], hoje.year
    elif m := re.search(r"\b(%s) (\d{1,2})\b" % "|".join(MESES_EN), texto_n):
        d, mo, y = int(m.group(2)), MESES_EN[m.group(1)], hoje.year
    elif re.search(r"\b\d{1,2} \d{2}\b", texto_n):                  # 11:29 -> today
        return hoje.isoformat()
    else:
        return None
    try:
        dt = datetime(y, mo, d).date()
    except ValueError:
        return None
    if hoje < dt <= hoje + timedelta(days=60):  # a near-future date is an event in the subject
        return None                              # ("Entrevista @ Thu Oct 1"), not the mail date
    if dt > hoje:  # "17 de dez." seen in January = last year
        dt = dt.replace(year=dt.year - 1)
    return dt.isoformat()
GENERICAS = {"carreiras", "grupo", "brasil", "tecnologia", "solucoes", "sistemas", "digital", "software",
             "consultoria", "servicos", "group", "tech", "oficial", "via", "jobs"}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in t if not unicodedata.combining(c)))


def chave_empresa(empresa):
    ws = [w for w in norm(empresa).split() if len(w) >= 3 and w not in GENERICAS]
    return ws[0] if ws else None


def contas():
    """Contact inbox (recruiter replies) and login inbox (platform notices), deduplicated."""
    c = json.load(open(DADOS, encoding="utf-8"))
    return list(dict.fromkeys(e for e in (c.get("email"), c.get("email_contas")) if e))


def extrair_conta(conta):
    # The Chrome lock has ONE owner: bot/chrome-lock.sh. 04/10: this used to be a 57-line Python
    # reimplementation (class browser_lock) living inside this file. Two copies of one protocol is
    # how loop.sh ended up with its own copy of quota detection on 30/09 -- a fix to the .sh never
    # reaches the .py, and nobody remembers the .py exists. So this shells out to the same script the
    # loop uses, with PRIO=alta: while waiting or holding, the flag agent-chrome-9222.prio.gmail makes
    # the loop yield its next round instead of making this short job wait behind it.
    cmd = [CHROME_LOCK, "gmail", "alta", "1500", "--", NODE,
           os.path.join(BOT_DIR, "gmail-extrair.mjs"), QUERY, conta]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "erro": str(e)[:300], "linhas": []}
    if r.returncode == 75:      # chrome-lock.sh: waited past WAIT and never got the lock
        return {"ok": False, "erro": "Chrome ocupado por mais de 1500s (rc 75)", "linhas": []}
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "erro": (r.stderr or r.stdout or "sem saida")[-300:], "linhas": []}


def extrair():
    """Merges every inbox; fails only if none could be read (errors per inbox still printed)."""
    linhas, erros = [], []
    for conta in contas():
        res = extrair_conta(conta)
        if res.get("ok"):
            linhas += res.get("linhas", [])
            # 06/10 (audit G1): Gmail lists 50 threads per page and only page 1 is read. Newest first, twice a day
            # and status only goes up, so a fresh reply is never past it — unless the reader was down for days.
            if len(res.get("linhas", [])) >= 50:
                print(f"gmail-status: aviso {conta}: pagina cheia (50) — e-mails mais antigos da busca nao foram lidos")
        else:
            erros.append(f"{conta}: {res.get('erro')}")
    for e in erros:
        print(f"gmail-status: aviso {e}")
    # The LOGIN inbox (codes, verification links) must be logged in; the contact inbox is optional.
    _c = json.load(open(DADOS, encoding="utf-8"))
    login = _c.get("email_contas") or _c.get("email")
    if any(e.startswith(f"{login}:") and ("nao logada" in e or "deslogado" in e) for e in erros):
        notificar(f"🔒 Gmail {login} deslogado no Chrome do robo — codigos e respostas param de chegar")
    if len(erros) == len(contas()):
        return {"ok": False, "erro": "; ".join(erros), "linhas": []}
    return {"ok": True, "linhas": list(dict.fromkeys(linhas))}


def notificar(msg):
    """Per-class Telegram notice via scripts/notificar.{sh,ps1} (silent without TELEGRAM_* env)."""
    if not os.path.exists(NOTIFICAR):
        return
    cmd = (["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", NOTIFICAR, msg]
           if os.name == "nt" else ["bash", NOTIFICAR, msg])
    subprocess.run(cmd, check=False, capture_output=True)


def main(dry):
    d = json.load(open(APLICADAS, encoding="utf-8"))
    res = extrair()
    if not res.get("ok"):
        print(f"gmail-status: falhou ({res.get('erro')})")
        return 1
    linhas = [norm(x) for x in res.get("linhas", [])]
    achados = []
    for a in d.get("aplicadas", []):
        k = chave_empresa(a.get("empresa"))
        if not k:
            continue
        # Gmail lists newest first: the first matching row is the latest word from that company.
        for texto_n, texto in zip(linhas, res["linhas"]):
            if re.search(rf"\b{re.escape(k)}\b", texto_n):
                cls = next((c for c, rx in CLASSES if rx.search(texto_n)), None)
                quando = data_email(texto_n)
                # 02/10: a mail dated before this application was sent is about an older process (or a
                # misread date: 30/09 stored 2025-10-01). Never moves this record.
                if cls and quando and quando < str(a.get("enviada_em") or a.get("data") or "")[:10]:
                    cls = None
                if cls:
                    # 04/10 (cap 121 E3): the 140-char budget was set here for the monitor benefit and PAID FOR
                    # by kit-entrevista.py, whose data_evento() reads the calendar date out of the
                    # subject. A real Outlook subject is ~220 chars and the date sits past 168, so
                    # with 140 the invite date was never found, evento_em stayed 0 in every record
                    # and the HOJE reminder could never fire. This file writes a FIELD another
                    # program parses: a budget chosen for one reader is a bug for the other. 320
                    # holds the subject and still bounds the file (5 achados x 320 = 1.6 KB).
                    achados.append({"chave": a.get("chave"), "empresa": a.get("empresa"), "classe": cls,
                                    "trecho": texto[:320], "email_data": quando})
                break
    mudou = []
    for f in achados:
        rec = next(a for a in d["aplicadas"] if a.get("chave") == f["chave"])
        atual = rec.get("status") or "enviada"
        if rec.get("status_manual") or ORDEM.get(f["classe"], 0) <= ORDEM.get(atual, 0):
            continue
        mudou.append(f)
        if not dry:
            subprocess.run([sys.executable, ESTADO, "--file", APLICADAS, "status",
                            f["chave"], f["classe"], "", f.get("email_data") or ""], check=False)
            quando = f" (e-mail de {f['email_data'][8:]}/{f['email_data'][5:7]})" if f.get("email_data") else ""
            aviso = {"entrevista": f"🎉 {f['empresa']}: e-mail fala em ENTREVISTA{quando} — confira o Gmail",
                     "etapa_teste": f"📝 {f['empresa']}: você passou para a etapa de TESTES{quando} — faça o teste na plataforma",
                     "proxima_etapa": f"👀 {f['empresa']}: e-mail de próxima etapa{quando} — confira o Gmail"}.get(f["classe"])
            if aviso:
                notificar(aviso)
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    json.dump({"atualizado": datetime.now().astimezone().isoformat(timespec="seconds"), "linhas_lidas": len(linhas),
               "achados": achados, "mudancas": [f["chave"] for f in mudou]},
              open(SAIDA + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(SAIDA + ".tmp", SAIDA)
    print(f"gmail-status: {len(linhas)} e-mails lidos, {len(achados)} de empresas aplicadas, "
          f"{len(mudou)} status {'a mudar (dry)' if dry else 'atualizados'}: "
          + ", ".join(f"{f['empresa']}={f['classe']}" for f in mudou))
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry" in sys.argv))
