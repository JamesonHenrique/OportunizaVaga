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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import datetime

BOT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_DIR = os.path.join(BOT_ROOT, "bot")
NODE = os.environ.get("NODE_BIN") or shutil.which("node") or "node"
LOCK = os.environ.get("CHROME_LOCK_FILE") or os.path.join(tempfile.gettempdir(), "agent-chrome-9222.lock")   # same file loop.sh/loop.ps1 lock
FLAG_DIR = os.environ.get("CHROME_LOCK_DIR") or tempfile.gettempdir()   # priority flags (bot/chrome-lock.sh protocol)
DADOS = os.environ.get("DADOS_FILE", os.path.join(BOT_DIR, "dados_candidato.json"))
APLICADAS = os.environ.get("APLICADAS_FILE", os.path.join(BOT_DIR, "aplicadas.json"))
SAIDA = os.path.join(BOT_DIR, "state", "gmail_status.json")
NOTIFICAR = os.path.join(BOT_ROOT, "scripts", "notificar.ps1" if os.name == "nt" else "notificar.sh")
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
ORDEM = {"enviada": 0, "sem_resposta": 0, "sem_retorno_verificavel": 0, "em_analise": 1, "proxima_etapa": 2,
         "etapa_teste": 2, "entrevista": 3, "encerrada": 4}
MESES = {m: i for i, m in enumerate(("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"), 1)}
MESES_EN = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


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


class browser_lock:
    """Portable exclusive lock on the shared Chrome lock file (flock on POSIX, msvcrt on Windows).
    Waits up to `wait` seconds; `acquired` tells whether it got the lock.

    Same protocol as bot/chrome-lock.sh with PRIO=alta: while waiting/holding, the flag file
    agent-chrome-9222.prio.NAME makes the application loop yield its next round instead of
    making this short job wait behind it. A flag that already existed is the parent's: kept."""

    def __init__(self, wait=900, name="gmail"):
        self.wait, self.fh, self.acquired = wait, None, False
        self.flag, self.flag_criada = os.path.join(FLAG_DIR, f"agent-chrome-9222.prio.{name}"), False

    def _try(self):
        if os.name == "nt":
            import msvcrt
            self.fh.seek(0)
            msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __enter__(self):
        try:
            self.flag_criada = not os.path.exists(self.flag)
            with open(self.flag, "a"):
                os.utime(self.flag, None)
        except OSError:
            self.flag_criada = False
        deadline = time.time() + self.wait
        while True:
            try:
                if self.fh is None:
                    self.fh = open(LOCK, "a+")
                self._try()
                self.acquired = True
                return self
            except OSError:   # busy (BlockingIOError / PermissionError on Windows)
                if time.time() >= deadline:
                    return self
                time.sleep(2)

    def __exit__(self, *exc):
        if self.flag_criada:
            try:
                os.unlink(self.flag)
            except OSError:
                pass
        if self.fh:
            try:
                if self.acquired and os.name == "nt":
                    import msvcrt
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.fh.close()


def extrair_conta(conta):
    with browser_lock() as lk:
        if not lk.acquired:
            return {"ok": False, "erro": "Chrome ocupado (lock)", "linhas": []}
        try:
            r = subprocess.run([NODE, os.path.join(BOT_DIR, "gmail-extrair.mjs"), QUERY, conta],
                               capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"ok": False, "erro": str(e)[:300], "linhas": []}
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
        else:
            erros.append(f"{conta}: {res.get('erro')}")
    for e in erros:
        print(f"gmail-status: aviso {e}")
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
                if cls:
                    achados.append({"chave": a.get("chave"), "empresa": a.get("empresa"), "classe": cls,
                                    "trecho": texto[:140], "email_data": data_email(texto_n)})
                break
    mudou = []
    for f in achados:
        rec = next(a for a in d["aplicadas"] if a.get("chave") == f["chave"])
        atual = rec.get("status") or "enviada"
        if rec.get("status_manual") or ORDEM.get(f["classe"], 0) <= ORDEM.get(atual, 0):
            continue
        mudou.append(f)
        if not dry:
            subprocess.run([sys.executable, os.path.join(BOT_DIR, "estado.py"), "--file", APLICADAS, "status",
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
