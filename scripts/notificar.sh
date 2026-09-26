#!/bin/bash
# notificar.sh "mensagem" — push genérico via Telegram Bot API (sendMessage).
# Silencioso (exit 0) sem TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no ambiente
# (mesmas envs de scripts/digest.sh --send; nunca hardcode, nunca imprime o token).
# Dedupe: a MESMA mensagem não é reenviada dentro de 6h (state/notify-sent).
# Uso: scripts/notificar.sh "texto da notificação"
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MSG="${1:-}"
[ -n "$MSG" ] || exit 0
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || exit 0

STATE="${OV_NOTIFY_STATE:-$BOT_ROOT/bot/state/notify-sent}"
mkdir -p "$(dirname "$STATE")"
touch "$STATE"
KEY=$(printf '%s' "$MSG" | md5sum | cut -c1-12)
NOW=$(date +%s)
if awk -v k="$KEY" -v now="$NOW" '$1==k && now-$2 < 21600 {found=1} END {exit !found}' "$STATE"; then
  exit 0   # mesma mensagem ja enviada nas ultimas 6h
fi

curl -s -m 15 -o /dev/null "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=${MSG}" \
  && echo "$KEY $NOW" >> "$STATE"

# mantem so as ultimas 200 entradas (o dedupe nao precisa de historico maior)
tail -n 200 "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
exit 0
