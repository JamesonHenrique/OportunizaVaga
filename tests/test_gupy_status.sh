#!/bin/bash
# tests/test_gupy_status.sh — bot/gupy-status.py decisions, offline (TAP output): tab -> status, one application per
# card, job id wins, true ties are skipped, retroactive records pass validation. Never opens a browser.
# Uso: bash tests/test_gupy_status.sh   (exit 0 = tudo verde)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOTAL=3; N=0; FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
python3 - "$ROOT" <<'PY'
import sys, importlib.util
s = importlib.util.spec_from_file_location("g", sys.argv[1] + "/bot/gupy-status.py"); g = importlib.util.module_from_spec(s); s.loader.exec_module(g)
assert (g.classe("Em andamento", "2/7"), g.classe("Em andamento", "1/6"), g.classe("Finalizadas", ""), g.classe("Em banco de talentos", "")) == \
       ("proxima_etapa", "em_analise", "encerrada", "encerrada")
PY
relata $? "aba do Gupy -> status (andamento 1/n em_analise, 2/n+ proxima_etapa, resto encerrada)"
python3 - "$ROOT" <<'PY'
import sys, importlib.util
s = importlib.util.spec_from_file_location("g", sys.argv[1] + "/bot/gupy-status.py"); g = importlib.util.module_from_spec(s); s.loader.exec_module(g)
ap = [{"chave": "a1", "empresa": "Acme", "vaga": "Desenvolvedor Junior"},
      {"chave": "a2_12345678", "empresa": "Acme", "vaga": "DESENVOLVEDOR JÚNIOR"},
      {"chave": "b", "empresa": "Beta", "vaga": "Pessoa Desenvolvedora Full Stack Júnior"}]
c = [{"empresa": "Acme", "vaga": "DESENVOLVEDOR JÚNIOR"}, {"empresa": "Acme", "vaga": "12345678 - DESENVOLVEDOR JÚNIOR"},
     {"empresa": "Beta", "vaga": "Pessoa Desenvolvedora Full Stack Júnior com foco em Front-End e Cloud"}, {"empresa": "Outra", "vaga": "Dev"}]
par, amb = g.casar_todos(ap, c)
assert par[1]["chave"] == "a2_12345678" and par[2]["chave"] == "b" and par[0]["chave"] == "a1" and 3 not in par, par
par, amb = g.casar_todos(ap[:2], c[:1]); assert amb == {0} and not par
PY
relata $? "casamento 1-1: id da vaga vence, titulo longo casa, empate real fica ambiguo"
cat > "$T/a.json" <<'J'
{"aplicadas":[{"chave":"gupy_1","empresa":"X","vaga":"Dev","registro_retroativo":true,"status":"encerrada"}],"bloqueados":{},"quase_la":{},"rodizio":{"ordem":["gupy"],"proximo":"gupy"}}
J
python3 "$ROOT/scripts/validate-rodada.py" "$T/a.json" >/dev/null 2>&1
relata $? "registro retroativo sem data passa no validate-rodada"
[ "$FAIL" -eq 0 ]
