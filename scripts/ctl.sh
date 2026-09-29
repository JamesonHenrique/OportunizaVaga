#!/bin/bash
# scripts/ctl.sh — um ponto de entrada para inspecionar o bot, sem abrir nenhum log grande.
# Respostas curtas e de tamanho fixo (barato em tokens). So le; nao altera nada.
#   scripts/ctl.sh status   saude de cada parte em ~20 linhas (comece por aqui)
#   scripts/ctl.sh rodada   resultado da ultima rodada (modelo, desfecho, resposta final)
#   scripts/ctl.sh chrome   quem usou o Chrome compartilhado recentemente (bot/logs/chrome-lock.log)
# Estado lido: $APLICADAS_FILE, senao bot/aplicadas.json, senao o primeiro bot/state/*/aplicadas.json.
# Espelho Windows: scripts/ctl.ps1.
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
BOT_ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
BOT="$BOT_ROOT/bot"
cd "$BOT" || exit 1

estado_json() {
  if [ -n "${APLICADAS_FILE:-}" ] && [ -f "$APLICADAS_FILE" ]; then echo "$APLICADAS_FILE"; return; fi
  [ -f "$BOT/aplicadas.json" ] && { echo "$BOT/aplicadas.json"; return; }
  ls -t "$BOT"/state/*/aplicadas.json 2>/dev/null | head -1
}

status() {
  local now pid f ap
  echo "== Motor"
  pid=$(ps -eo pid,args | awk '/bash .*bot\/loop\.sh/ && !/awk/ {print $1; exit}')
  if [ -n "$pid" ]; then echo "loop: vivo (pid $pid, $(ps -o etime= -p "$pid" | tr -d ' '))"; else echo "loop: PARADO (o guardiao.sh religa em ate 5 min, se agendado)"; fi
  grep -E "rodada (iniciada|usou|estourou|ok)|FALHOU|dormindo|ALERTA" loop.log 2>/dev/null | tail -2 | cut -c1-140
  now=$(date +%s)
  awk -v now="$now" '{last[$1]=$2} END {b=0; n=0; for (m in last) {n++; if (last[m] > now) b++}; printf "modelos em cooldown: %d de %d vistos\n", b, n}' state/model_cooldown 2>/dev/null
  echo "== Prompt (ultima rodada)"
  f=$(ls -t logs/rodada-*.log 2>/dev/null | head -1)
  rt=$(ls -t prompt_loop.runtime.md state/*/prompt_loop.runtime.md 2>/dev/null | head -1)
  if [ -n "$rt" ] && [ -n "$f" ]; then
    echo "prompt: $(wc -c < "$rt") bytes | ja-visto: $(grep -c 'estado.py.*ja-visto' "$f") | leu aplicadas.json inteiro: $(grep -cE '(Read|cat ).*aplicadas\.json' "$f") (meta 0) | improdutivas hoje: $(grep "^\[$(date +%F)" loop.log 2>/dev/null | grep -c improdutiva)"
  else
    echo "sem prompt renderizado ou sem log de rodada ainda"
  fi
  echo "== Estado"
  ap=$(estado_json)
  if [ -n "$ap" ]; then
    python3 - "$ap" <<'PY'
import json, sys
from datetime import date
d = json.load(open(sys.argv[1], encoding="utf-8"))
hoje = date.today().isoformat()
ap = d.get("aplicadas", [])
st = {}
for a in ap:
    k = a.get("status") or "enviada"
    st[k] = st.get(k, 0) + 1
print(f"enviadas: {len(ap)} (hoje {sum(1 for a in ap if str(a.get('data'))[:10] == hoje)}) | status: "
      + (", ".join(f"{k}={v}" for k, v in sorted(st.items(), key=lambda x: -x[1])) or "-"))
q, b = d.get("quase_la") or {}, d.get("bloqueados") or {}
r = d.get("rodizio") or {}
print(f"quase_la: {len(q)} | bloqueados: {len(b)} | proximo site: {r.get('proximo')} | ordem calculada em: {r.get('ordem_calculada_em', '-')}")
PY
  else
    echo "aplicadas.json nao encontrado (defina APLICADAS_FILE)"
  fi
  echo "== Navegador"
  curl -s --max-time 3 http://127.0.0.1:9222/json/version >/dev/null && echo "chrome 9222: ok" || echo "chrome 9222: FORA"
  tail -1 logs/chrome-lock.log 2>/dev/null | cut -c1-140
  ls "${CHROME_LOCK_DIR:-/tmp}"/agent-chrome-9222.prio.* 2>/dev/null | sed 's/.*prio\./prioridade ativa: /'
  echo "== Logs"
  tail -1 logs/redact.log 2>/dev/null | cut -c1-100
  [ -f gmail-status.log ] && tail -1 gmail-status.log | cut -c1-120
  [ -f validate-rodada.log ] && tail -1 validate-rodada.log | cut -c1-120
}

rodada() {
  local f
  f=$(ls -t logs/rodada-*.log 2>/dev/null | head -1)
  [ -n "$f" ] || { echo "sem log de rodada"; exit 0; }
  echo "arquivo: $f ($(stat -c %s "$f") bytes)"
  grep -m1 -oE "build · [^ ]+" "$f"
  echo "--- final:"
  sed 's/\x1b\[[0-9;]*m//g' "$f" | grep -vE "^\s*$|^[⚙→$✗]" | tail -12 | cut -c1-200
}

case "${1:-status}" in
  status) status ;;
  rodada) rodada ;;
  chrome) tail -15 logs/chrome-lock.log 2>/dev/null || echo "sem bot/logs/chrome-lock.log ainda" ;;
  *) sed -n 2,8p "$SELF" ;;
esac
