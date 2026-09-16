#!/usr/bin/env bash
# monitor-keepalive.sh — mantem SO o publisher do monitor de pe.
# Esta maquina e MX Linux com sysVinit (PID 1 = init), sem systemd: o kit
# systemd (~/monitor/pc/install-autopilot.sh + units) NAO funciona aqui, entao
# este cron faz o papel de supervisor do publisher — e SO do publisher.
#
# Importante: NAO sobe o loop de candidaturas (opencode) nem o Chrome. O loop
# segue PAUSADO ate religado manualmente. Unico script que sabe INICIAR o
# publisher; o pull-monitor.sh apenas o derruba quando o codigo muda, e este
# ressobe na proxima passada (*/5).
set -uo pipefail

REPO="$HOME/monitor"
PUB="$REPO/publish-status.mjs"
LOG="$HOME/monitor-keepalive.log"

# node estavel do fnm (default alias segue a versao corrente); fallback no PATH.
NODE="$HOME/.local/share/fnm/aliases/default/bin/node"
[ -x "$NODE" ] || NODE="$(command -v node || echo node)"

export MONITOR_URL="https://sua-url.vercel.app"
export CANDIDATURAS_ROOT="$HOME/candidaturas"
export LINKEDIN_ROOT="$HOME/linkedin-rh"
export TZ="America/Fortaleza"

# pgrep pelo caminho absoluto do .mjs: so casa o proprio publisher (este
# script e o pull-monitor tem o caminho no ARQUIVO, nunca no argv).
if ! pgrep -f "$PUB" >/dev/null 2>&1; then
  echo "$(date -Is) publisher fora, subindo com $NODE" >> "$LOG"
  ( cd "$REPO" && setsid "$NODE" "$PUB" >/tmp/candidaturas-monitor.log 2>&1 </dev/null & )
fi
