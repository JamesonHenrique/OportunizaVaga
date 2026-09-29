#!/bin/bash
# Follow-up semanal das candidaturas (segundas 09:00, via cron). Sessao unica:
# le o status das vagas ja aplicadas e grava em aplicadas.json. NUNCA se candidata.
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export BOT_ROOT   # o prompt referencia $BOT_ROOT; exportado p/ os comandos que o agente roda via bash
cd "$BOT_ROOT/bot" || exit 1
export TZ=America/Fortaleza
export PATH="$HOME/.opencode/bin:$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/bin:$PATH"
OPENCODE_BIN="$HOME/.opencode/bin/opencode"
[ -x "$OPENCODE_BIN" ] || { echo "[$(date '+%F %T')] ERRO: opencode nao encontrado" >> followup.log; exit 1; }
[ -f "$HOME/.config/opencode/cron.env" ] && set -a && . "$HOME/.config/opencode/cron.env" && set +a

# Instancia unica
exec 9>/tmp/oportunizavaga-followup.lock
flock -n 9 || exit 0

# Lean run: MCPs/ferramentas que o follow-up nunca usa custam tokens de schema em toda chamada.
# Precedencia: OV_OPENCODE_CONFIG_CONTENT > bot/opencode-enxuto.py (fail-open) > config fixa abaixo.
OPENCODE_CONFIG_CONTENT="${OV_OPENCODE_CONFIG_CONTENT:-$(python3 "$BOT_ROOT/bot/opencode-enxuto.py" 2>/dev/null)}"
[ -n "$OPENCODE_CONFIG_CONTENT" ] || OPENCODE_CONFIG_CONTENT='{"mcp":{"github":{"enabled":false},"context7":{"enabled":false},"ai-memory":{"enabled":false},"playwright-firefox":{"enabled":false}},"permission":{"*":"allow","skill":"deny"}}'
export OPENCODE_CONFIG_CONTENT
export AI_MEMORY_DISABLE=1

# Semanal com retentativa diaria: o cron pode rodar todo dia; pula se o ultimo
# SUCESSO tiver menos de 6 dias (assim uma falha nao trava 7 dias sem tentar de novo).
mkdir -p state
OK_MARK="${OV_FOLLOWUP_OK_MARK:-state/followup.ok}"
if [ -f "$OK_MARK" ] && [ $(( $(date +%s) - $(stat -c %Y "$OK_MARK" 2>/dev/null || echo 0) )) -lt $((6 * 86400)) ]; then
  exit 0
fi

# Cascata de modelos gratuitos (mesma familia do loop.sh; se um bater quota ou
# travar, cascateia para o proximo em vez de esperar o timeout inteiro parado).
MODELOS=(
  "opencode/muse-spark-1.3-contributor-free"
  "opencode/nemotron-3-ultra-free"
  "opencode/nemotron-3.5-lightning-free"
  "opencode/mimo-v2.5-free"
)
STALL_WATCHDOG_SECONDS="${OV_FOLLOWUP_STALL:-180}"
NOTIFICAR_SH="$BOT_ROOT/scripts/notificar.sh"
notify() { [ -x "$NOTIFICAR_SH" ] && "$NOTIFICAR_SH" "$1" >/dev/null 2>&1 || true; }

FLOG="logs/followup-$(date '+%Y%m%d-%H%M%S').log"
echo "[$(date '+%F %T')] follow-up iniciado" >> followup.log
if curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null; then
  APLICADAS_FILE="${APLICADAS_FILE:-$BOT_ROOT/bot/aplicadas.json}"
  export APLICADAS_FILE   # estado.py (chamado pelo agente via bash) usa este env var como default
  PROMPT="$(cat "$BOT_ROOT/bot/prompt_followup.md")

APLICADAS (gerado agora; NAO leia aplicadas.json inteiro) — chave | empresa | vaga | como | data | status atual:
$(python3 - "$APLICADAS_FILE" <<'PY'
import json, sys
try:
    ap = json.load(open(sys.argv[1], encoding='utf-8')).get('aplicadas', [])
except Exception:
    ap = []
for a in ap:
    print(f"  {a.get('chave')} | {a.get('empresa')} | {str(a.get('vaga'))[:60]} | {str(a.get('como'))[:40]} | {a.get('data')} | {a.get('status', '-')}")
PY
)"

  # Priority flag for the WHOLE run (all model attempts), so the application loop does not grab the
  # Chrome between attempts; chrome-lock.sh does not remove a flag it did not create.
  touch /tmp/agent-chrome-9222.prio.followup; trap 'rm -f /tmp/agent-chrome-9222.prio.followup' EXIT
  STATUS=1
  for MODELO in "${MODELOS[@]}"; do
    setsid timeout --kill-after=30s 55m \
      "$BOT_ROOT/bot/chrome-lock.sh" followup alta 1800 -- \
      "$OPENCODE_BIN" run -m "$MODELO" --title "followup-$(date '+%F')" "$PROMPT" \
      </dev/null 9>&- >"$FLOG" 2>&1 &
    RPID=$!
    # Stall watchdog: modelo com quota pode ficar minutos calado segurando o Chrome.
    # So conta depois que o opencode ja esta rodando de verdade (passou da espera do
    # flock): saida parada por STALL_WATCHDOG_SECONDS s -> aborta e cascateia.
    (
      last=-1; parado=0
      while sleep 15; do
        pgrep -f -- "opencode run .*--title followup-" >/dev/null || { parado=0; continue; }
        tam=$(stat -c %s "$FLOG" 2>/dev/null || echo 0)
        if [ "$tam" -eq "$last" ]; then parado=$((parado + 15)); else parado=0; last=$tam; fi
        if [ "$parado" -ge "$STALL_WATCHDOG_SECONDS" ]; then
          echo "STALL_WATCHDOG" >> "$FLOG"
          kill -TERM -- "-$RPID" 2>/dev/null || kill -TERM "$RPID" 2>/dev/null
          break
        fi
      done
    ) 9>&- >/dev/null 2>&1 &
    WPID=$!
    wait "$RPID"; STATUS=$?
    kill "$WPID" 2>/dev/null
    wait "$WPID" 2>/dev/null

    if grep -q "STALL_WATCHDOG" "$FLOG"; then
      echo "[$(date '+%F %T')] follow-up: ${MODELO} travado sem saida (provavel cota), proximo" >> followup.log
      STATUS=1
      continue
    fi
    [ "$STATUS" -eq 75 ] && break   # Chrome ocupado por 30min: tenta de novo amanha
    if grep -qE "QUOTA_EXAUSTA|Rate limit|Model not found" "$FLOG"; then
      echo "[$(date '+%F %T')] follow-up: ${MODELO} sem cota/indisponivel, proximo" >> followup.log
      STATUS=1
      continue
    fi
    break
  done

  { echo "--- saida do follow-up (completa em ${FLOG}) ---"; tail -n 20 "$FLOG"; } >> followup.log
  if [ "$STATUS" -eq 0 ]; then
    touch "$OK_MARK"
    echo "[$(date '+%F %T')] follow-up ok (modelo ${MODELO})" >> followup.log
    notify "📬 Follow-up semanal: $(tail -n 12 "$FLOG" | tr -s '\n' ' ' | cut -c1-600)"
  else
    echo "[$(date '+%F %T')] follow-up FALHOU (status ${STATUS}); tenta de novo amanha" >> followup.log
    notify "⚠️ Follow-up falhou (status ${STATUS}); tenta de novo amanhã"
  fi
else
  echo "[$(date '+%F %T')] follow-up pulado: Chrome CDP fora" >> followup.log
fi
ls -1t logs/followup-*.log 2>/dev/null | tail -n +11 | xargs -r rm -f
