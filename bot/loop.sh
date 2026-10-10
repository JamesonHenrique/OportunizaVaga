#!/bin/bash
# Loop continuo de candidaturas (deixa o PC ligado). Sessao nova por rodada.
# Estado duravel vive em aplicadas.json, nao na sessao do opencode.
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT/bot" || exit 1

# Ajuste TZ ao seu fuso (ex.: America/Sao_Paulo). Sem isto, logs e datas gravadas saem
# com offset errado — foi o que fez candidaturas da noite virarem o dia seguinte.
export TZ=America/Fortaleza

# Binarios resolvidos explicitamente. O cron tem PATH minimo (/usr/bin:/bin) e NAO acha
# opencode (~/.opencode/bin) nem node (fnm): quando o guardiao reinicia este loop pelo
# cron, o `opencode`/`node` puro falha com "failed to execute opencode" -> status 69.
# (Foi exatamente isso que derrubava reinicios pelo cron.) Este loop so "funcionava"
# porque o processo atual herdou o PATH interativo; um restart pelo cron quebraria.
export PATH="$HOME/.opencode/bin:$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/bin:$PATH"
OPENCODE_BIN="$HOME/.opencode/bin/opencode"
NODE_BIN="$HOME/.local/share/fnm/aliases/default/bin/node"
[ -x "$OPENCODE_BIN" ] || { echo "[$(date '+%F %T')] ERRO: opencode nao encontrado em $OPENCODE_BIN" >> loop.log; exit 1; }
[ -x "$NODE_BIN" ]     || { echo "[$(date '+%F %T')] ERRO: node nao encontrado em $NODE_BIN" >> loop.log; exit 1; }

# Chaves de provedores que exigem env (OpenRouter): o cron nao herda o ambiente
# interativo, entao sem isto o segundo poco :free morre com erro de auth no cron.
# Arquivo 600, so nesta maquina, nunca commitado nem publicado.
[ -f "$HOME/.config/opencode/cron.env" ] && set -a && . "$HOME/.config/opencode/cron.env" && set +a

# Ritmo (pacing) — configuravel por env para uso mais "humano"/conservador.
# Defaults preservam o comportamento historico. Ver docs/USO-ETICO.md e
# config/pacing.example.env. Aumentar estes valores = menos requisicoes/hora.
RUN_TIMEOUT="${OV_RUN_TIMEOUT:-20m}"
RETRY_BASE="${OV_RETRY_BASE:-300}"          # backoff exponencial: 5min, 10min, 20min, teto 30min
RETRY_MAX="${OV_RETRY_MAX:-1800}"
QUOTA_STEPS=(900 1800 3600)   # quota: 15min -> 30min -> 1h, reseta ao dar certo
NORMAL_WAIT="${OV_NORMAL_WAIT:-1200}"         # sleep base apos rodada ok (20min)
VAZIA_BASE="${OV_VAZIA_BASE:-3600}"           # backoff por rodada sem vaga nova: 1h na primeira
VAZIA_MAX="${OV_VAZIA_MAX:-14400}"            # teto do backoff (4h): sem teto, 5 vazias seguidas = 16h parado
# Descoberta deterministica (sem LLM, opt-in): bot/descobrir.py monta uma fila de vagas
# pre-filtradas pelo perfil e o prompt da rodada as avalia ANTES de varrer o site do rodizio.
# Consulta LinkedIn/Gupy publicos a cada ~90min; ligue com OV_DESCOBRIR=1 (ver docs/USO-ETICO.md).
OV_DESCOBRIR="${OV_DESCOBRIR:-0}"
# Modelo PAGO so para rodadas com algo pronto para ENVIAR (fila com score >= 3 ou login ja feito):
# modelos gratuitos erram tool-call justamente ai. Opt-in: OV_USAR_PAGO_ENVIO=1 + OV_MODELO_PAGO=<id>.
# OV_PAGO_MAX_DIA limita as rodadas pagas por dia (o credito da conta e finito).
OV_USAR_PAGO_ENVIO="${OV_USAR_PAGO_ENVIO:-0}"
OV_MODELO_PAGO="${OV_MODELO_PAGO:-}"
OV_PAGO_MAX_DIA="${OV_PAGO_MAX_DIA:-2}"
# Rodada enxuta (opcional): JSON de config do opencode desligando MCPs que o loop nao usa (cada MCP
# custa dezenas de milhares de tokens de schema em TODA chamada). Ex.:
#   OV_OPENCODE_CONFIG_CONTENT='{"mcp":{"github":{"enabled":false},"context7":{"enabled":false}}}'
# So desligue MCPs que voce realmente tem configurados. Vazio = bot/opencode-enxuto.py monta a config enxuta a
# partir da sua propria config do opencode (OV_OPENCODE_ENXUTO=1 para ligar; desligado por padrao).
OV_OPENCODE_CONFIG_CONTENT="${OV_OPENCODE_CONFIG_CONTENT:-}"
# Cadeia de modelos GRATUITOS, em ordem de preferencia. Toda rodada comeca pelo
# primeiro: por isso a volta ao preferido e automatica quando o limite dele passa,
# sem precisar detectar recuperacao nem guardar estado.
# Os 6 modelos GRATUITOS do Zen. Nada de OpenRouter: aquela conta tem credito
# limitado (US$1) e sem renovacao conhecida — parar de candidatar por credito
# esgotado seria pior que esperar um limite que reseta sozinho.
# Limite e POR MODELO e transitorio (medido: mimo dava 429 enquanto
# nemotron-3.5-lightning respondia normal) — e o que faz cascatear valer a pena.
# nex-n2.5-pro vem primeiro enquanto muse-spark-1.3 estiver no limite; a volta
# ao preferido historico e automatica quando a cota dele reseta.
# Todos rodam por API: consumo de RAM local = zero (a maquina tem 7.7G e ja usa swap).
# Ordem = capacidade decrescente. Navegar formulario (Gupy, LinkedIn) e onde
# modelo fraco erra, entao o maior vem primeiro; os menores sao rede de seguranca.
# Todos verificados em 14/09/2026 executando chamada de ferramenta de verdade.
# Segundo poco: modelos :free do OpenRouter. MEDIDO em 14/09/2026 que eles NAO consomem
# o credito de US$1 da conta (usage antes 0.019801999, depois 0.019801999; a propria API
# responde "cost": 0). O limite deles e de requisicoes/dia, nao de dinheiro.
# 1 = usa como segundo nivel, so depois que os 6 do Zen esgotarem. 0 = so Zen.
USAR_OPENROUTER=1

# Measured on a real instance (7 days, ~300 rounds): space-bunny 83 rounds with 0 unproductive sessions;
# muse-spark-1.3 64 unproductive out of 85, nemotron-3-ultra 53, mimo-v2.6 54; nemotron-3.5-lightning caused
# most of the 20-min timeouts. bot/modelos-saude.py reorders by real success anyway; names the installed
# opencode no longer lists are dropped at start.
MODELOS=(
  "opencode/space-bunny-free"
  "openrouter/thinkingmachines/inkling:free"
  "openrouter/nex-agi/nex-n2.5-pro:free"
  "opencode/muse-spark-1.3-contributor-free"
  "opencode/nemotron-3-ultra-free"
  "opencode/nemotron-3.5-lightning-free"
  "opencode/mimo-v2.5-free"
  "opencode/muse-spark-1.2-contributor-free"
  "opencode/ling-3.0-flash-fin-free"
)

# Segundo nivel: :free do OpenRouter (NAO consome o credito da conta, limite e de
# requisicoes/dia — medido cost=0). Ordem por capacidade de codigo.
if [ "$USAR_OPENROUTER" = "1" ]; then
  MODELOS+=(
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    "openrouter/z-ai/glm-5.2:free"
    "openrouter/poolside/laguna-s-2.1:free"
    "openrouter/thinkingmachines/inkling:free"
    "openrouter/cohere/north-mini-code:free"
    "openrouter/nex-agi/nex-n2.5-pro:free"
    "openrouter/dots-studio/dots-3-note-preview:free"
    "openrouter/nvidia/nemotron-3.5-lightning:free"
  )
fi

# Terceiro nivel: NVIDIA direto (auth via auth.json, funciona no cron).
USAR_NVIDIA=1
[ "$USAR_NVIDIA" = "1" ] && MODELOS+=("nvidia/nvidia/nemotron-3-super-120b-a12b")

# Quarto nivel: Groq (gratis, sem cartao; limite de req/dia por modelo).
USAR_GROQ=1
if [ "$USAR_GROQ" = "1" ]; then
  MODELOS+=(
    "groq/openai/gpt-oss-120b"
    "groq/qwen/qwen3.8-27b"
    "groq/openai/gpt-oss-20b"
    "groq/meta-llama/llama-3.3-70b-versatile"
  )
fi

# Quinto nivel: Cerebras (gratis; dois modelos open).
USAR_CEREBRAS=1
if [ "$USAR_CEREBRAS" = "1" ]; then
  MODELOS+=(
    "cerebras/gpt-oss-120b"
    "cerebras/qwen-3.8-27b"
  )
fi

# Sexto nivel: Hugging Face Inference Providers (gratis; inferencia serverless).
USAR_HF=1
if [ "$USAR_HF" = "1" ]; then
  MODELOS+=(
    "huggingface/deepseek-ai/DeepSeek-V4-Pro"
    "huggingface/deepseek-ai/DeepSeek-V3.2"
    "huggingface/google/gemma-3-27b-it"
  )
fi

# Ultimo nivel: GitHub Copilot (consome premium requests do Student: 0 = desligado
# por padrao, ligue com USAR_COPILOT=1 se o resto secar; entra POR ULTIMO na fila).
USAR_COPILOT=0
[ "$USAR_COPILOT" = "1" ] && MODELOS+=("github-copilot/claude-sonnet-4.6")

# Descarta modelos que o opencode nao lista mais (nome morto gasta uma vaga da cascata ou quebra a
# rodada). Suave: se a listagem falhar, mantem a lista como esta.
AVAILABLE_MODELS=$(timeout 30 "$OPENCODE_BIN" models 2>/dev/null)
if [ -n "$AVAILABLE_MODELS" ]; then
  MODELOS_VALIDOS=()
  for M in "${MODELOS[@]}"; do
    if printf '%s\n' "$AVAILABLE_MODELS" | grep -Fxq "$M"; then
      MODELOS_VALIDOS+=("$M")
    else
      echo "[$(date '+%F %T')] modelo indisponivel removido da cascata: $M" >> loop.log
    fi
  done
  [ "${#MODELOS_VALIDOS[@]}" -gt 0 ] && MODELOS=("${MODELOS_VALIDOS[@]}")
fi

WATCHDOG_AFTER=240        # limite maximo de espera do watchdog
WATCHDOG_MIN_WAIT=45      # antes disso nao aborta: rodada boa pode demorar a produzir saida
WATCHDOG_STALL="${OV_WATCHDOG_STALL:-90}"   # quota no meio da rodada + saida parada ha Ns -> aborta e cascateia
WATCHDOG_MIN_BYTES=800    # rodada que produziu menos que isso nao comecou de verdade
WATCHDOG_HANG=${OV_WATCHDOG_HANG:-360}   # nenhuma saida por 6 min (sem erro do provider) = ferramenta travada -> aborta
PORTAO_ESPERA=${OV_PORTAO_ESPERA:-1800}  # portao disse "nada a fazer": pergunta de novo em 30 min
MONITOR_URL="${MONITOR_URL:-https://sua-url.vercel.app}"
LOG_MAX_BYTES=2097152   # 2MB -> rotaciona
ROUNDS_KEPT=20          # quantos logs completos de rodada manter
BROWSER_LOCK=/tmp/agent-chrome-9222.lock   # lock do Chrome compartilhado entre agentes locais

# Perfil ativo e estado isolado. Sem BOT_PERFIL/perfil.json, o comportamento
# historico permanece em bot/aplicadas.json.
PERFIL_FILE="${BOT_PERFIL:-}"
if [ -z "$PERFIL_FILE" ] && [ -f "$BOT_ROOT/bot/perfil.json" ]; then
  PERFIL_FILE="$BOT_ROOT/bot/perfil.json"
fi
if [ -n "$PERFIL_FILE" ] && [ ! -f "$PERFIL_FILE" ]; then
  echo "[$(date '+%F %T')] ERRO: perfil nao encontrado: $PERFIL_FILE" >> loop.log
  exit 1
fi
if [ -n "$PERFIL_FILE" ]; then
  # Perfil ilegivel PARA o loop: antes o nome saia vazio, o slug virava "perfil" e um estado
  # novo (vazio) era semeado do exemplo — historico sumia e vagas ja enviadas voltavam.
  if ! PERFIL_NOME="$(python3 - "$PERFIL_FILE" 2>&1 <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
if not isinstance(d, dict):
    sys.exit('o JSON precisa ser um objeto')
print(d.get('nome_perfil', 'perfil'))
PY
)"; then
    echo "[$(date '+%F %T')] ERRO: perfil invalido ($PERFIL_FILE): $(printf '%s' "$PERFIL_NOME" | tail -1)" >> loop.log
    exit 1
  fi
  PERFIL_SLUG="$(printf '%s' "$PERFIL_NOME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48)"
  [ -n "$PERFIL_SLUG" ] || PERFIL_SLUG="perfil"
  STATE_DIR="$BOT_ROOT/bot/state/$PERFIL_SLUG"
else
  PERFIL_NOME="default"
  PERFIL_SLUG="default"
  STATE_DIR="$BOT_ROOT/bot"
fi
APLICADAS_FILE="$STATE_DIR/aplicadas.json"
DADOS_CANDIDATO_FILE="$BOT_ROOT/bot/dados_candidato.json"
RUNTIME_PROMPT="$STATE_DIR/prompt_loop.runtime.md"
RECONHECIMENTO_FILE="$STATE_DIR/reconhecimento-$(date '+%Y%m%d-%H%M%S').json"
export BOT_PERFIL="$PERFIL_FILE" PERFIL_FILE PERFIL_NOME PERFIL_SLUG STATE_DIR APLICADAS_FILE DADOS_CANDIDATO_FILE RUNTIME_PROMPT RECONHECIMENTO_FILE
export OV_RECONHECIMENTO="${OV_RECONHECIMENTO:-0}"
export OV_MAX_CANDIDATURAS="${OV_MAX_CANDIDATURAS:-3}"
export OV_RECONHECIMENTO_LIMIT="${OV_RECONHECIMENTO_LIMIT:-10}"
export OV_TELEMETRY_MODE="${OV_TELEMETRY_MODE:-aggregate}"
export OV_MONITOR_INCLUDE_DETAILS="${OV_MONITOR_INCLUDE_DETAILS:-0}"
mkdir -p "$STATE_DIR"
if [ ! -f "$APLICADAS_FILE" ]; then
  # Estado novo e vazio: legitimo na 1a execucao, perigoso se o nome do perfil mudou (o historico
  # fica no slug antigo e o anti-duplicata nao o ve). Deixa rastro no log em vez de seguir calado.
  outros="$(find "$BOT_ROOT/bot/state" -mindepth 2 -maxdepth 2 -name aplicadas.json ! -path "$APLICADAS_FILE" 2>/dev/null | head -3 | tr '\n' ' ')"
  [ -f "$BOT_ROOT/bot/aplicadas.json" ] && [ "$APLICADAS_FILE" != "$BOT_ROOT/bot/aplicadas.json" ] && outros="$outros$BOT_ROOT/bot/aplicadas.json"
  cp "$BOT_ROOT/examples/aplicadas.example.json" "$APLICADAS_FILE"
  if [ -n "$outros" ]; then
    echo "[$(date '+%F %T')] AVISO: estado novo criado em $APLICADAS_FILE (perfil '$PERFIL_NOME'); ja existe historico em: $outros— se o nome_perfil mudou, mova o estado antigo para ca." >> loop.log
  fi
fi
mkdir -p logs

# Instancia unica deste loop
exec 9>/tmp/oportunizavaga-loop.lock
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
  # page snapshots/console dumps of the browser MCP (~20 MB/day, some with filled-in forms = personal data);
  # nothing reads them after the round: keep 2 days
  find .playwright-mcp "$BOT_ROOT/.playwright-mcp" -maxdepth 1 -type f -mtime +1 -delete 2>/dev/null || true
}

log() {
  echo "[$(date '+%F %T')] $1" >> loop.log
  MONITOR_URL="$MONITOR_URL" CANDIDATURAS_ROOT="$BOT_ROOT/bot" \
    "$NODE_BIN" "$BOT_ROOT/monitor/publish-once.mjs" >/tmp/oportunizavaga-monitor.log 2>&1 9>&- &
}

ensure_chrome() {
  if curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null; then
    return 0
  fi
  log "Chrome CDP fora do ar, subindo novamente"
  DISPLAY=:0 nohup "$BOT_ROOT/browser/chrome-real.sh" >/tmp/chrome-real.log 2>&1 9>&- &
  sleep 6
  curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null
}

ensure_monitor() {
  pgrep -f "monitor/publish-status.mjs" >/dev/null && return 0
  MONITOR_URL="$MONITOR_URL" CANDIDATURAS_ROOT="$BOT_ROOT/bot" \
    nohup "$NODE_BIN" "$BOT_ROOT/monitor/publish-status.mjs" >/tmp/oportunizavaga-monitor.log 2>&1 9>&- &
}

# Quota no log da rodada vem de is_quota(), em prompt_cond/../opencode-erros.sh: esta linha estava
# copiada aqui e nos dois installs privados (04/10, cap 121 F4).
# O opencode NAO imprime rate limit no stdout quando entra em retry silencioso: o erro so existe no log
# interno. bot/lib/opencode-erros.sh separa COTA de erro TRANSITORIO (503, timeout de cabecalho, sobrecarga):
# antes qualquer AI_APICallError contava como cota e punha o melhor modelo em resfriamento por um 503.
. "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/lib/opencode-erros.sh"
quota_in_opencode_log() {   # $1 = timestamp ISO do inicio da rodada; so COTA real
  [ "$(erro_opencode_log "$1" "$PWD")" = "quota" ]
}

# Impressao digital do estado: hash de toda CHAVE de vaga que o robo registrou (aplicadas,
# bloqueados, quase_la, aguardando_login). Descartes de listagem NAO contam como novidade: contar
# fazia quase toda rodada parecer "com vaga nova" e o backoff de rodada vazia nunca disparava.
fingerprint() {
  python3 - "$1" <<'PY'
import hashlib, json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as fh:
        d = json.load(fh)
    ks = sorted(str(a.get('chave')) for a in d.get('aplicadas', []) if isinstance(a, dict))
    for sec in ('bloqueados', 'quase_la', 'aguardando_login'):
        v = d.get(sec)
        if isinstance(v, dict):
            ks += sorted(f'{sec}:{k}' for k in v)
    print(hashlib.md5('|'.join(ks).encode()).hexdigest()[:16])
except Exception:
    print('-1')
PY
}

# Algo pronto para ENVIAR nesta rodada: fila da descoberta com score >= 3 ou (se o estado tiver a
# secao) vaga aguardando login cujo canal ja esta logado. Usado p/ escolher o modelo pago (opt-in)
# e para nao dormir horas em cima de uma fila que ainda tem vaga boa.
tem_envio_pronto() {
  python3 - "$APLICADAS_FILE" "$STATE_DIR/vagas_fila.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    chk = d.get('login_checagens') or {}
    if any((chk.get(v.get('canal')) or {}).get('logado') == 'sim' for v in (d.get('aguardando_login') or {}).values() if isinstance(v, dict)):
        sys.exit(0)
    f = json.load(open(sys.argv[2], encoding='utf-8'))
    sys.exit(0 if any(v.get('status') == 'nova' and v.get('score', 0) >= 3 for v in f.get('vagas', {}).values()) else 1)
except Exception:
    sys.exit(1)
PY
}

render_prompt() {
  python3 - "$BOT_ROOT/bot/prompt_loop.md" "$RUNTIME_PROMPT" "$APLICADAS_FILE" "$DADOS_CANDIDATO_FILE" "$PERFIL_FILE" "$PERFIL_NOME" "$RECONHECIMENTO_FILE" "$OV_RECONHECIMENTO" "$OV_MAX_CANDIDATURAS" "$OV_RECONHECIMENTO_LIMIT" "$BOT_ROOT" <<'PY'
from pathlib import Path
import sys

source, target, aplicadas, dados, perfil, perfil_nome, reconhecimento, modo, limite, limite_reconhecimento, bot_root = sys.argv[1:]
text = Path(source).read_text(encoding='utf-8')
sys.path.insert(0, str(Path(bot_root) / 'bot'))
import prompt_cond
# Conditional blocks (<!--se:site=X-->...<!--/se-->, <!--se:telegram-->): keep only what this round can use.
text = prompt_cond.aplicar(text, prompt_cond.site_da_rodada(aplicadas), prompt_cond.telegram_para_prompt(Path(aplicadas).parent))
import os as _os
SO_FILA = _os.environ.get('OV_SO_FILA') == '1'   # bot/rodada-portao.py: no site scan this round
if SO_FILA:
    text = prompt_cond.so_fila(text)
text = text.replace('$APLICADAS_FILE', aplicadas)
text = text.replace('$DADOS_CANDIDATO_FILE', dados)
text = text.replace('$BOT_ROOT', bot_root)
text = text.replace('bot/perfil.json', perfil)
text = text.replace('SEU_NOME', perfil_nome)
text = text.replace('YOUR_NAME', perfil_nome)
# Nivel/area/termos do perfil ativo -> placeholders {{...}} (bot/perfil_render.py).
import perfil_render
text = perfil_render.render(text, perfil_render.carregar(perfil))
if modo in {'1', 'true', 'True', 'sim', 'Sim'}:
    text += '''\n\nMODO RECONHECIMENTO (obrigatorio): NAO se candidate, NAO preencha formulario, NAO envie mensagem, NAO altere aplicadas.json. Avalie no maximo %s vagas recentes do site da rodada e grave somente %s com schema compativel com config/reconhecimento.schema.json. Use chave estavel site+vaga, score 0-5, URL, empresa, vaga, remota, nivel, stack, motivos e observacoes; nunca inclua dados pessoais.\n''' % (limite_reconhecimento, reconhecimento)
else:
    text += '''\n\nPERFIL ATIVO: %s. Use somente os termos, filtros e estado deste perfil. O limite desta rodada e %s candidaturas novas.\n''' % (perfil_nome, limite)
# RESUMO DO ESTADO: gerado agora via estado.py (compacto) em vez do agente ler
# o aplicadas.json inteiro (arquivo de estado pode dominar os tokens de uma rodada).
try:
    import subprocess
    res = subprocess.run([sys.executable, str(Path(bot_root) / 'bot' / 'estado.py'), '--file', aplicadas, 'resumo'],
                         capture_output=True, text=True, timeout=30)
    if res.returncode == 0 and res.stdout.strip():
        text += '\n\nRESUMO DO ESTADO (gerado agora de ' + aplicadas + '; NAO leia o arquivo inteiro)\n' + res.stdout
except Exception:
    pass
# RESUMO DO CANDIDATO: the fields forms ask for; the model used to read the whole dados_candidato.json
# (~10 KB) in half the sessions and keep it in context for every later call. The rest: estado.py dado CAMPO.
try:
    rc = subprocess.run([sys.executable, str(Path(bot_root) / 'bot' / 'estado.py'), 'resumo-candidato'], capture_output=True,
                        text=True, timeout=30, env=dict(_os.environ, DADOS_CANDIDATO_FILE=dados))
    if rc.returncode == 0 and rc.stdout.strip():
        text += ('\n\nRESUMO DO CANDIDATO (de ' + dados + '; NAO leia o arquivo inteiro — campo fora daqui: python3 '
                 + str(Path(bot_root) / 'bot' / 'estado.py') + ' dado CAMPO[.SUB])\n' + rc.stdout)
except Exception:
    pass
# Blocos extras (so em rodada normal, nunca no modo reconhecimento: o "prompt" conta uma oferta
# por vaga). Cada um e best-effort: falha silenciosa nunca impede a rodada.
if modo not in {'1', 'true', 'True', 'sim', 'Sim'}:
    import json as _json, os, subprocess
    # Termos da rodada: sessao nova nao tem memoria, entao o loop rotaciona os termos do perfil
    # com um contador persistente (2 termos por rodada).
    try:
        termos = [] if SO_FILA else (perfil_render.carregar(perfil).get('termos') or [])
        termos = [t for t in termos if isinstance(t, str) and t.strip()]
        if termos:
            idx_file = Path(aplicadas).parent / 'termo_idx'
            try:
                idx = int(idx_file.read_text().strip())
            except Exception:
                idx = 0
            escolhidos = [termos[(idx + i) % len(termos)] for i in range(min(2, len(termos)))]
            idx_file.write_text(str((idx + 2) % len(termos)))
            text += "\n\nTERMOS DESTA RODADA (use ESTES, nesta ordem, no site do rodizio): " + " | ".join(escolhidos) + "\n"
    except Exception:
        pass
    cmds = []
    if os.environ.get('OV_DESCOBRIR') == '1':
        cmds.append([sys.executable, str(Path(bot_root) / 'bot' / 'descobrir.py'), 'prompt', '5'])
    if (Path(aplicadas).parent / 'telegram_vagas.json').exists():
        cmds.append([sys.executable, str(Path(bot_root) / 'bot' / 'tg-garimpo.py'), 'prompt', '3'])
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                # Titles/companies/posts come from third parties: fenced as DATA (rule 9 of the prompt).
                text += prompt_cond.cercar('fila' if 'descobrir' in cmd[1] else 'telegram', r.stdout)
        except Exception:
            pass
Path(target).write_text(text, encoding='utf-8')
PY
}

# Backoff por rodada vazia: 1h na primeira e dobra a cada rodada vazia seguinte
# (3600 -> 7200 -> 14400), com teto em VAZIA_MAX. Reseta ao achar vaga nova.
vazia_wait() {   # $1 = rodadas vazias seguidas (1 = primeira)
  local w=$VAZIA_BASE n=$(( $1 - 1 ))
  while [ "$n" -gt 0 ]; do w=$((w * 2)); n=$((n - 1)); done
  [ "$w" -gt "$VAZIA_MAX" ] && w=$VAZIA_MAX
  echo "$w"
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
VAZIAS=0

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
  # Round id: estado.py stamps it as "rodada" on records; descobrir.py marcar uses it for "caminho" (fila|rodizio).
  OV_RODADA=$(basename "$ROUND_LOG" .log); OV_RODADA=${OV_RODADA#rodada-}; export OV_RODADA
  # Descoberta deterministica (opt-in, sem LLM; a coleta respeita o intervalo dentro do script):
  # enche <estado>/vagas_fila.json, que o render_prompt injeta no prompt.
  if [ "$OV_DESCOBRIR" = "1" ]; then
    timeout 180 python3 "$BOT_ROOT/bot/descobrir.py" coletar >> loop.log 2>&1 || log "descobrir: coleta falhou (segue sem fila)"
    # Pre-read the next jobs (closed posting, profile link, already registered, description/official level)
    # BEFORE the gate, so a queue the model would only discard opens no session.
    timeout 120 python3 "$BOT_ROOT/bot/descobrir.py" triar 8 >> loop.log 2>&1 || log "descobrir: triagem falhou (segue sem ela)"
  fi
  # Round gate (opt-in OV_PORTAO=1, bot/rodada-portao.py): no model session when there is nothing to do;
  # queue-only round (no site scan) when no site is due. Fail-open: an error means a normal round.
  OV_SO_FILA=0
  if [ "${OV_PORTAO:-0}" = "1" ]; then
    PORTAO=$(APLICADAS_FILE="$APLICADAS_FILE" python3 "$BOT_ROOT/bot/rodada-portao.py" "$APLICADAS_FILE" 2>>loop.log || echo "completa portao sem resposta")
    case "${PORTAO%% *}" in
      pular) log "portao: ${PORTAO#* } — sem sessao de modelo, reavaliando em $((PORTAO_ESPERA / 60))min"; sleep "$PORTAO_ESPERA"; continue ;;
      so_fila) OV_SO_FILA=1; log "portao: rodada SO FILA (${PORTAO#* })" ;;
      *) log "portao: ${PORTAO#* }" ;;
    esac
  fi
  export OV_SO_FILA
  # Rotation snapshot AFTER the gate: when the gate moves the rotation to the site that is due, `pos` must credit
  # that site (ultima_varredura) — taken before, it credited the old one and the scanned site stayed "due".
  python3 "$BOT_ROOT/bot/rodizio-saude.py" pre "$APLICADAS_FILE" --perfil "$PERFIL_FILE" >> loop.log 2>&1 || true
  render_prompt
  FP_ANTES=$(fingerprint "$APLICADAS_FILE")
  log "rodada iniciada (perfil ${PERFIL_NOME}, rodadas vazias seguidas: ${VAZIAS})"

  STATUS=0
  MODELO_OK=""
  TODOS_NO_LIMITE=1
  IMPRODUTIVA=0

  # Cooldown por modelo (evita recascatear pelo mesmo modelo esgotado a cada rodada,
  # cada tentativa custa ~dezenas de segundos so p/ redescobrir o mesmo limite).
  COOLDOWN_FILE="$STATE_DIR/model_cooldown"
  AGORA_S=$(date +%s)
  CASCATA=()
  # Adaptive order: best success rate first, useless models benched (bot/modelos-saude.py); fail-open to MODELOS.
  MODELOS_ORD=()
  if [ "${OV_MODELOS_SAUDE:-1}" = "1" ]; then
    mapfile -t MODELOS_ORD < <(python3 "$BOT_ROOT/bot/modelos-saude.py" ordenar "${MODELOS[@]}" 2>>loop.log)
  fi
  [ "${#MODELOS_ORD[@]}" -gt 0 ] || MODELOS_ORD=("${MODELOS[@]}")
  for M in "${MODELOS_ORD[@]}"; do
    ATE=$(awk -v m="$M" '$1==m {print $2}' "$COOLDOWN_FILE" 2>/dev/null | tail -1)
    [ -n "$ATE" ] && [ "$ATE" -gt "$AGORA_S" ] && continue
    CASCATA+=("$M")
  done
  [ "${#CASCATA[@]}" -eq 0 ] && CASCATA=("${MODELOS_ORD[@]}")   # todos em resfriamento: tenta assim mesmo
  # Modelo pago (opt-in) na frente da cascata so quando ha algo pronto para enviar, ate OV_PAGO_MAX_DIA/dia.
  if [ "$OV_USAR_PAGO_ENVIO" = "1" ] && [ -n "$OV_MODELO_PAGO" ] && tem_envio_pronto; then
    PAGO_HOJE=$(awk -v d="$(date +%F)" '$1==d {print $2}' "$STATE_DIR/pago_dia" 2>/dev/null | tail -1)
    if [ "${PAGO_HOJE:-0}" -lt "$OV_PAGO_MAX_DIA" ]; then
      CASCATA=("$OV_MODELO_PAGO" "${CASCATA[@]}")
      echo "$(date +%F) $(( ${PAGO_HOJE:-0} + 1 ))" >> "$STATE_DIR/pago_dia"
      log "rodada com envio pronto: ${OV_MODELO_PAGO} na frente da cascata ($(( ${PAGO_HOJE:-0} + 1 ))/${OV_PAGO_MAX_DIA} hoje)"
    fi
  fi
  [ "${#CASCATA[@]}" -lt "${#MODELOS_ORD[@]}" ] && log "cascata sem $(( ${#MODELOS_ORD[@]} - ${#CASCATA[@]} )) modelo(s) em resfriamento"

  CI=0; REPETIU=""
  while [ "$CI" -lt "${#CASCATA[@]}" ]; do
  MODELO=${CASCATA[$CI]}; CI=$((CI + 1))
  ROUND_START=$(date -u '+%Y-%m-%dT%H:%M:%S.000Z')
  # elapsed-time clock read by the model (bot/tempo-rodada.py, prompt rule 7d)
  mkdir -p "$STATE_DIR"; date +%s > "$STATE_DIR/rodada_inicio"; rm -f "$STATE_DIR/rodada_travou"
  # </dev/null: opencode le stdin; sem TTY isso gerava "EBADF: bad file descriptor".
  # 9>&-: nao vaza o fd do flock para o filho.
  # Sessao nova a cada rodada: o historico nao carrega nada que aplicadas.json nao tenha.
  # Rodada enxuta: OPENCODE_CONFIG_CONTENT desliga MCPs/ferramentas que o loop nao usa. Precedencia:
  # OV_OPENCODE_CONFIG_CONTENT (explicito) > bot/opencode-enxuto.py (le a SUA config; OV_OPENCODE_ENXUTO=1 liga (desligado por padrão))
  # > nada. Fail-open: script sem saida = config do opencode intacta.
  OC_CFG="$OV_OPENCODE_CONFIG_CONTENT"
  [ -n "$OC_CFG" ] || OC_CFG="$(python3 "$BOT_ROOT/bot/opencode-enxuto.py" 2>>loop.log)"
  OC_ENV=()
  [ -n "$OC_CFG" ] && OC_ENV=(OPENCODE_CONFIG_CONTENT="$OC_CFG")
  setsid env "${OC_ENV[@]}" timeout --kill-after=30s "$RUN_TIMEOUT" \
    env CHROME_LOCK_YIELD_RC=75 CHROME_LOCK_FILE="$BROWSER_LOCK" "$BOT_ROOT/bot/chrome-lock.sh" loop normal 900 -- \
    "$OPENCODE_BIN" run -m "$MODELO" --title "candidaturas-$(date '+%F-%H%M')" "$(cat "$RUNTIME_PROMPT")" \
    </dev/null 9>&- >"$ROUND_LOG" 2>&1 &
  ROUND_PID=$!

  # Watchdog: em rate limit o opencode trava calado e a rodada so morreria no timeout de 20min.
  # Aborta cedo em dois casos: (1) quota cedo e a rodada nao produziu nada ainda; (2) quota no
  # MEIO da rodada com a saida parada ha WATCHDOG_STALL segundos (ficaria pendurado ate o timeout).
  (
    # O erro de rate limit aparece no log interno em menos de 1s. Em vez de dormir o
    # periodo inteiro, checa de 15 em 15s a partir de WATCHDOG_MIN_WAIT: rodada bloqueada
    # morre bem antes do timeout, o que torna viavel cascatear para o proximo modelo.
    esperado=0
    ultimo_tam=0
    parado=0
    # runs for the whole round (the loop kills it after wait); before, it stopped after WATCHDOG_AFTER and a
    # stall in the middle of the round hung until RUN_TIMEOUT.
    while true; do
      sleep 15
      esperado=$((esperado + 15))
      tam=$(stat -c %s "$ROUND_LOG" 2>/dev/null || echo 0)
      if [ "$tam" -eq "$ultimo_tam" ]; then parado=$((parado + 15)); else parado=0; ultimo_tam=$tam; fi
      [ "$esperado" -lt "$WATCHDOG_MIN_WAIT" ] && continue
      # any provider error (quota OR transient) + no output = the run is stuck: abort and let the loop go on
      if { [ "$tam" -lt "$WATCHDOG_MIN_BYTES" ] || [ "$parado" -ge "$WATCHDOG_STALL" ]; } \
         && [ -n "$(erro_opencode_log "$ROUND_START" "$PWD")" ]; then
        kill -TERM -- "-$ROUND_PID" 2>/dev/null || kill -TERM "$ROUND_PID" 2>/dev/null
        break
      fi
      # no output at all for WATCHDOG_HANG s and no provider error = a hung tool (e.g. a file upload that never
      # returns): abort now instead of waiting for RUN_TIMEOUT; the loop retries the same model once.
      if [ "$parado" -ge "$WATCHDOG_HANG" ]; then
        echo "$parado" > "$STATE_DIR/rodada_travou"
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

    ERRO_PROV=$(erro_opencode_log "$ROUND_START" "$PWD")
    if [ "$ERRO_PROV" = "transitorio" ] && [ "$REPETIU" != "$MODELO" ] && [ "$STATUS" -ne 75 ]; then
      REPETIU="$MODELO"; CI=$((CI - 1))
      log "modelo ${MODELO}: erro transitorio do provider (5xx/timeout), repetindo o MESMO modelo em 60s (sem resfriamento)"
      sleep 60
      continue
    fi
    if [ -f "$STATE_DIR/rodada_travou" ] && [ "$REPETIU" != "$MODELO" ]; then
      REPETIU="$MODELO"; CI=$((CI - 1))
      log "modelo ${MODELO}: rodada sem saida por $(cat "$STATE_DIR/rodada_travou")s (ferramenta travada), repetindo com o mesmo modelo"
      continue
    fi
    if [ "$ERRO_PROV" = "quota" ] || { [ "$ERRO_PROV" != "transitorio" ] && is_quota "$ROUND_LOG"; }; then
      log "modelo ${MODELO} no limite, cascateando para o proximo"
      mkdir -p "$STATE_DIR"
      echo "$MODELO $(( $(date +%s) + 5400 ))" >> "$COOLDOWN_FILE"
      tail -n 50 "$COOLDOWN_FILE" > "$COOLDOWN_FILE.tmp" && mv "$COOLDOWN_FILE.tmp" "$COOLDOWN_FILE"
      continue
    fi
    # Sessao improdutiva = falha do modelo, nao "rodada vazia" (modelo fraco que encerra sem
    # navegar ou imprime a tool-call como texto): nao deve contar no backoff de 1h+ de vaga
    # nova nem pausar site por falta de retorno.
    if [ "$STATUS" -ne 75 ] && ! grep -q "browser_navigate" "$ROUND_LOG" 2>/dev/null; then
      if grep -qE "<tool_call>|<function=|<parameter=" "$ROUND_LOG" 2>/dev/null; then
        log "modelo ${MODELO} quebrou o formato de tool-call, cascateando para o proximo"
      else
        log "modelo ${MODELO} encerrou sem navegar (sessao improdutiva), cascateando para o proximo"
      fi
      IMPRODUTIVA=1
      continue
    fi
    # Sessao que morreu logo apos uma tool-call com erro (ex.: alvo de clique invalido; a rodada
    # termina em "Error:" sem resumo final). Ela navegou, entao o teste acima deixa passar e o
    # loop dormiria horas sem ter feito o trabalho: cascateia para o proximo modelo.
    if [ "$STATUS" -ne 75 ] && tail -n 8 "$ROUND_LOG" 2>/dev/null | grep -qE "Error: |^.{0,12}✗ "; then
      log "modelo ${MODELO} morreu apos erro de ferramenta (sem resumo final), cascateando para o proximo"
      IMPRODUTIVA=1
      continue
    fi
    IMPRODUTIVA=0
    MODELO_OK="$MODELO"
    TODOS_NO_LIMITE=0
    break
  done

  [ -n "$MODELO_OK" ] && log "rodada usou o modelo ${MODELO_OK}"

  # A rodada acabou e o opencode fechou o log: mascara segredos AGORA (antes do tail ir para o loop.log),
  # sem esperar a varredura do cron. Falha aqui nunca derruba o loop.
  python3 "$BOT_ROOT/bot/redact-logs.py" --forcar "$ROUND_LOG" >> loop.log 2>&1 || true

  # loop.log fica legivel: so o fim da rodada. Dump completo vive em logs/.
  { echo "--- saida da rodada (completa em ${ROUND_LOG}) ---"; tail -n 40 "$ROUND_LOG"; } >> loop.log

  # O agente as vezes grava log_rodada_* em aplicadas.json; arquiva pra logs/rodadas.jsonl
  # (o resumo de estado nao precisa cargar esse historico a cada rodada).
  python3 "$BOT_ROOT/bot/arquivar-logs-rodada.py" "$APLICADAS_FILE" "$BOT_ROOT/bot/logs/rodadas.jsonl" >> loop.log 2>&1 || true

  # Fecha na fila as vagas que o robo registrou (ou ofertou demais); barato e idempotente.
  if [ "$OV_DESCOBRIR" = "1" ]; then
    python3 "$BOT_ROOT/bot/descobrir.py" marcar "$ROUND_LOG" >> loop.log 2>&1 || true
  fi
  # Checagem semantica do estado apos cada rodada (o monitor le a ultima linha do log).
  if [ -f "$BOT_ROOT/scripts/validate-rodada.py" ]; then
    if python3 "$BOT_ROOT/scripts/validate-rodada.py" "$APLICADAS_FILE" >> validate-rodada.log 2>&1; then
      echo "validate-rodada: OK ($(date '+%F %T'))" >> validate-rodada.log
    else
      log "ALERTA: validate-rodada reprovou o estado (ver bot/validate-rodada.log)"
      "$BOT_ROOT/scripts/notificar.sh" "Candidaturas: validate-rodada reprovou o aplicadas.json — $(tail -1 validate-rodada.log | cut -c1-200)" || true
    fi
  fi

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
    if [ "$IMPRODUTIVA" -eq 1 ]; then
      log "nenhum modelo produtivo agora (quota ou sessao sem navegar em todos), rechecando em ${W}s"
    else
      log "quota/limite: TODOS os ${#MODELOS[@]} modelos gratuitos no teto (${QUOTA_HITS}x seguidas), rechecando em ${W}s"
    fi
    sleep "$W"
  elif { [ "$STATUS" -eq 124 ] || [ "$STATUS" -eq 137 ] || [ "$STATUS" -eq 143 ]; } \
       && [ "$FP_ANTES" != "-1" ] && [ "$FP_ANTES" != "$(fingerprint "$APLICADAS_FILE")" ]; then
    # the round ran past RUN_TIMEOUT but DID record progress: not a failure (no retry backoff)
    FAILS=0
    python3 "$BOT_ROOT/bot/rodizio-saude.py" "$([ "$OV_SO_FILA" = 1 ] && echo pos-so-fila || echo pos)" "$APLICADAS_FILE" >> loop.log 2>&1 || true
    log "rodada passou de ${RUN_TIMEOUT} mas GRAVOU progresso: conta como ok, dormindo $((NORMAL_WAIT / 60))min"
    sleep "$NORMAL_WAIT"
  elif [ "$STATUS" -eq 124 ] || [ "$STATUS" -eq 137 ] || [ "$STATUS" -eq 143 ]; then
    FAILS=$((FAILS + 1))
    W=$(fail_wait "$FAILS")
    log "rodada estourou ${RUN_TIMEOUT} (ou foi morta), nova tentativa em ${W}s"
    sleep "$W"
  elif [ "$STATUS" -eq 75 ]; then
    log "Chrome ocupado (lock de 15min ou cedeu a job prioritario), tentando de novo em ${RETRY_BASE}s"
    sleep "$RETRY_BASE"
  elif [ "$STATUS" -ne 0 ]; then
    FAILS=$((FAILS + 1))
    W=$(fail_wait "$FAILS")
    log "opencode terminou com erro (status ${STATUS}), nova tentativa em ${W}s"
    sleep "$W"
  else
    FAILS=0
    QUOTA_HITS=0
    python3 "$BOT_ROOT/bot/rodizio-saude.py" "$([ "$OV_SO_FILA" = 1 ] && echo pos-so-fila || echo pos)" "$APLICADAS_FILE" >> loop.log 2>&1 || true
    FP_DEPOIS=$(fingerprint "$APLICADAS_FILE")
    if [ "$FP_ANTES" != "-1" ] && [ "$FP_DEPOIS" != "-1" ] && [ "$FP_ANTES" = "$FP_DEPOIS" ]; then
      VAZIAS=$((VAZIAS + 1))
      W=$(vazia_wait "$VAZIAS")
      # Ainda ha vaga boa na fila/login pronto: nao durma horas em cima dela.
      if tem_envio_pronto && [ "$W" -gt "$NORMAL_WAIT" ]; then W=$NORMAL_WAIT; fi
      log "rodada ok, NENHUMA vaga nova (${VAZIAS}x seguidas), dormindo $((W / 60))min"
      sleep "$W"
    else
      VAZIAS=0
      log "rodada ok, vaga nova processada, dormindo 20min"
      sleep "$NORMAL_WAIT"
    fi
  fi

  if [ "$FAILS" -ge 8 ]; then
    log "ALERTA: ${FAILS} falhas consecutivas — loop pode estar quebrado, verifique ${ROUND_LOG}"
  fi
done
