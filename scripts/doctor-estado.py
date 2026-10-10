#!/usr/bin/env python3
"""doctor-estado.py — state and operation checks shared by bot/doctor.sh and bot/doctor.ps1.

Read-only. Prints the doctor's line format ([ok] / [..] / [??] aviso / [FALHA]) and exits 1 only when
something blocks a correct run (unreadable profile or state file). Never prints personal data: only
profile slugs, counts, ages and file names.

  python3 scripts/doctor-estado.py
Env: BOT_PERFIL, OV_STATE_ROOT (default bot), OV_BACKUP_DIR (default bot/backups) — same as the loop/backup.
"""
import glob
import importlib.util
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.environ.get("OV_STATE_ROOT") or os.path.join(ROOT, "bot")
BACKUPS = os.environ.get("OV_BACKUP_DIR") or os.path.join(STATE, "backups")
sys.path.insert(0, os.path.join(ROOT, "bot"))

falhou = False


def ok(m):
    print(f"  [ok] {m}")


def info(m):
    print(f"  [..] {m}")


def aviso(m, como):
    print(f"  [??] {m} -- {como}")


def falha(m, como):
    global falhou
    falhou = True
    print(f"  [FALHA] {m} -- {como}")


def _modulo(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rel(p):
    r = os.path.relpath(p, ROOT)
    return p if r.startswith("..") else r


def idade_h(path):
    return (time.time() - os.path.getmtime(path)) / 3600


def perfil():
    import perfil_render
    caminho = os.environ.get("BOT_PERFIL") or os.path.join(STATE, "perfil.json")
    if not os.path.exists(caminho):
        info("sem perfil.json: o loop usa os padroes historicos e o estado em bot/aplicadas.json.")
        return
    try:
        doc = perfil_render.carregar(caminho)
    except SystemExit as e:
        falha(f"perfil ilegivel ({os.path.basename(caminho)})", f"{e} O loop se recusa a rodar assim.")
        return
    ok(f"perfil valido ({os.path.basename(caminho)}, nome_perfil={doc.get('nome_perfil', 'perfil')}).")


def estados():
    validar = _modulo("validate_rodada", os.path.join(ROOT, "scripts", "validate-rodada.py"))
    arquivos = [("default", os.path.join(STATE, "aplicadas.json"))]
    arquivos += [(os.path.basename(os.path.dirname(p)), p) for p in sorted(glob.glob(os.path.join(STATE, "state", "*", "aplicadas.json")))]
    achou = False
    for nome, p in arquivos:
        if not os.path.exists(p):
            continue
        achou = True
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError) as e:
            falha(f"estado '{nome}' ilegivel ({e.__class__.__name__})",
                  "restaure: python3 scripts/restore-json.py --listar (docs/OPERACAO.md).")
            continue
        if not isinstance(d, dict) or not isinstance(d.get("aplicadas"), list):
            falha(f"estado '{nome}' sem a lista 'aplicadas'", "restaure de um backup valido.")
            continue
        ok(f"estado '{nome}': {len(d['aplicadas'])} aplicadas, {len(d.get('bloqueados') or {})} bloqueados.")
        pend = d.get("envios_pendentes") if isinstance(d.get("envios_pendentes"), dict) else {}
        if pend:
            aviso(f"estado '{nome}': {len(pend)} envio(s) com resultado desconhecido",
                  "confira no portal/e-mail; saiu = estado.py add-aplicada, nao saiu = estado.py cancelar-intencao.")
        com = sum(1 for a in d["aplicadas"] if isinstance(a, dict) and a.get("intencao_em"))
        sem = sum(1 for a in d["aplicadas"] if isinstance(a, dict) and a.get("sem_intencao"))
        if sem:
            aviso(f"estado '{nome}': {sem} envio(s) do robo sem `intencao` (passo d0) contra {com} com",
                  "o modelo pulou a protecao contra reenvio; veja docs/OPERACAO.md (envio com resultado desconhecido).")
        elif com:
            ok(f"estado '{nome}': {com} envio(s) com intencao registrada antes do clique.")
        problemas = validar.check(d, os.environ.get("OV_ALLOW_UTC") == "1")
        if problemas:
            aviso(f"estado '{nome}': {len(problemas)} inconsistencia(s)", f"python3 scripts/validate-rodada.py {rel(p)}")
    if not achou:
        info("nenhum aplicadas.json ainda (normal antes da primeira rodada).")


def backups():
    restore = _modulo("restore_json", os.path.join(ROOT, "scripts", "restore-json.py"))
    restore.BACKUPS = BACKUPS
    lista = restore.backups()
    if not lista:
        aviso("nenhum backup em " + rel(BACKUPS),
              "agende scripts/backup-jsons.sh (config/crontab.example) ou rode-o 1x.")
        return
    ruins = [n for n, i in lista if restore.validar(os.path.join(BACKUPS, n), i["tipo"])[1]]
    recente = min(idade_h(os.path.join(BACKUPS, n)) for n, i in lista if i["tipo"] == "aplicadas") \
        if any(i["tipo"] == "aplicadas" for _, i in lista) else None
    if ruins:
        aviso(f"{len(ruins)} backup(s) invalido(s) de {len(lista)}", "python3 scripts/restore-json.py --verificar")
    if recente is None:
        aviso("nenhum backup de aplicadas.json", "rode scripts/backup-jsons.sh.")
    elif recente > 48:
        aviso(f"backup mais recente de aplicadas tem {recente:.0f}h", "o cron do backup parou? (config/crontab.example)")
    else:
        ok(f"backups: {len(lista)} arquivos, mais recente ha {recente:.0f}h, {len(lista) - len(ruins)} validos.")


def operacao():
    logs = glob.glob(os.path.join(STATE, "logs", "rodada-*.log"))
    if not logs:
        info("nenhuma rodada registrada em bot/logs (normal antes da primeira execucao).")
    else:
        h = min(idade_h(p) for p in logs)
        (ok if h <= 6 else lambda m: aviso(m, "o loop esta parado? ./scripts/ctl.sh status"))(
            f"ultima rodada ha {h:.1f}h.")
    loop_log = os.path.join(STATE, "loop.log")
    if os.path.exists(loop_log):
        with open(loop_log, encoding="utf-8", errors="replace") as fh:
            fim = fh.readlines()[-300:]
        # Count only: log lines can carry company/job names, never printed here.
        graves = sum(1 for linha in fim if "ERRO" in linha or "ALERTA" in linha)
        if graves:
            aviso(f"{graves} linha(s) ERRO/ALERTA nas ultimas 300 do loop.log", "veja: grep -E 'ERRO|ALERTA' bot/loop.log | tail")
        else:
            ok("loop.log sem ERRO/ALERTA nas ultimas 300 linhas.")


def main():
    for etapa in (perfil, estados, backups, operacao):
        try:
            etapa()
        except Exception as e:   # one broken check must not hide the others
            aviso(f"checagem {etapa.__name__} nao rodou ({e.__class__.__name__}: {e})", "reporte numa issue.")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
