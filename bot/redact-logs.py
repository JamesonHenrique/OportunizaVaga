#!/usr/bin/env python3
"""Masks secrets in the bot's logs. One sweeper for every script instead of a filter per script:
round logs are written live by opencode and read live by the loop watchdog, so they are cleaned
after the fact. Idempotent; rewrites a file only if something changed. Portable (Linux/Windows).

  redact-logs.py                    sweep the default log locations (cron / Task Scheduler, every ~10 min)
  redact-logs.py FILE...            sweep only these files (still skips files written < 30 min ago)
  redact-logs.py --forcar FILE...   clean now; the caller guarantees the file is closed
                                    (bot/loop.sh and bot/loop.ps1 do this right after each round)

Masks: every password stored in the credentials file (literal match, read here, never printed),
the value of password-like fields in tool calls (fill_form/type), `printf ... >> credenciais.tsv`
last argument, API/bot tokens, CPF and 6-digit verification codes. Handles .gz. Prints only counts.

Config (environment):
  OV_CREDENTIALS_FILE   credentials file (same as bot/nova-senha.mjs; default ~/.config/oportunizavaga/credenciais.tsv)
  OV_REDACT_GLOBS       log globs to sweep, separated by os.pathsep (":" on Linux, ";" on Windows);
                        default: bot/logs/*.log(.gz), bot/*.log, bot/loop.log.*
"""
import glob
import gzip
import os
import re
import sys
import time

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
CRED = os.environ.get("OV_CREDENTIALS_FILE") or os.path.join(os.path.expanduser("~"), ".config", "oportunizavaga", "credenciais.tsv")
ALVOS_PADRAO = [
    os.path.join(BOT_DIR, "logs", "*.log"), os.path.join(BOT_DIR, "logs", "*.log.gz"),
    os.path.join(BOT_DIR, "*.log"), os.path.join(BOT_DIR, "loop.log.*"),
]
M = "[REDACTED]"

# A JSON-ish object (one tool call field) that talks about a password: mask its "value"/"text".
RE_CAMPO_SENHA = re.compile(r'\{[^{}]*?(?:senha|password|passwd|pwd)[^{}]*?\}', re.I)
RE_VALOR = re.compile(r'("(?:value|text)"\s*:\s*")((?:[^"\\]|\\.)*)(")')
PADROES = [
    # "senha": "x" / password=x in any command or JSON
    (re.compile(r'((?:"|\b)(?:senha|password|passwd|pwd|secret|token)"?\s*[:=]\s*"?)([^"\s,}]{6,})', re.I), r"\1" + M),
    # printf "<site>" "<email>" "<password>" >> credenciais.tsv  (password not in the file yet):
    # the LAST quoted arg right before ">> ...credenciais"
    (re.compile(r'(printf\b[^\n]*")([^"\n]+)("\s*>>\s*\S*credenciais)'), r"\1" + M + r"\3"),
    (re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{30,}\b'), M),                      # Telegram bot token
    (re.compile(r'\b(?:sk-or-v1-|sk-ant-|sk-|gsk_|ghp_|github_pat_|AIza)[A-Za-z0-9_-]{20,}'), M),  # API keys
    (re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'), M),                         # CPF
    (re.compile(r'((?:c[oó]digo|code|verifica[cç][aã]o)[^0-9\n]{0,40})\b\d{6}\b', re.I), r"\1" + M),  # 6-digit codes
]
ATIVO_MIN = 30   # never touch a log written in the last 30 min: a live round still holds it open


def senhas_conhecidas():
    try:
        with open(CRED, encoding="utf-8") as f:
            return sorted({c[2].strip() for c in (ln.split("\t") for ln in f) if len(c) >= 3 and len(c[2].strip()) >= 6},
                          key=len, reverse=True)
    except OSError:
        return []


def limpar(texto, senhas):
    for s in senhas:
        texto = texto.replace(s, M)
    texto = RE_CAMPO_SENHA.sub(lambda m: RE_VALOR.sub(lambda v: v.group(1) + M + v.group(3), m.group(0)), texto)
    for rx, rep in PADROES:
        texto = rx.sub(rep, texto)
    return texto


def varrer(caminho, senhas, forcar=False):
    # os.replace gives the path a NEW inode; a writer that still has the old one open (opencode
    # during a round) would keep writing to a deleted file while the loop watches the path.
    # Only settled files are rewritten.
    try:
        if not forcar and time.time() - os.path.getmtime(caminho) < ATIVO_MIN * 60:
            return False
    except OSError:
        return False
    abrir = gzip.open if caminho.endswith(".gz") else open
    try:
        with abrir(caminho, "rt", encoding="utf-8", errors="surrogateescape") as f:
            antes = f.read()
    except (OSError, EOFError):
        return False
    depois = limpar(antes, senhas)
    if depois == antes:
        return False
    tmp = caminho + ".redact.tmp"
    try:
        with abrir(tmp, "wt", encoding="utf-8", errors="surrogateescape") as f:
            f.write(depois)
        os.chmod(tmp, os.stat(caminho).st_mode & 0o777)
        os.replace(tmp, caminho)   # Windows: PermissionError if another process still has it open
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False
    return True


def alvos():
    env = os.environ.get("OV_REDACT_GLOBS")
    globs = [g for g in env.split(os.pathsep) if g.strip()] if env else ALVOS_PADRAO
    return sorted({p for g in globs for p in glob.glob(os.path.expanduser(g)) if not p.endswith(".redact.tmp")})


def main(args):
    # --forcar FILE...: the caller guarantees the file is CLOSED (loop right after a round).
    forcar = bool(args) and args[0] == "--forcar"
    args = args[1:] if forcar else args
    senhas = senhas_conhecidas()
    arquivos = args or alvos()
    mudados = [p for p in arquivos if varrer(p, senhas, forcar)]
    if mudados or args:
        print(f"redact-logs: {len(arquivos)} arquivos lidos, {len(mudados)} limpos"
              + (": " + ", ".join(os.path.basename(p) for p in mudados) if mudados else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
