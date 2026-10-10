#!/bin/bash
# tests/test_doctor_estado.sh — scripts/doctor-estado.py (secao 7 do bot/doctor.sh), saida TAP.
# Estado sintetico num diretorio temporario; nada do bot real e lido.
# Uso: bash tests/test_doctor_estado.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"

TOTAL=6
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT
export OV_STATE_ROOT="$TMPD/bot" OV_BACKUP_DIR="$TMPD/backups" BOT_PERFIL=""
mkdir -p "$OV_STATE_ROOT/state/front" "$OV_STATE_ROOT/logs" "$OV_BACKUP_DIR"
cp tests/fixtures/aplicadas.valida.json "$OV_STATE_ROOT/aplicadas.json"
printf '{"aplicadas": [], "envios_pendentes": {"x_dev_1": {"empresa": "Exemplo"}}}' > "$OV_STATE_ROOT/state/front/aplicadas.json"
bash scripts/backup-jsons.sh >/dev/null 2>&1
touch "$OV_STATE_ROOT/logs/rodada-1.log"

SAIDA="$("$PY" scripts/doctor-estado.py 2>&1)"; RC=$?
[ "$RC" -eq 0 ] && grep -q "\[ok\] estado 'front'" <<<"$SAIDA" && grep -q "\[ok\] backups:" <<<"$SAIDA" && grep -q "\[ok\] ultima rodada" <<<"$SAIDA"
relata $? "estado saudavel: exit 0 com perfis, backups e ultima rodada [ok]"
grep -q "\[??\] estado 'front': 1 envio(s) com resultado desconhecido" <<<"$SAIDA"
relata $? "envio pendente vira aviso (nao bloqueia)"
! grep -q "Exemplo" <<<"$SAIDA"
relata $? "nenhum nome de empresa/dado do estado aparece na saida"

printf '{"niveis": [' > "$TMPD/perfil.json"
SAIDA="$(BOT_PERFIL="$TMPD/perfil.json" "$PY" scripts/doctor-estado.py 2>&1)"; RC=$?
[ "$RC" -eq 1 ] && grep -q "\[FALHA\] perfil ilegivel" <<<"$SAIDA"
relata $? "perfil corrompido = FALHA e exit 1"

printf '{' > "$OV_STATE_ROOT/aplicadas.json"
SAIDA="$("$PY" scripts/doctor-estado.py 2>&1)"; RC=$?
[ "$RC" -eq 1 ] && grep -q "\[FALHA\] estado 'default' ilegivel" <<<"$SAIDA" && grep -q "\[ok\] backups:" <<<"$SAIDA"
relata $? "estado corrompido = FALHA, e as outras checagens continuam"

rm -f "$OV_BACKUP_DIR"/*
SAIDA="$("$PY" scripts/doctor-estado.py 2>&1)"
grep -q "\[??\] nenhum backup em" <<<"$SAIDA" && ! grep -q "nao rodou" <<<"$SAIDA"
relata $? "sem backups: aviso claro, nenhuma checagem quebra"

exit $((FAIL > 0))
