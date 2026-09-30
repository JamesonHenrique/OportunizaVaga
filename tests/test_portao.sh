#!/bin/bash
# tests/test_portao.sh — bot/rodada-portao.py (round gate), prompt_cond.so_fila and bot/tempo-rodada.py (TAP output).
# Pure decisions on synthetic state; never opens a browser or calls a model.
# Uso: bash tests/test_portao.sh   (exit 0 = tudo verde)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOTAL=5; N=0; FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

python3 - "$ROOT" <<'PY'
import sys, importlib.util
from datetime import datetime, timedelta
s = importlib.util.spec_from_file_location("p", sys.argv[1] + "/bot/rodada-portao.py"); p = importlib.util.module_from_spec(s); s.loader.exec_module(p)
now = datetime(2026, 9, 30, 12, 0)
h = lambda n: (now - timedelta(hours=n)).isoformat(timespec="minutes")
cfg = {"rodizio_intervalo_h": {"indeed": 4, "gupy": 8}}
d = {"rodizio": {"ordem": ["indeed", "gupy"], "proximo": "indeed"}}
sau = {"sites": {"indeed": {"ultima_varredura": h(1)}, "gupy": {"ultima_varredura": h(2)}}}
assert p.decidir(d, {}, cfg, sau, {}, now)[0] == "pular"
assert p.decidir(d, {"vagas": {"a": {"status": "nova", "score": 3}}}, cfg, sau, {}, now)[0] == "so_fila"
sau["sites"]["gupy"]["ultima_varredura"] = h(9)
m = p.decidir(d, {}, cfg, sau, {}, now); assert m[0] == "completa" and m[2] == "gupy", m
assert p.decidir(d, {}, cfg, sau, {}, now, {"gupy": {"estado": "bloqueado", "em": h(1)}})[0] == "pular"   # blocked site
PY
relata $? "portao: pular / so_fila / completa (move o rodizio) / site bloqueado nao vence"

python3 "$ROOT/bot/rodada-portao.py" /nao/existe | grep -q '^completa'
relata $? "portao falha aberto (estado ilegivel -> rodada normal)"

python3 - "$ROOT" <<'PY'
import sys; sys.path.insert(0, sys.argv[1] + "/bot"); import prompt_cond as pc
for f, marca in (("prompt_loop.md", "MODO SO FILA"), ("prompt_loop.en.md", "QUEUE-ONLY MODE")):
    t = open(sys.argv[1] + "/bot/" + f, encoding="utf-8").read(); r = pc.so_fila(t)
    assert marca in r and len(r) < len(t) and ("b) RODÍZIO DE SITES" not in r and "b) SITE ROTATION" not in r), f
PY
relata $? "so_fila corta o passo b nos prompts pt e en"

echo $(( $(date +%s) - 780 )) > "$T/rodada_inicio"
STATE_DIR="$T" python3 "$ROOT/bot/tempo-rodada.py" | grep -q "NAO comece"
relata $? "tempo-rodada: 13 min -> nao comecar vaga nova"
echo $(( $(date +%s) - 60 )) > "$T/rodada_inicio"
STATE_DIR="$T" python3 "$ROOT/bot/tempo-rodada.py" | grep -q " ok "
relata $? "tempo-rodada: 1 min -> ok"
[ "$FAIL" -eq 0 ]
