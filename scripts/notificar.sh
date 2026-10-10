#!/bin/bash
# notificar.sh "mensagem" — push genérico via Telegram Bot API (sendMessage).
# Silencioso (exit 0) sem TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no ambiente
# (mesmas envs de scripts/digest.sh --send; nunca hardcode, nunca imprime o token).
# Dedupe: o MESMO alerta não é reenviado dentro de 6h (OV_NOTIFY_JANELA_S; state/notify-sent).
# "Mesmo" ignora números (horas, contagens, ids): "reprovou às 10:02" e "reprovou às 10:22" são um alerta
# só — com o hash exato, cada rodada mandava de novo. Só envio aceito pela API (HTTP 2xx) conta.
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
JANELA="${OV_NOTIFY_JANELA_S:-21600}"
KEY=$(printf '%s' "$MSG" | sed -E 's/[0-9]+/#/g' | md5sum | cut -c1-12)
NOW=$(date +%s)
if awk -v k="$KEY" -v now="$NOW" -v j="$JANELA" '$1==k && now-$2 < j {found=1} END {exit !found}' "$STATE"; then
  exit 0   # mesmo alerta ja enviado dentro da janela
fi

curl -sf -m 15 -o /dev/null "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=${MSG}" \
  && echo "$KEY $NOW" >> "$STATE"

# mantem so as ultimas 200 entradas (o dedupe nao precisa de historico maior)
tail -n 200 "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
exit 0
