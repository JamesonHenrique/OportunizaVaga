#!/bin/bash
# tests/test_modelos_saude.sh — cascata adaptativa (bot/modelos-saude.py): ordem por taxa de sucesso, quarentena,
# minimo de ativos e fail-open. Offline; logs e estado sinteticos em diretorio temporario.
# Uso: bash tests/test_modelos_saude.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"

TOTAL=5
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export ROOT MODELOS_SAUDE_FILE="$TMP/ms.json" MODELOS_SAUDE_LOGS="$TMP/loop.log*"

# 1 — ordena por sucesso; desempate mantem a ordem escrita a mao; modelo nunca visto vale 0,5.
"$PY" - <<'PYEOF'
import importlib.util, os
from datetime import datetime
s = importlib.util.spec_from_file_location("m", os.environ["ROOT"] + "/bot/modelos-saude.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
L = ["[2026-09-29 10:00:00] rodada usou o modelo b"] * 5 + \
    ["[2026-09-29 10:00:00] modelo a encerrou sem navegar (sessao improdutiva), cascateando para o proximo"] * 12 + \
    ["[2026-09-29 10:00:00] modelo c no limite, cascateando para o proximo",
     "[2026-09-29 10:00:00] modelo c quebrou o formato de tool-call, cascateando para o proximo",
     "[2026-09-29 10:00:00] modelo c morreu apos erro de ferramenta (sem resumo final), cascateando para o proximo",
     "[2020-01-01 10:00:00] rodada usou o modelo a"]   # fora da janela de 7 dias
st = m.estatisticas(datetime(2026, 9, 29, 12), L)
assert st["b"]["usou"] == 5 and st["a"]["improdutiva"] == 12 and "usou" in st["a"] and st["a"]["usou"] == 0, st
assert (st["c"]["limite"], st["c"]["improdutiva"], st["c"]["erro"]) == (1, 1, 1), st["c"]
assert m.ordenar(["a", "b", "d"], st, {}, datetime(2026, 9, 29)) == ["b", "d", "a"]   # d unseen = 0.5
PYEOF
relata $? "ordena por taxa de sucesso, janela de 7 dias, desempate estavel"

# 2 — quarentena: 0 sucessos em >= 10 tentativas; nunca abaixo de MIN_ATIVOS.
"$PY" - <<'PYEOF'
import importlib.util, os
from datetime import datetime
s = importlib.util.spec_from_file_location("m", os.environ["ROOT"] + "/bot/modelos-saude.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
agora = datetime(2026, 9, 29, 12)
assert m.ordenar(["a", "b", "c"], {}, {"a": "2026-10-09"}, agora) == ["b", "c"]
assert m.ordenar(["a", "b"], {}, {"a": "2026-10-09", "b": "2026-10-09"}, agora) == ["a", "b"]   # below MIN_ATIVOS: bench ignored
PYEOF
relata $? "quarentena tira o modelo da cascata mas respeita o minimo de ativos"

# 3 — ponta a ponta: loop.log sintetico -> 'ordenar' poe o melhor na frente e quarentena o inutil (estado no override).
TS="$(date '+%F %T')"
{ for _ in 1 2 3 4 5; do echo "[$TS] rodada usou o modelo x/bom"; done
  for _ in $(seq 1 10); do echo "[$TS] modelo x/inutil encerrou sem navegar (sessao improdutiva), cascateando para o proximo"; done
} > "$TMP/loop.log"
OUT="$("$PY" bot/modelos-saude.py ordenar x/inutil x/novo x/bom x/outro | tr '\n' ' ')"
[ "$OUT" = "x/bom x/novo x/outro " ] && grep -q '"x/inutil"' "$MODELOS_SAUDE_FILE"
relata $? "ordenar: melhor na frente, modelo inutil em quarentena e persistido (got: $OUT)"

# 4 — fail-open: sem log/estado a ordem escrita a mao volta; estado corrompido tambem.
rm -f "$MODELOS_SAUDE_FILE" "$TMP"/loop.log*
OUT="$("$PY" bot/modelos-saude.py ordenar x/um x/dois | tr '\n' ' ')"
[ "$OUT" = "x/um x/dois " ]
relata $? "fail-open: sem historico a ordem original volta"
echo '{lixo' > "$MODELOS_SAUDE_FILE"
OUT="$("$PY" bot/modelos-saude.py ordenar x/um x/dois 2>/dev/null | tr '\n' ' ')"
[ "$OUT" = "x/um x/dois " ]
relata $? "fail-open: estado corrompido nao perde a cascata"

# nao tocou no estado real
[ ! -e bot/state/modelos_saude.json ] || { echo "vazou para bot/state"; FAIL=1; }
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
