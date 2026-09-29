#!/bin/bash
# tests/test_jsonlock.sh — race test for bot/jsonlock.py used by bot/estado.py (saida TAP).
# 30 parallel `estado.py descartes 1 0 0` must add exactly 30 (no lost update, no tmp leftovers).
# Uso: bash tests/test_jsonlock.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
ESTADO="bot/estado.py"
PY="${PYTHON:-python3}"

TOTAL=3
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT
STATE="$TMPD/aplicadas.json"
cp examples/aplicadas.example.json "$STATE"
"$PY" "$ESTADO" --file "$STATE" descartes 0 0 0 >/dev/null

for _ in $(seq 30); do
  "$PY" "$ESTADO" --file "$STATE" descartes 1 0 0 >/dev/null 2>&1 &
done
wait

NIVEL="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["descartes_listagem"]["nivel"])' "$STATE")"
[ "$NIVEL" = "30" ]; relata $? "30 escritas paralelas somam exatamente 30 (obtido: $NIVEL)"

LEFT="$(find "$TMPD" -name '*.tmp' | wc -l)"
[ "$LEFT" = "0" ]; relata $? "nenhum .tmp sobrando"

"$PY" -c 'import json,sys; json.load(open(sys.argv[1]))' "$STATE"; relata $? "estado continua JSON valido"

if [ "$FAIL" -eq 0 ]; then echo "# verde: $N/$TOTAL"; exit 0; else echo "# FALHAS: $FAIL/$TOTAL"; exit 1; fi
