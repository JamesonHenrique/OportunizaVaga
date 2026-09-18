#!/bin/bash
# tests/test_validate.sh — suite minima em bash puro (sem framework), saida TAP.
# Cobre: scripts/validate.sh (exit 0 nos validos, exit !=0 nos invalidos)
# e bot/dry-run.sh --json (saida parseavel por python, ok == true).
# Uso: bash tests/test_validate.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
FIX="tests/fixtures"

TOTAL=6
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

# Backup dos exemplos para os testes de swap (restaurados via trap).
BACKUP_DIR="$(mktemp -d)"
cp examples/dados_candidato.example.json "$BACKUP_DIR/dados.json"
cp examples/aplicadas.example.json "$BACKUP_DIR/aplic.json"
restaura() {
  cp "$BACKUP_DIR/dados.json" examples/dados_candidato.example.json
  cp "$BACKUP_DIR/aplic.json" examples/aplicadas.example.json
  rm -rf "$BACKUP_DIR"
}
trap restaura EXIT

# 1 — validate.sh passa com os exemplos validos do repo.
TMP1="$(mktemp)"
if bash scripts/validate.sh >"$TMP1" 2>&1; then
  relata 0 "validate.sh exit 0 com exemplos validos"
else
  cat "$TMP1"
  relata 1 "validate.sh exit 0 com exemplos validos"
fi
rm -f "$TMP1"

# 2 — fixture dados_candidato valido: JSON parseavel + chave email presente.
if python3 - "$FIX/dados_candidato.valido.json" <<'PYEOF' 2>/dev/null; then
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
assert isinstance(doc, dict) and "email" in doc, "sem email"
PYEOF
  relata 0 "fixture dados_candidato.valido.json tem email"
else
  relata 1 "fixture dados_candidato.valido.json tem email"
fi

# 3 — validate.sh falha com dados_candidato sem email (swap temporario).
cp "$FIX/dados_candidato.sem-email.json" examples/dados_candidato.example.json
TMP3="$(mktemp)"
if bash scripts/validate.sh >"$TMP3" 2>&1; then
  ST3=0
else
  ST3=$?
fi
cp "$BACKUP_DIR/dados.json" examples/dados_candidato.example.json
if [ "$ST3" -ne 0 ]; then
  relata 0 "validate.sh exit !=0 com dados_candidato sem email"
else
  cat "$TMP3"
  relata 1 "validate.sh exit !=0 com dados_candidato sem email"
fi
rm -f "$TMP3"

# 4 — fixture aplicadas valida: JSON parseavel + rodizio.proximo presente.
if python3 - "$FIX/aplicadas.valida.json" <<'PYEOF' 2>/dev/null; then
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
assert isinstance(doc, dict) and "aplicadas" in doc, "sem aplicadas"
assert isinstance(doc.get("rodizio"), dict) and doc["rodizio"].get("proximo"), "sem rodizio.proximo"
PYEOF
  relata 0 "fixture aplicadas.valida.json tem rodizio.proximo"
else
  relata 1 "fixture aplicadas.valida.json tem rodizio.proximo"
fi

# 5 — validate.sh falha com aplicadas sem rodizio.proximo (swap temporario).
cp "$FIX/aplicadas.sem-rodizio-proximo.json" examples/aplicadas.example.json
TMP5="$(mktemp)"
if bash scripts/validate.sh >"$TMP5" 2>&1; then
  ST5=0
else
  ST5=$?
fi
cp "$BACKUP_DIR/aplic.json" examples/aplicadas.example.json
if [ "$ST5" -ne 0 ]; then
  relata 0 "validate.sh exit !=0 com aplicadas sem rodizio.proximo"
else
  cat "$TMP5"
  relata 1 "validate.sh exit !=0 com aplicadas sem rodizio.proximo"
fi
rm -f "$TMP5"

# 6 — dry-run.sh --json: exit 0 + saida parseavel por python com ok == true.
TMP6="$(mktemp)"
if bash bot/dry-run.sh --json >"$TMP6" 2>&1; then
  if python3 - "$TMP6" <<'PYEOF' 2>/dev/null; then
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
assert doc.get("ok") is True, "ok != true"
assert doc.get("dry_run") is True, "dry_run != true"
PYEOF
    relata 0 "dry-run.sh --json parseavel por python com ok true"
  else
    relata 1 "dry-run.sh --json parseavel por python com ok true"
  fi
else
  cat "$TMP6"
  relata 1 "dry-run.sh --json parseavel por python com ok true"
fi
rm -f "$TMP6"

if [ "$FAIL" -eq 0 ]; then
  echo "# verde: $N/$TOTAL"
  exit 0
else
  echo "# FALHAS: $FAIL/$TOTAL"
  exit 1
fi
