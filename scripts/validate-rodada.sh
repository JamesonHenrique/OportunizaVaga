#!/bin/bash
# validate-rodada.sh — sanidade SEMANTICA de aplicadas.json (duplicatas, datas locais, coerencia).
# Complementa validate.sh (schema). So le, nunca escreve. Quieto por padrao (so falha faz barulho).
# O loop (bot/loop.sh) roda apos cada rodada; tambem serve de cron:
#   */30 * * * * $BOT_DIR/scripts/validate-rodada.sh >> $BOT_DIR/bot/validate-rodada.log 2>&1
# Uso: scripts/validate-rodada.sh [aplicadas.json]   Exit 0 = ok; 1 = falha.
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT" || exit 1
exec python3 "$BOT_ROOT/scripts/validate-rodada.py" "$@"
