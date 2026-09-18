#!/usr/bin/env bash
# pull-monitor.sh — "correio" do monitor via git.
# Faz o fast-forward do dir monitor/ e, se o codigo mudou, derruba o publisher
# para que o monitor-keepalive.sh (*/5) o ressuba com a versao nova.
# Nunca commita, nunca envia segredo. Exit 0 = ok, 2 = atencao (ver log).
set -uo pipefail

BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$BOT_ROOT/monitor"
PUB="$REPO/publish-status.mjs"
LOG="$BOT_ROOT/monitor-pull.log"
export TZ="${BOT_TZ:-America/Sao_Paulo}"

# Se GITHUB_TOKEN estiver setado com um PAT sem acesso, ele mascara o token bom.
unset GITHUB_TOKEN GH_TOKEN

[ -d "$REPO/.git" ] || { echo "$(date -Is) ERRO: $REPO sem .git" >> "$LOG"; exit 2; }

before="$(git -C "$REPO" rev-parse HEAD 2>/dev/null)"
if ! git -C "$REPO" pull --ff-only --quiet 2>>"$LOG"; then
  echo "$(date -Is) ERRO: git pull falhou (conflito local? rode git status)" >> "$LOG"
  exit 2
fi
after="$(git -C "$REPO" rev-parse HEAD 2>/dev/null)"

if [ "$before" != "$after" ]; then
  echo "$(date -Is) atualizado $before -> $after; derrubando publisher p/ recarregar" >> "$LOG"
  pkill -f "$PUB" 2>/dev/null || true
fi
exit 0
