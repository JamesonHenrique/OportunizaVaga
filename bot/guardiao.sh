#!/bin/bash
# Supervisor: garante que loop de candidaturas e publisher do monitor estejam de pe.
# Chamado pelo cron a cada 5min e no boot. Idempotente: se ja estiver rodando, nao faz nada
# (o loop.sh tem flock proprio e sai calado; o publisher e checado por pgrep).
# Sem systemd na maquina, o cron faz o papel de supervisor.
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT/bot" || exit 1
export TZ=America/Fortaleza
export MONITOR_URL="${MONITOR_URL:-https://sua-url.vercel.app}"
export CANDIDATURAS_ROOT="$BOT_ROOT/bot"

# 1) Publisher do monitor — dono unico: monitor-keepalive.sh (*/5). O guardiao
# NAO sobe publisher para nao duplicar (o dono unico e scripts/monitor-keepalive.sh).

# Loop de candidaturas — checa o PROCESSO, nao so o lock: um `sleep` orfao
# herdado do loop antigo segura o fd do flock e faz o fuser mentir
# (loop morto, lock "preso", guardiao achando que estava tudo bem).
if pgrep -f "bot/loop\.sh" >/dev/null; then
  : # loop vivo, nada a fazer
else
  if fuser /tmp/oportunizavaga-loop.lock >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] guardiao: lock preso sem loop vivo, limpando orfaos" >> guardiao.log
    fuser -k /tmp/oportunizavaga-loop.lock >/dev/null 2>&1 || true
    sleep 2
  fi
  echo "[$(date '+%F %T')] guardiao: loop caido, subindo" >> guardiao.log
  setsid "$BOT_ROOT/bot/loop.sh" >/dev/null 2>&1 </dev/null &
fi

# 3) Chrome com CDP — sem ele o robo nao navega e os logins se perdem de vista.
if ! curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null; then
  echo "[$(date '+%F %T')] guardiao: Chrome CDP fora, subindo" >> guardiao.log
  DISPLAY=:0 setsid "$BOT_ROOT/browser/chrome-real.sh" >/tmp/chrome-real.log 2>&1 </dev/null &
fi

# mantem guardiao.log pequeno
[ "$(stat -c %s guardiao.log 2>/dev/null || echo 0)" -gt 262144 ] && tail -n 200 guardiao.log > guardiao.log.tmp && mv guardiao.log.tmp guardiao.log
exit 0
