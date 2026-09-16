#!/bin/bash
# Follow-up semanal das candidaturas (segundas 09:00, via cron). Sessao unica:
# le o status das vagas ja aplicadas e grava em aplicadas.json. NUNCA se candidata.
cd $HOME/candidaturas || exit 1
export TZ=America/Fortaleza
export PATH="$HOME/.opencode/bin:$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/bin:$PATH"
OPENCODE_BIN=$HOME/.opencode/bin/opencode
[ -x "$OPENCODE_BIN" ] || { echo "[$(date '+%F %T')] ERRO: opencode nao encontrado" >> followup.log; exit 1; }
[ -f $HOME/.config/opencode/cron.env ] && set -a && . $HOME/.config/opencode/cron.env && set +a

# Instancia unica
exec 9>/tmp/candidaturas-followup.lock
flock -n 9 || exit 0

MODELO="opencode/muse-spark-1.3-contributor-free"
FLOG="logs/followup-$(date '+%Y%m%d-%H%M%S').log"
echo "[$(date '+%F %T')] follow-up iniciado" >> followup.log
if curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null; then
  setsid timeout --kill-after=30s 15m \
    flock -w 900 -E 75 /tmp/agent-chrome-9222.lock \
    "$OPENCODE_BIN" run -m "$MODELO" --title "followup-$(date '+%F')" "$(cat prompt_followup.md)" \
    </dev/null 9>&- >"$FLOG" 2>&1
  STATUS=$?
  { echo "--- saida do follow-up (completa em ${FLOG}) ---"; tail -n 20 "$FLOG"; } >> followup.log
  echo "[$(date '+%F %T')] follow-up ok (status ${STATUS})" >> followup.log
else
  echo "[$(date '+%F %T')] follow-up pulado: Chrome CDP fora" >> followup.log
fi
ls -1t logs/followup-*.log 2>/dev/null | tail -n +11 | xargs -r rm -f
