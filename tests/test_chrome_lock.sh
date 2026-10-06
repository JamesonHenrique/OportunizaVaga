#!/bin/bash
# tests/test_chrome_lock.sh — protocolo do Chrome compartilhado (bot/chrome-lock.sh), saida TAP.
# Tudo em diretorio temporario (CHROME_LOCK_FILE/DIR/LOG): nunca toca o lock real.
# Uso: bash tests/test_chrome_lock.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CL="$ROOT/bot/chrome-lock.sh"

TOTAL=12
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

T="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$T"' EXIT
export CHROME_LOCK_FILE="$T/lock" CHROME_LOCK_DIR="$T" CHROME_LOCK_LOG="$T/logs/chrome-lock.log"
unset CHROME_LOCK_YIELD_RC

# 1 — run path: executes the command and passes its output through.
OUT="$("$CL" t1 normal 2 -- echo hello)"; RC=$?
[ "$RC" = "0" ] && [ "$OUT" = "hello" ]; relata $? "caminho normal executa o comando (rc=$RC)"

# 2 — the command's own exit code is returned; the log records the release.
"$CL" t2 normal 2 -- bash -c 'exit 7'; RC=$?
[ "$RC" = "7" ] && grep -q "released the Chrome.*rc=7" "$CHROME_LOCK_LOG"; relata $? "rc do comando propagado e registrado no log (rc=$RC)"

# 3 — usage error.
"$CL" onlyname >/dev/null 2>&1; RC=$?
[ "$RC" = "2" ]; relata $? "argumentos faltando -> rc 2 (rc=$RC)"
"$CL" t3 urgente 1 -- true >/dev/null 2>&1; RC=$?
[ "$RC" = "2" ]; relata $? "PRIO invalida -> rc 2 (rc=$RC)"

# 4 — yield: a fresh flag of another job makes the normal job give way (76, or CHROME_LOCK_YIELD_RC).
touch "$T/agent-chrome-9222.prio.followup"
"$CL" loop normal 2 -- echo nao-deve-rodar >"$T/out" 2>&1; RC=$?
[ "$RC" = "76" ] && [ ! -s "$T/out" ]; relata $? "normal cede a flag fresca de outro job (rc=$RC)"
CHROME_LOCK_YIELD_RC=75 "$CL" loop normal 2 -- true; RC=$?
[ "$RC" = "75" ]; relata $? "CHROME_LOCK_YIELD_RC remapeia o rc de cessao (rc=$RC)"

# 5 — a stale flag (> 120 min) and the job's own flag do not make it yield.
touch -d '3 hours ago' "$T/agent-chrome-9222.prio.followup"
"$CL" loop normal 2 -- true; RC=$?
[ "$RC" = "0" ]; relata $? "flag velha (>120min) e ignorada (rc=$RC)"
touch "$T/agent-chrome-9222.prio.loop"
"$CL" loop normal 2 -- true; RC=$?
[ "$RC" = "0" ]; relata $? "flag do proprio job nao faz ceder (rc=$RC)"
rm -f "$T"/agent-chrome-9222.prio.*

# 6 — alta: flag exists while the command runs and is removed afterwards.
"$CL" fu alta 2 -- bash -c 'test -e "$CHROME_LOCK_DIR/agent-chrome-9222.prio.fu"'; RC=$?
[ "$RC" = "0" ] && [ ! -e "$T/agent-chrome-9222.prio.fu" ]; relata $? "alta cria a flag durante a execucao e remove ao fim (rc=$RC)"

# 7 — alta: a flag owned by the parent job is NOT removed.
touch "$T/agent-chrome-9222.prio.fu"
"$CL" fu alta 2 -- true
[ -e "$T/agent-chrome-9222.prio.fu" ]; relata $? "flag pre-existente (do job pai) nao e removida"
rm -f "$T"/agent-chrome-9222.prio.*

# 8 — timeout: another holder keeps the lock -> 75 after WAIT seconds, command not run.
( exec 8>>"$CHROME_LOCK_FILE"; flock 8; sleep 4 ) &
sleep 0.5
T0=$(date +%s)
"$CL" busy normal 1 -- echo nao-deve-rodar >"$T/out" 2>&1; RC=$?
DT=$(( $(date +%s) - T0 ))
[ "$RC" = "75" ] && [ ! -s "$T/out" ] && [ "$DT" -le 3 ] && grep -q "timed out" "$CHROME_LOCK_LOG"; relata $? "lock ocupado -> timeout rc 75 em ${DT}s"
wait

# 9 — gmail-status.py has no lock of its own (04/10): it shells out to chrome-lock.sh with priority alta, and
# rc 75 (waited past WAIT) is reported as "Chrome ocupado", not as a parse error.
python3 - "$ROOT" "$T" <<'PYEOF'
import importlib.util, os, sys, types
root, t = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("gs", os.path.join(root, "bot", "gmail-status.py"))
gs = importlib.util.module_from_spec(spec); spec.loader.exec_module(gs)
visto = {}
def falso(cmd, **kw):
    visto["cmd"] = cmd
    return types.SimpleNamespace(returncode=75, stdout="", stderr="")
gs.subprocess.run = falso
r = gs.extrair_conta("conta@exemplo.invalid")
c = visto["cmd"]
assert c[0] == gs.CHROME_LOCK and c[0].endswith("chrome-lock.sh") and c[1:3] == ["gmail", "alta"] and "--" in c, c
assert r["ok"] is False and "rc 75" in r["erro"], r
PYEOF
relata $? "gmail-status usa o chrome-lock.sh com prioridade alta e trata rc 75"

if [ "$FAIL" -eq 0 ]; then echo "# verde: $N/$TOTAL"; exit 0; else echo "# FALHAS: $FAIL/$TOTAL"; exit 1; fi
