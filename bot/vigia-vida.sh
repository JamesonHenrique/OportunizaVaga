#!/bin/bash
# vigia-vida.sh - dead man's switch do robo (cron a cada 15 min). Avisa no Telegram (scripts/notificar.sh) quando:
#   1. o loop.sh NAO esta rodando em 2 checagens seguidas (o guardiao.sh religa; uma falta e normal);
#   2. o heartbeat do monitor (MONITOR_URL/api/status?ping=1) tem mais de HB_MAX_MIN minutos
#      (publisher parado = monitor cego). So checa se MONITOR_URL estiver definido;
#   3. o aplicadas.json do perfil ativo esta ausente ou ilegivel.
# Por que nao usar so o log: o loop dorme 1-4 h legitimamente quando nao ha vaga nova, entao "log parado"
# gera alarme falso constante. Limite: roda NA maquina; PC desligado nao avisa (precisa de pinger externo).
# Uso: bot/vigia-vida.sh   (exit 0 = tudo ok, 2 = alerta enviado). Env: MONITOR_URL (opcional, sem padrao),
# HB_MAX_MIN (20), VIGIA_INTERVALO_MIN (15, so para a mensagem), NOTIFY, VIGIA_STATE, VIGIA_LOOP_PATTERN.
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT/bot" || exit 1
MONITOR_URL="${MONITOR_URL:-}"
case "$MONITOR_URL" in *sua-url*|*example.invalid*) MONITOR_URL="" ;; esac   # placeholders = nao configurado
HB_MAX_MIN="${HB_MAX_MIN:-20}"
INTERVALO="${VIGIA_INTERVALO_MIN:-15}"
STATE="${VIGIA_STATE:-$BOT_ROOT/bot/state/vigia-vida.falhas}"
NOTIFY="${NOTIFY:-$BOT_ROOT/scripts/notificar.sh}"
LOOP_PATTERN="${VIGIA_LOOP_PATTERN:-bot/loop\.sh}"
mkdir -p "$(dirname "$STATE")"
problemas=()

# 1) loop vivo? (checa o PROCESSO, como o guardiao)
if pgrep -f "$LOOP_PATTERN" >/dev/null; then
  rm -f "$STATE"
else
  n=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE"
  [ "$n" -ge 2 ] && problemas+=("loop.sh parado ha ~$((n * INTERVALO)) min (guardiao nao religou)")
fi

# 2) heartbeat do monitor (opcional)
if [ -n "$MONITOR_URL" ]; then
  hb=$(curl -s --max-time 15 "${MONITOR_URL%/}/api/status?ping=1" | python3 -c "
import json,sys,datetime as D
try:
    u=json.load(sys.stdin).get('updatedAt')
    print(int((D.datetime.now(D.timezone.utc)-D.datetime.fromisoformat(u.replace('Z','+00:00'))).total_seconds()//60) if u else 'sem')
except Exception: print('erro')")
  case "$hb" in
    sem|erro|"") problemas+=("monitor sem heartbeat (${hb:-erro}): publisher parado ou servidor frio") ;;
    *) [ "$hb" -gt "$HB_MAX_MIN" ] && problemas+=("heartbeat do monitor ha ${hb} min (limite ${HB_MAX_MIN})") ;;
  esac
fi

# 3) estado legivel? (aplicadas.json do perfil ativo, mesma resolucao do loop)
APLICADAS=$(python3 -c "
import sys
sys.path.insert(0, '.')
import vagas_filtros as v
print(v.resolve_paths()['aplicadas'])" 2>/dev/null)
# cron nao herda BOT_PERFIL: sem o arquivo resolvido, usa o aplicadas.json mais recente de bot/state/*/ (como o ctl.sh)
[ -f "$APLICADAS" ] || APLICADAS=$(ls -t "$BOT_ROOT"/bot/state/*/aplicadas.json 2>/dev/null | head -1)
if [ -z "$APLICADAS" ] || ! python3 -c "import json,sys;json.load(open(sys.argv[1], encoding='utf-8'))" "$APLICADAS" 2>/dev/null; then
  problemas+=("aplicadas.json ausente ou ilegivel (${APLICADAS:-caminho nao resolvido})")
fi

if [ ${#problemas[@]} -gt 0 ]; then
  msg="[ALERTA] Robo: $(IFS='; '; echo "${problemas[*]}") - rode scripts/ctl.sh status"
  echo "[$(date '+%F %T')] $msg"
  "$NOTIFY" "$msg"
  exit 2
fi
exit 0
