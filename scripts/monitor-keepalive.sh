#!/usr/bin/env bash
# monitor-keepalive.sh — mantem SO o publisher do monitor de pe.
# Sem systemd na maquina, este cron (*/5) faz o papel de supervisor do publisher
# — e SO do publisher.
#
# Importante: NAO sobe o loop de candidaturas (opencode) nem o Chrome (o dono
# deles e bot/guardiao.sh). Unico script que sabe INICIAR o publisher;
# o pull-monitor.sh apenas o derruba quando o codigo muda, e este ressobe na proxima passada.
set -uo pipefail

BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$BOT_ROOT/monitor"
PUB="$REPO/publish-status.mjs"
LOG="$BOT_ROOT/monitor-keepalive.log"

# node estavel do fnm (default alias segue a versao corrente); fallback no PATH.
NODE="$HOME/.local/share/fnm/aliases/default/bin/node"
[ -x "$NODE" ] || NODE="$(command -v node || echo node)"

export MONITOR_URL="${MONITOR_URL:-https://sua-url.vercel.app}"
export CANDIDATURAS_ROOT="$BOT_ROOT/bot"
export TZ="${BOT_TZ:-America/Sao_Paulo}"

# pgrep pelo caminho absoluto do .mjs: so casa o proprio publisher (este
# script e o pull-monitor tem o caminho no ARQUIVO, nunca no argv).
if ! pgrep -f "$PUB" >/dev/null 2>&1; then
  echo "$(date -Is) publisher fora, subindo com $NODE" >> "$LOG"
  ( cd "$REPO" && setsid "$NODE" "$PUB" >/tmp/candidaturas-monitor.log 2>&1 </dev/null & )
fi

# Mede a cota diaria dos :free do OpenRouter (1x/h) e grava quota-cache.json,
# que o snapshot.mjs mistura no painel "Uso dos modelos". Mesmo esquema do
# publisher: caminho absoluto no pgrep, sobe so se nao estiver rodando.
QUOTA="$REPO/quota-daemon.mjs"
if ! pgrep -f "$QUOTA" >/dev/null 2>&1; then
  echo "$(date -Is) quota-daemon fora, subindo com $NODE" >> "$LOG"
  ( cd "$REPO" && setsid "$NODE" "$QUOTA" >/tmp/quota-daemon.log 2>&1 </dev/null & )
fi
