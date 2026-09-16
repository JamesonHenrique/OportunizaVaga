#!/bin/bash
# Loop continuo de candidaturas (deixa o PC ligado). Sessao nova por rodada.
# Estado duravel vive em aplicadas.json, nao na sessao do opencode.
cd $HOME/candidaturas || exit 1

# A maquina roda em America/New_York. Sem isto, todo log e toda data gravada saem
# 1h atras de SUA_CIDADE — foi o que fez candidaturas das 21h46 de 13/09 virarem 14/09.
export TZ=America/Fortaleza

# Binarios resolvidos explicitamente. O cron tem PATH minimo (/usr/bin:/bin) e NAO acha
# opencode (~/.opencode/bin) nem node (fnm): quando o guardiao reinicia este loop pelo
# cron, o `opencode`/`node` puro falha com "failed to execute opencode" -> status 69.
# (Foi exatamente isso que derrubou o loop do LinkedIn.) Este loop so "funcionava"
# porque o processo atual herdou o PATH interativo; um restart pelo cron quebraria.
export PATH="$HOME/.opencode/bin:$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/bin:$PATH"
OPENCODE_BIN=$HOME/.opencode/bin/opencode
NODE_BIN=$HOME/.local/share/fnm/aliases/default/bin/node
[ -x "$OPENCODE_BIN" ] || { echo "[$(date '+%F %T')] ERRO: opencode nao encontrado em $OPENCODE_BIN" >> loop.log; exit 1; }
[ -x "$NODE_BIN" ]     || { echo "[$(date '+%F %T')] ERRO: node nao encontrado em $NODE_BIN" >> loop.log; exit 1; }

# Chaves de provedores que exigem env (OpenRouter): o cron nao herda o ambiente
# interativo, entao sem isto o segundo poco :free morre com erro de auth no cron.
# Arquivo 600, so nesta maquina, nunca commitado nem publicado.
[ -f $HOME/.config/opencode/cron.env ] && set -a && . $HOME/.config/opencode/cron.env && set +a

RUN_TIMEOUT="20m"
RETRY_BASE=300          # backoff exponencial: 5min, 10min, 20min, teto 30min
RETRY_MAX=1800
QUOTA_STEPS=(900 1800 3600)   # quota: 15min -> 30min -> 1h, reseta ao dar certo
NORMAL_WAIT=1200
# Cadeia de modelos GRATUITOS, em ordem de preferencia. Toda rodada comeca pelo
# primeiro: por isso a volta ao preferido e automatica quando o limite dele passa,
# sem precisar detectar recuperacao nem guardar estado.
# Os 6 modelos GRATUITOS do Zen. Nada de OpenRouter: aquela conta tem credito
# limitado (US$1) e sem renovacao conhecida — parar de candidatar por credito
# esgotado seria pior que esperar um limite que reseta sozinho.
# Limite e POR MODELO e transitorio (medido: mimo dava 429 enquanto
# nemotron-3.5-lightning respondia normal) — e o que faz cascatear valer a pena.
# muse-spark-1.3 vem primeiro: e o unico com historico de completar rodadas reais
# (as 7 candidaturas de 13-14/09 sairam com ele).
# Todos rodam por API: consumo de RAM local = zero (a maquina tem 7.7G e ja usa swap).
# Ordem = capacidade decrescente. Navegar formulario (Gupy, LinkedIn) e onde
# modelo fraco erra, entao o maior vem primeiro; os menores sao rede de seguranca.
# Todos verificados em 14/09/2026 executando chamada de ferramenta de verdade.
# Segundo poco: modelos :free do OpenRouter. MEDIDO em 14/09/2026 que eles NAO consomem
# o credito de US$1 da conta (usage antes 0.019801999, depois 0.019801999; a propria API
# responde "cost": 0). O limite deles e de requisicoes/dia, nao de dinheiro.
# 1 = usa como segundo nivel, so depois que os 6 do Zen esgotarem. 0 = so Zen.
USAR_OPENROUTER=1

MODELOS=(
  "opencode/muse-spark-1.3-contributor-free"
  "opencode/nemotron-3-ultra-free"
  "opencode/nemotron-3.5-lightning-free"
  "opencode/mimo-v2.5-free"
  "opencode/muse-spark-1.2-contributor-free"
  "opencode/ling-3.0-flash-fin-free"
)

# Segundo nivel entra so no fim da fila: a preferencia pelo Zen fica preservada.
if [ "$USAR_OPENROUTER" = "1" ]; then
  MODELOS+=(
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    "openrouter/cohere/north-mini-code:free"
    "openrouter/nex-agi/nex-n2.5-pro:free"
  )
fi

# Terceiro nivel: NVIDIA direto (auth via auth.json, funciona no cron) e
# GitHub Copilot (consome premium requests do Student: 0 = desligado por padrao,
# ligue com USAR_COPILOT=1 se o resto secar; entra POR ULTIMO na fila).
USAR_NVIDIA=1
USAR_COPILOT=0
[ "$USAR_NVIDIA" = "1" ] && MODELOS+=("nvidia/nvidia/nemotron-3-super-120b-a12b")
[ "$USAR_COPILOT" = "1" ] && MODELOS+=("github-copilot/claude-sonnet-4.6")

WATCHDOG_AFTER=240        # limite maximo de espera do watchdog
WATCHDOG_MIN_WAIT=45      # antes disso nao aborta: rodada boa pode demorar a produzir saida
WATCHDOG_MIN_BYTES=800    # rodada que produziu menos que isso nao comecou de verdade
MONITOR_URL="https://sua-url.vercel.app"
LOG_MAX_BYTES=2097152   # 2MB -> rotaciona
ROUNDS_KEPT=20          # quantos logs completos de rodada manter
BROWSER_LOCK=/tmp/agent-chrome-9222.lock   # compartilhado com outro-robo/dia.sh

mkdir -p logs

# Instancia unica deste loop
exec 9>/tmp/candidaturas-loop.lock
if ! flock -n 9; then
  # Silencioso de proposito: o guardiao do cron chama este script a cada 5min so para
  # garantir que ele esta de pe. Quando ja esta, sair calado evita poluir o loop.log.
  exit 0
fi

rotate_log() {
  local size
  size=$(stat -c %s loop.log 2>/dev/null || echo 0)
  if [ "$size" -gt "$LOG_MAX_BYTES" ]; then
    mv loop.log "loop.log.1"
    : > loop.log
    echo "[$(date '+%F %T')] loop.log rotacionado (anterior em loop.log.1)" >> loop.log
  fi
  # mantem apenas as ultimas ROUNDS_KEPT rodadas completas
  ls -1t logs/rodada-*.log 2>/dev/null | tail -n +$((ROUNDS_KEPT + 1)) | xargs -r rm -f
}

log() {
  echo "[$(date '+%F %T')] $1" >> loop.log
  MONITOR_URL="$MONITOR_URL" CANDIDATURAS_ROOT=$HOME/candidaturas \
    "$NODE_BIN" $HOME/candidaturas/monitor/publish-once.mjs >/tmp/candidaturas-monitor.log 2>&1 9>&- &
}

ensure_chrome() {
  if curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null; then
    return 0
  fi
  log "Chrome CDP fora do ar, subindo novamente"
  DISPLAY=:0 nohup $HOME/chrome-real.sh >/tmp/chrome-real.log 2>&1 9>&- &
  sleep 6
  curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null
}

ensure_monitor() {
  pgrep -f "monitor/publish-status.mjs" >/dev/null && return 0
  MONITOR_URL="$MONITOR_URL" CANDIDATURAS_ROOT=$HOME/candidaturas \
    nohup "$NODE_BIN" $HOME/candidaturas/monitor/publish-status.mjs >/tmp/candidaturas-monitor.log 2>&1 9>&- &
}

# Quota so conta quando vem de linha de erro do provider ou do sentinel do prompt.
# Nunca varre o corpo da rodada (anuncio de vaga com "trial"/"credit" nao deve
# mandar o loop dormir 1h).
is_quota() {
  grep -qE '^[[:space:]]*QUOTA_EXAUSTA|Error from provider.*([Rr]ate limit|[Qq]uota|429|[Ee]xhausted|[Tt]oo [Mm]any)|AI_RetryError|RateLimitError' "$1"
}

# O opencode NAO imprime rate limit no stdout quando entra em retry silencioso:
# a rodada simplesmente trava ate o timeout. O erro so existe no log interno.
# Sem isto, rodada bloqueada por quota queima 20min de timeout + 5min de backoff, em loop.
OC_LOG_DIR=$HOME/.local/share/opencode/log
quota_in_opencode_log() {   # $1 = timestamp ISO do inicio da rodada
  local f
  f=$(ls -t "$OC_LOG_DIR"/*.log 2>/dev/null | head -1)
  [ -n "$f" ] || return 1
  awk -v since="$1" '
    /Rate limit exceeded|AI_RetryError|AI_APICallError|[Tt]oo [Mm]any [Rr]equests/ {
      if (match($0, /timestamp=[0-9T:.-]+Z/)) {
        ts = substr($0, RSTART + 10, RLENGTH - 10)
        if (ts >= since) found = 1
      }
    }
    END { exit(found ? 0 : 1) }
  ' "$f"
}

is_broken_session() {
  grep -qiE 'Session not found|session (expired|invalid)|invalid session' "$1"
}

fail_wait() {   # backoff exponencial com teto
  local n=$1 w=$RETRY_BASE
  while [ "$n" -gt 1 ]; do w=$((w * 2)); n=$((n - 1)); done
  [ "$w" -gt "$RETRY_MAX" ] && w=$RETRY_MAX
  echo "$w"
}

ensure_chrome || sleep "$RETRY_BASE"
ensure_monitor

FAILS=0
QUOTA_HITS=0

while true; do
  rotate_log
  if ! ensure_chrome; then
    FAILS=$((FAILS + 1))
    W=$(fail_wait "$FAILS")
    log "Chrome CDP indisponivel (falha ${FAILS}), nova tentativa em ${W}s"
    sleep "$W"
    continue
  fi
  ensure_monitor

  ROUND_LOG="logs/rodada-$(date '+%Y%m%d-%H%M%S').log"
  log "rodada iniciada"

  STATUS=0
  MODELO_OK=""
  TODOS_NO_LIMITE=1

  for MODELO in "${MODELOS[@]}"; do
  ROUND_START=$(date -u '+%Y-%m-%dT%H:%M:%S.000Z')
  # </dev/null: opencode le stdin; sem TTY isso gerava "EBADF: bad file descriptor".
  # 9>&-: nao vaza o fd do flock para o filho.
  # Sessao nova a cada rodada: o historico nao carrega nada que aplicadas.json nao tenha.
  setsid timeout --kill-after=30s "$RUN_TIMEOUT" \
    flock -w 900 -E 75 "$BROWSER_LOCK" \
    "$OPENCODE_BIN" run -m "$MODELO" --title "candidaturas-$(date '+%F-%H%M')" "$(cat prompt_loop.md)" \
    </dev/null 9>&- >"$ROUND_LOG" 2>&1 &
  ROUND_PID=$!

  # Watchdog: em rate limit o opencode trava calado e a rodada so morreria no timeout de 20min.
  # Se depois de WATCHDOG_AFTER o log interno acusar quota E a rodada nao tiver produzido nada,
  # aborta ja — recupera em 4min em vez de 20.
  (
    # O erro de rate limit aparece no log interno em menos de 1s. Em vez de dormir o
    # periodo inteiro, checa de 15 em 15s a partir de WATCHDOG_MIN_WAIT: rodada bloqueada
    # morre em ~45s em vez de 4min, o que torna viavel cascatear para o proximo modelo.
    esperado=0
    while [ "$esperado" -lt "$WATCHDOG_AFTER" ]; do
      sleep 15
      esperado=$((esperado + 15))
      [ "$esperado" -lt "$WATCHDOG_MIN_WAIT" ] && continue
      if quota_in_opencode_log "$ROUND_START" \
         && [ "$(stat -c %s "$ROUND_LOG" 2>/dev/null || echo 0)" -lt "$WATCHDOG_MIN_BYTES" ]; then
        kill -TERM -- "-$ROUND_PID" 2>/dev/null || kill -TERM "$ROUND_PID" 2>/dev/null
        break
      fi
    done
  ) 9>&- >/dev/null 2>&1 &
  WATCHDOG_PID=$!

  STATUS=0
  wait "$ROUND_PID" || STATUS=$?
  kill "$WATCHDOG_PID" 2>/dev/null
  wait "$WATCHDOG_PID" 2>/dev/null

    if is_quota "$ROUND_LOG" || quota_in_opencode_log "$ROUND_START"; then
      log "modelo ${MODELO} no limite, cascateando para o proximo"
      continue
    fi
    MODELO_OK="$MODELO"
    TODOS_NO_LIMITE=0
    break
  done

  [ -n "$MODELO_OK" ] && log "rodada usou o modelo ${MODELO_OK}"

  # loop.log fica legivel: so o fim da rodada. Dump completo vive em logs/.
  { echo "--- saida da rodada (completa em ${ROUND_LOG}) ---"; tail -n 40 "$ROUND_LOG"; } >> loop.log

  if is_broken_session "$ROUND_LOG"; then
    FAILS=$((FAILS + 1))
    W=$(fail_wait "$FAILS")
    log "sessao opencode invalida, nova tentativa em ${W}s"
    sleep "$W"
  elif [ "$TODOS_NO_LIMITE" -eq 1 ]; then
    IDX=$QUOTA_HITS
    [ "$IDX" -ge "${#QUOTA_STEPS[@]}" ] && IDX=$((${#QUOTA_STEPS[@]} - 1))
    W=${QUOTA_STEPS[$IDX]}
    QUOTA_HITS=$((QUOTA_HITS + 1))
    log "quota/limite: TODOS os ${#MODELOS[@]} modelos gratuitos no teto (${QUOTA_HITS}x seguidas), rechecando em ${W}s"
    sleep "$W"
  elif [ "$STATUS" -eq 124 ] || [ "$STATUS" -eq 137 ] || [ "$STATUS" -eq 143 ]; then
    FAILS=$((FAILS + 1))
    W=$(fail_wait "$FAILS")
    log "rodada estourou ${RUN_TIMEOUT} (ou foi morta), nova tentativa em ${W}s"
    sleep "$W"
  elif [ "$STATUS" -eq 75 ]; then
    log "outro agente segurou o Chrome por 15min (lock), tentando de novo em ${RETRY_BASE}s"
    sleep "$RETRY_BASE"
  elif [ "$STATUS" -ne 0 ]; then
    FAILS=$((FAILS + 1))
    W=$(fail_wait "$FAILS")
    log "opencode terminou com erro (status ${STATUS}), nova tentativa em ${W}s"
    sleep "$W"
  else
    FAILS=0
    QUOTA_HITS=0
    log "rodada ok, dormindo 20min"
    sleep "$NORMAL_WAIT"
  fi

  if [ "$FAILS" -ge 8 ]; then
    log "ALERTA: ${FAILS} falhas consecutivas — loop pode estar quebrado, verifique ${ROUND_LOG}"
  fi
done
