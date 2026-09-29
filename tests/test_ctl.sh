#!/bin/bash
# tests/test_ctl.sh — scripts/ctl.sh (status/rodada/chrome) numa copia sintetica do repo (saida TAP).
# Uso: bash tests/test_ctl.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOTAL=5
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bot/logs" "$T/scripts"
cp "$ROOT/scripts/ctl.sh" "$T/scripts/"
cp "$ROOT/examples/aplicadas.example.json" "$T/bot/aplicadas.json"
echo "[2026-09-29 10:00:00] rodada iniciada (perfil x, rodadas vazias seguidas: 0)" > "$T/bot/loop.log"
printf 'build · modelo-x\nnavegou\nResumo final: 1 vaga avaliada\n' > "$T/bot/logs/rodada-teste-a.log"
echo "[2026-09-29 10:00:01] loop(normal) released the Chrome after 3s (rc=0)" > "$T/bot/logs/chrome-lock.log"
unset APLICADAS_FILE

OUT="$(bash "$T/scripts/ctl.sh" status 2>&1)"
echo "$OUT" | grep -q "== Motor" && echo "$OUT" | grep -q "rodada iniciada"; relata $? "status mostra o motor e a ultima linha do loop.log"
echo "$OUT" | grep -q "enviadas: 0" && echo "$OUT" | grep -q "proximo site: indeed"; relata $? "status resume o estado (aplicadas.json)"
[ "$(echo "$OUT" | wc -l)" -le 30 ]; relata $? "status tem tamanho curto (<= 30 linhas)"
bash "$T/scripts/ctl.sh" rodada | grep -q "Resumo final: 1 vaga avaliada"; relata $? "rodada mostra o final do ultimo log"
bash "$T/scripts/ctl.sh" chrome | grep -q "released the Chrome"; relata $? "chrome mostra o chrome-lock.log"

if [ "$FAIL" -eq 0 ]; then echo "# verde: $N/$TOTAL"; exit 0; else echo "# FALHAS: $FAIL/$TOTAL"; exit 1; fi
