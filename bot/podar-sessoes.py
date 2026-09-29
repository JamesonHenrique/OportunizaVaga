#!/usr/bin/env python3
"""Deletes the BOT's old opencode sessions (opt-in; run it daily from cron / Task Scheduler).

The opencode database keeps every tool argument of every round - including anything typed into
forms - and redact-logs.py cannot reach it. Pruning old bot sessions limits how long that stays
around. Only official CLI calls (`opencode session list --format json` / `opencode session delete`),
never raw SQL.

  podar-sessoes.py [--dry] [DIAS]   default 3 days; --dry only prints what it would delete

Safety: a session is deleted only if its title starts with a bot prefix AND its directory is a
bot directory. Interactive sessions (yours) are never touched. Age uses `created` (opencode bumps
`updated` in bulk, so it would keep old sessions alive forever). Also chmods the opencode DB to 600
(POSIX only; least privilege - the DB holds secrets). Prints only counts.

Config (environment):
  OV_OPENCODE_BIN        opencode binary (default: opencode on PATH, else ~/.opencode/bin/opencode)
  OV_PODAR_PREFIXOS      title prefixes, comma separated (default: candidaturas-,followup-)
  OV_PODAR_PASTAS        extra bot directories, separated by os.pathsep (default: <repo> and <repo>/bot)
  OPENCODE_DB            path of the opencode database (default: ~/.local/share/opencode/opencode.db)
"""
import json
import os
import shutil
import subprocess
import sys
import time

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_ROOT = os.path.dirname(BOT_DIR)


def _norm(p):
    return os.path.normcase(os.path.realpath(os.path.expanduser(str(p))))


def opencode_bin():
    return (os.environ.get("OV_OPENCODE_BIN") or shutil.which("opencode")
            or os.path.join(os.path.expanduser("~"), ".opencode", "bin", "opencode"))


def prefixos():
    env = os.environ.get("OV_PODAR_PREFIXOS")
    return tuple(p.strip() for p in env.split(",") if p.strip()) if env else ("candidaturas-", "followup-")


def pastas():
    extra = [p for p in os.environ.get("OV_PODAR_PASTAS", "").split(os.pathsep) if p.strip()]
    return {_norm(p) for p in [BOT_ROOT, BOT_DIR] + extra}


def db_path():
    return os.environ.get("OPENCODE_DB") or os.path.join(os.path.expanduser("~"), ".local", "share", "opencode", "opencode.db")


def alvos(sessoes, dias, agora=None):
    corte = ((agora or time.time()) - dias * 86400) * 1000
    pre, dirs = prefixos(), pastas()
    return [s for s in sessoes
            if str(s.get("title", "")).startswith(pre)
            and _norm(s.get("directory", "")) in dirs
            and float(s.get("created") or 0) < corte]


def main(args):
    dry = "--dry" in args
    dias = next((int(a) for a in args if a.isdigit()), 3)
    oc = opencode_bin()
    try:
        r = subprocess.run([oc, "session", "list", "--format", "json", "-n", "100000"],
                           capture_output=True, text=True, timeout=300)
        sessoes = json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        print(f"podar-sessoes: lista ilegivel ({str(e)[-200:]})")
        return 1
    alvo = alvos(sessoes, dias)
    ok = 0
    if not dry:
        for s in alvo:
            try:
                if subprocess.run([oc, "session", "delete", str(s["id"])], capture_output=True, timeout=60).returncode == 0:
                    ok += 1
            except (OSError, subprocess.TimeoutExpired):
                pass
        db = db_path()
        for f in (db, db + "-wal", db + "-shm"):   # least privilege: the DB holds secrets
            try:
                os.chmod(f, 0o600)
            except OSError:
                pass
    print(f"podar-sessoes: {len(sessoes)} sessoes, {len(alvo)} do robo com >{dias}d"
          + (" (dry)" if dry else f", {ok} apagadas"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
