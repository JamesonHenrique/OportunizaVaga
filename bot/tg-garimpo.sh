#!/bin/bash
# tg-garimpo.sh — wrapper (cron) de bot/tg-garimpo.py: instancia unica, timeout, log proprio.
# Opt-in: sem telegram_canais.json + credenciais o script Python sai calado (nada a fazer).
# Uso: bot/tg-garimpo.sh          (colheita)      |  bot/tg-garimpo.sh --login (1a vez)
# Se existir um venv em bot/.venv-tg, ele e usado (pip install telethon la dentro).
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT/bot" || exit 1
export TZ="${TZ:-America/Fortaleza}"
mkdir -p logs
PY=python3
[ -x .venv-tg/bin/python ] && PY=.venv-tg/bin/python
exec 9>/tmp/oportunizavaga-tg.lock
flock -n 9 || exit 0
if [ "${1:-}" = "--login" ]; then
  exec "$PY" tg-garimpo.py --login   # interativo: sem timeout
fi
timeout 300 "$PY" tg-garimpo.py >> logs/tg-garimpo.log 2>&1
