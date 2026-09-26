#!/bin/bash
# tests/test_rodizio_saude.sh — suite minima em bash puro (sem framework), saida TAP.
# Cobre: bot/rodizio-saude.py (pausa de 48h apos N rodadas seguidas sem candidatura).
# Uso: bash tests/test_rodizio_saude.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
SAUDE="bot/rodizio-saude.py"

TOTAL=4
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

TMPDIR_STATE="$(mktemp -d)"
TMP_STATE="$TMPDIR_STATE/aplicadas.json"
cp examples/aplicadas.example.json "$TMP_STATE"
cleanup() { rm -rf "$TMPDIR_STATE"; }
trap cleanup EXIT

# 1 — pre roda sem erro numa rodada sem sites pausados (nada a pular).
OUT1="$(python3 "$SAUDE" pre "$TMP_STATE" 2>&1)"
ST1=$?
if [ "$ST1" -eq 0 ]; then
  relata 0 "pre roda sem erro sem sites pausados"
else
  echo "$OUT1"
  relata 1 "pre roda sem erro sem sites pausados"
fi

# 2 — site com 3 rodadas seguidas ja sem candidatura (seed) + mais 1 rodada vazia = pausa (4a).
python3 - "$TMPDIR_STATE/rodizio_saude.json" <<'PYEOF'
import json, sys
json.dump({"sites": {"indeed": {"rodadas": 3, "vazias_seguidas": 3, "aplicadas": 0, "pausado_ate": None}}}, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF
python3 "$SAUDE" pre "$TMP_STATE" >/dev/null 2>&1   # rodizio.proximo comeca em "indeed"
OUT2="$(python3 "$SAUDE" pos "$TMP_STATE" 2>&1)"
if echo "$OUT2" | grep -q "indeed pausado"; then
  relata 0 "site pausado apos 4 rodadas seguidas sem candidatura"
else
  echo "$OUT2"
  relata 1 "site pausado apos 4 rodadas seguidas sem candidatura"
fi

# 3 — rodizio_saude.json foi criado no MESMO diretorio do aplicadas.json (isolado por perfil)
# e marca indeed como pausado.
if python3 -c "
import json, sys
d = json.load(open('$TMPDIR_STATE/rodizio_saude.json', encoding='utf-8'))
sys.exit(0 if d.get('sites', {}).get('indeed', {}).get('pausado_ate') else 1)
"; then
  relata 0 "rodizio_saude.json marca indeed como pausado"
else
  relata 1 "rodizio_saude.json marca indeed como pausado"
fi

# 4 — pos com candidatura nova (enviada DURANTE a rodada) zera vazias_seguidas do site da vez.
# rodizio.proximo ja avancou para "linkedin" no teste 2; pre() marca o inicio da rodada de
# linkedin ANTES da candidatura ser gravada, exatamente como o loop real faz.
python3 "$SAUDE" pre "$TMP_STATE" >/dev/null 2>&1
python3 - "$TMP_STATE" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d.setdefault("aplicadas", []).append({"chave": "teste-rodizio", "empresa": "AcmeCorp", "vaga": "Dev Jr"})
json.dump(d, open(p, "w", encoding="utf-8"))
PYEOF
python3 "$SAUDE" pos "$TMP_STATE" >/dev/null 2>&1
VAZIAS_SEGUIDAS="$(python3 -c "
import json
d = json.load(open('$TMPDIR_STATE/rodizio_saude.json', encoding='utf-8'))
print(d.get('sites', {}).get('linkedin', {}).get('vazias_seguidas', 'sem-site'))
")"
if [ "$VAZIAS_SEGUIDAS" = "0" ]; then
  relata 0 "candidatura nova zera vazias_seguidas do site"
else
  echo "vazias_seguidas=$VAZIAS_SEGUIDAS"
  relata 1 "candidatura nova zera vazias_seguidas do site"
fi

if [ "$FAIL" -eq 0 ]; then
  echo "# verde: $N/$TOTAL"
  exit 0
else
  echo "# FALHAS: $FAIL/$TOTAL"
  exit 1
fi
