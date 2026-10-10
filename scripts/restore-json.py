#!/usr/bin/env python3
"""restore-json.py — verify and restore the backups written by scripts/backup-jsons.sh/.ps1.

  python3 scripts/restore-json.py --listar                 # backups found, newest first, with validity
  python3 scripts/restore-json.py --verificar              # validate every backup (exit 1 if any is bad)
  python3 scripts/restore-json.py BACKUP.json              # dry-run: what would be restored, and the diff in counts
  python3 scripts/restore-json.py BACKUP.json --aplicar    # restore it for real

Restoring never trusts the backup blindly: it must parse and have the expected shape
(aplicadas.json -> object with an "aplicadas" list; dados_candidato.json -> object).
Before replacing, the current file (if any) is copied to <backups>/<prefix>.pre-restore.<stamp>.json,
and the write goes through the same lock + atomic replace used by bot/estado.py, so a running
loop never sees a half-written file. Stop the loop first anyway: a round in flight keeps its
in-memory copy and may write it back after the restore.

Env: OV_BACKUP_DIR (default bot/backups), OV_STATE_ROOT (default bot) — same as backup-jsons.sh.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bot"))
from jsonlock import gravar, travado  # noqa: E402

BACKUPS = os.environ.get("OV_BACKUP_DIR") or os.path.join(ROOT, "bot", "backups")
STATE = os.environ.get("OV_STATE_ROOT") or os.path.join(ROOT, "bot")

# Backup name -> (kind, profile slug or None). Mirrors the prefixes used by backup-jsons.sh.
NOME = re.compile(r"^(?:(aplicadas|dados_candidato)|(aplicadas|dados)\.perfil-([^/\\]+?))\.(\d{8}-\d{4})\.json$")


def classificar(nome):
    m = NOME.match(nome)
    if not m:
        return None
    if m.group(1):
        tipo, slug = m.group(1), None
    else:
        tipo = "aplicadas" if m.group(2) == "aplicadas" else "dados_candidato"
        slug = m.group(3)
    return {"tipo": tipo, "perfil": slug, "carimbo": m.group(4)}


def destino(info):
    pasta = STATE if info["perfil"] is None else os.path.join(STATE, "state", info["perfil"])
    return os.path.join(pasta, info["tipo"] + ".json")


def validar(path, tipo):
    """Return (doc, None) when the file is usable for `tipo`, else (None, reason)."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as e:
        return None, f"ilegível: {e.__class__.__name__}: {e}"
    if not isinstance(doc, dict):
        return None, "não é um objeto JSON"
    if tipo == "aplicadas" and not isinstance(doc.get("aplicadas"), list):
        return None, 'sem a lista "aplicadas"'
    return doc, None


def resumo(doc, tipo):
    if doc is None:
        return "-"
    if tipo == "aplicadas":
        return f"{len(doc.get('aplicadas', []))} aplicadas, {len(doc.get('bloqueados') or {})} bloqueados"
    return f"{len(doc)} campos"


def backups():
    try:
        nomes = os.listdir(BACKUPS)
    except OSError:
        return []
    achados = [(n, classificar(n)) for n in nomes]
    achados = [(n, i) for n, i in achados if i]
    return sorted(achados, key=lambda x: x[1]["carimbo"], reverse=True)


def listar(so_verificar):
    lista = backups()
    if not lista:
        print(f"nenhum backup em {BACKUPS}")
        return 0 if so_verificar else 1
    ruins = 0
    for nome, info in lista:
        doc, erro = validar(os.path.join(BACKUPS, nome), info["tipo"])
        ruins += bool(erro)
        if so_verificar and not erro:
            continue
        estado = f"INVÁLIDO ({erro})" if erro else "ok"
        print(f"{nome}  {estado}  {resumo(doc, info['tipo'])}  -> {os.path.relpath(destino(info), ROOT)}")
    if so_verificar:
        print(f"{len(lista)} backups verificados, {ruins} inválidos")
    return 1 if ruins else 0


def restaurar(arquivo, aplicar):
    nome = os.path.basename(arquivo)
    info = classificar(nome)
    if not info:
        print(f"nome não reconhecido: {nome} (esperado <prefixo>.AAAAMMDD-HHMM.json)", file=sys.stderr)
        return 2
    src = arquivo if os.path.exists(arquivo) else os.path.join(BACKUPS, nome)
    novo, erro = validar(src, info["tipo"])
    if erro:
        print(f"backup recusado: {erro}. Nada foi alterado.", file=sys.stderr)
        return 1
    alvo = destino(info)
    atual, erro_atual = validar(alvo, info["tipo"]) if os.path.exists(alvo) else (None, "inexistente")
    print(f"backup : {src}\n  {resumo(novo, info['tipo'])}")
    print(f"destino: {alvo}\n  {resumo(atual, info['tipo']) if atual is not None else erro_atual}")
    if info["tipo"] == "aplicadas" and atual is not None:
        perdidas = {a.get("chave") for a in atual["aplicadas"]} - {a.get("chave") for a in novo["aplicadas"]}
        if perdidas:
            # These were sent after the backup: restoring forgets them and the bot could apply again.
            print(f"ATENÇÃO: {len(perdidas)} aplicada(s) do arquivo atual não existem no backup "
                  "e seriam esquecidas (risco de reenvio).")
    if not aplicar:
        print("simulação: nada foi alterado. Use --aplicar para restaurar.")
        return 0
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    with travado(alvo):
        if os.path.exists(alvo):
            prefixo = nome[: -len(".AAAAMMDD-HHMM.json")]
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            guarda = os.path.join(BACKUPS, f"{prefixo}.pre-restore.{stamp}.json")
            shutil.copy2(alvo, guarda)
            print(f"cópia do atual: {guarda}")
        gravar(alvo, novo)
    print("restaurado.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("backup", nargs="?", help="arquivo de backup a restaurar")
    ap.add_argument("--listar", action="store_true", help="lista os backups e sua validade")
    ap.add_argument("--verificar", action="store_true", help="valida todos os backups (exit 1 se algum for inválido)")
    ap.add_argument("--aplicar", action="store_true", help="restaura de fato (sem isso é só simulação)")
    a = ap.parse_args()
    if a.listar or a.verificar:
        return listar(a.verificar)
    if not a.backup:
        ap.print_help()
        return 2
    return restaurar(a.backup, a.aplicar)


if __name__ == "__main__":
    sys.exit(main())
