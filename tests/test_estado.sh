#!/bin/bash
# tests/test_estado.sh — suite minima em bash puro (sem framework), saida TAP.
# Cobre: bot/estado.py (CLI compacta de leitura/escrita atomica de aplicadas.json).
# Uso: bash tests/test_estado.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
ESTADO="bot/estado.py"

TOTAL=7
N=0
FAIL=0
echo "1..$TOTAL"

relata() { # relata <status: 0=ok> <descricao>
  N=$((N + 1))
  if [ "$1" -eq 0 ]; then
    echo "ok $N - $2"
  else
    echo "not ok $N - $2"
    FAIL=$((FAIL + 1))
  fi
}

TMP_STATE="$(mktemp -d)/aplicadas.json"
cp examples/aplicadas.example.json "$TMP_STATE"
cleanup() { rm -rf "$(dirname "$TMP_STATE")"; }
trap cleanup EXIT

# 1 — resumo roda sem erro e cita o rodizio.
OUT1="$(python3 "$ESTADO" --file "$TMP_STATE" resumo 2>&1)"
if echo "$OUT1" | grep -q "rodizio.proximo=indeed"; then
  relata 0 "resumo mostra rodizio.proximo"
else
  echo "$OUT1"
  relata 1 "resumo mostra rodizio.proximo"
fi

# 2 — add-aplicada grava e resumo passa a listar a chave.
python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"teste-1","empresa":"AcmeCorp","vaga":"Dev Jr"}' >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" resumo | grep -q "teste-1"; then
  relata 0 "add-aplicada grava a chave nova"
else
  relata 1 "add-aplicada grava a chave nova"
fi

# 3 — add-aplicada com chave repetida nao duplica (exit != 0).
python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"teste-1","empresa":"AcmeCorp","vaga":"Dev Jr"}' >/dev/null 2>&1
ST3=$?
if [ "$ST3" -ne 0 ]; then
  relata 0 "add-aplicada recusa chave duplicada"
else
  relata 1 "add-aplicada recusa chave duplicada"
fi

# 4 — add-bloqueado grava motivo e get recupera o registro.
python3 "$ESTADO" --file "$TMP_STATE" add-bloqueado "teste-2" '{"motivo":"CPF ausente"}' >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" get "teste-2" | grep -q "CPF ausente"; then
  relata 0 "add-bloqueado + get recuperam o motivo"
else
  relata 1 "add-bloqueado + get recuperam o motivo"
fi

# 5 — set-quase-la grava e null remove.
python3 "$ESTADO" --file "$TMP_STATE" set-quase-la "teste-3" '{"falta":"telefone"}' >/dev/null
HAS_ANTES="$(python3 "$ESTADO" --file "$TMP_STATE" tem "teste-3")"
python3 "$ESTADO" --file "$TMP_STATE" set-quase-la "teste-3" null >/dev/null
HAS_DEPOIS="$(python3 "$ESTADO" --file "$TMP_STATE" tem "teste-3")"
if [ "$HAS_ANTES" = "sim quase_la" ] && echo "$HAS_DEPOIS" | grep -q "^nao"; then
  relata 0 "set-quase-la grava e null remove"
else
  echo "antes=$HAS_ANTES depois=$HAS_DEPOIS"
  relata 1 "set-quase-la grava e null remove"
fi

# 6 — rodizio-avancar avanca proximo para o item seguinte da ordem.
python3 "$ESTADO" --file "$TMP_STATE" rodizio-avancar >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" resumo | grep -q "rodizio.proximo=linkedin"; then
  relata 0 "rodizio-avancar avanca para o proximo da ordem"
else
  relata 1 "rodizio-avancar avanca para o proximo da ordem"
fi

# 7 — descartes soma incrementos e grava total.
python3 "$ESTADO" --file "$TMP_STATE" descartes 2 1 3 >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" resumo | grep -q '"total": 6'; then
  relata 0 "descartes soma nivel+modelo+stack no total"
else
  relata 1 "descartes soma nivel+modelo+stack no total"
fi

if [ "$FAIL" -eq 0 ]; then
  echo "# verde: $N/$TOTAL"
  exit 0
else
  echo "# FALHAS: $FAIL/$TOTAL"
  exit 1
fi
