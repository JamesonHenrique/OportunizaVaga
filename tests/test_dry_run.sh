#!/bin/bash
# tests/test_dry_run.sh — suite TAP para bot/dry-run.sh (global, perfil, site único).
# Cobre o plano SEM risco: nenhuma escrita em estado real, nenhum browser aberto.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TOTAL=3
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

check_json() { # check_json <arquivo>
  python3 - "$1" <<'PYEOF'
import json, sys
doc = json.load(open(sys.argv[1], encoding='utf-8'))
assert doc.get('ok') is True, 'ok != true'
assert doc.get('dry_run') is True, 'dry_run != true'
assert doc.get('browser_aberto') is False, 'browser_aberto != false'
assert doc.get('candidaturas_enviadas') == 0, 'candidaturas_enviadas != 0'
PYEOF
}

# 1 — dry-run global: 6 sites, estado default e nenhuma escrita.
TMP1="$(mktemp)"
if ./bot/dry-run.sh --json >"$TMP1" 2>&1; then
  if check_json "$TMP1" && python3 - "$TMP1" <<'PYEOF'
import json, sys
doc = json.load(open(sys.argv[1], encoding='utf-8'))
assert doc.get('global') is True, 'global != true'
assert doc.get('site_count') == 6, 'site_count != 6'
assert doc.get('perfil', {}).get('slug') == 'default', 'perfil.slug != default'
assert doc.get('estado', {}).get('isolado') is False, 'estado.isolado != false'
PYEOF
  then
    relata 0 "dry-run global lista 6 sites sem browser"
  else
    relata 1 "dry-run global lista 6 sites sem browser"
  fi
else
  cat "$TMP1" >&2
  relata 1 "dry-run global lista 6 sites sem browser"
fi
rm -f "$TMP1"

# 2 — dry-run com perfil: estado isolado e slug derivado do nome.
PROFILE="$(mktemp)"
cat >"$PROFILE" <<'EOF'
{
  "nome_perfil": "Frontend Teste",
  "nivel": "junior",
  "termos": ["frontend junior remoto"],
  "pular_tipos": ["design/UX"]
}
EOF
TMP2="$(mktemp)"
if BOT_PERFIL="$PROFILE" ./bot/dry-run.sh --json >"$TMP2" 2>&1; then
  if check_json "$TMP2" && python3 - "$TMP2" <<'PYEOF'
import json, sys
doc = json.load(open(sys.argv[1], encoding='utf-8'))
assert doc.get('perfil', {}).get('slug') == 'frontend-teste', 'perfil.slug != frontend-teste'
assert doc.get('estado', {}).get('isolado') is True, 'estado.isolado != true'
assert doc.get('estado', {}).get('diretorio', '').endswith('/state/frontend-teste'), 'diretorio errado'
PYEOF
  then
    relata 0 "dry-run com perfil usa estado isolado"
  else
    relata 1 "dry-run com perfil usa estado isolado"
  fi
else
  cat "$TMP2" >&2
  relata 1 "dry-run com perfil usa estado isolado"
fi
rm -f "$PROFILE" "$TMP2"

# 3 — dry-run com --site: plano restrito a um adaptador.
TMP3="$(mktemp)"
if ./bot/dry-run.sh --json --site indeed >"$TMP3" 2>&1; then
  if check_json "$TMP3" && python3 - "$TMP3" <<'PYEOF'
import json, sys
doc = json.load(open(sys.argv[1], encoding='utf-8'))
assert doc.get('global') is False, 'global != false'
assert doc.get('site_count') == 1, 'site_count != 1'
assert doc.get('sites', [])[0].get('site_id') == 'indeed', 'site_id != indeed'
PYEOF
  then
    relata 0 "dry-run --site indeed restrige o plano a 1 site"
  else
    relata 1 "dry-run --site indeed restrige o plano a 1 site"
  fi
else
  cat "$TMP3" >&2
  relata 1 "dry-run --site indeed restrige o plano a 1 site"
fi
rm -f "$TMP3"

if [ "$FAIL" -eq 0 ]; then
  echo "# verde: $N/$TOTAL"
  exit 0
else
  echo "# FALHAS: $FAIL/$TOTAL"
  exit 1
fi
