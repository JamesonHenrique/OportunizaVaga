#!/bin/bash
# digest.sh — resumo do dia a partir de aplicadas.json + loop.log.
# Uso: ./scripts/digest.sh [--aplicadas PATH] [--log PATH] [--markdown] [--send]
#   --markdown: saída em Markdown (padrão: texto simples).
#   --send: envia o resumo ao Telegram SOMENTE se TELEGRAM_BOT_TOKEN e
#     TELEGRAM_CHAT_ID existirem (nunca imprime/loga o token).
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APLICADAS="${BOT_APLICADAS:-$BOT_ROOT/bot/aplicadas.json}"
LOOPLOG="$BOT_ROOT/bot/loop.log"
MARKDOWN=0
SEND=0

while [ $# -gt 0 ]; do
  case "$1" in
    --aplicadas) APLICADAS="$2"; shift 2 ;;
    --log) LOOPLOG="$2"; shift 2 ;;
    --markdown) MARKDOWN=1; shift ;;
    --send) SEND=1; shift ;;
    -h|--help) echo "Uso: $(basename "$0") [--aplicadas PATH] [--log PATH] [--markdown] [--send]"; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

[ -f "$APLICADAS" ] || { echo "aplicadas.json não encontrado: $APLICADAS" >&2; exit 1; }
export DIGEST_APLICADAS="$APLICADAS" DIGEST_LOG="$LOOPLOG" DIGEST_MARKDOWN="$MARKDOWN"
RESUMO=$(python3 -c "
import json, os
ap = json.load(open(os.environ['DIGEST_APLICADAS']))
from datetime import date
hoje = date.today().isoformat()
apl = ap.get('aplicadas', [])
bloq = ap.get('bloqueados', {}) or {}
feitas = [a for a in apl if (a.get('data') or '') == hoje]
bloq_hoje = [k for k, v in bloq.items()
             if isinstance(v, dict) and str(v.get('bloqueado_em') or v.get('em') or v.get('criadoEm') or '')[:10] == hoje]
rod = ap.get('rodizio', {}) or {}
print(json.dumps({
  'hoje': hoje,
  'aplicadas_hoje': len(feitas),
  'aplicadas_hoje_lista': [str(a.get('chave') or a.get('vaga')) for a in feitas[:10]],
  'bloqueadas_hoje': len(bloq_hoje),
  'total_aplicadas': len(apl),
  'total_bloqueadas': len(bloq),
  'proximo': rod.get('proximo', '?'),
  'ultima_rodada': rod.get('ultima_rodada', ''),
}))
")
export DIGEST_JSON="$RESUMO"
# Alertas de anomalia: regras simples sobre as linhas de HOJE do loop.log
# (nenhuma rodada ok, sequencia longa de rodadas vazias, muitos timeouts/quota).
export DIGEST_ALERTAS=$(python3 -c "
import os, re
from datetime import date
hoje = date.today().isoformat()
linhas = []
try:
    linhas = open(os.environ['DIGEST_LOG'], encoding='utf-8', errors='replace').readlines()
except OSError:
    pass
hoje_l = [l for l in linhas if l.startswith('[' + hoje)]
oks = [l for l in hoje_l if 'rodada ok' in l]
vazias = [l for l in hoje_l if 'NENHUMA vaga nova' in l]
estouros = [l for l in hoje_l if 'estourou' in l]
quotas = [l for l in hoje_l if 'quota/limite' in l or 'no limite' in l]
erros = [l for l in hoje_l if 'terminou com erro' in l or 'sessao opencode invalida' in l]
streak = 0
for l in reversed(oks + vazias):
    m = re.search(r'\((\d+)x seguidas\)', l)
    if 'NENHUMA vaga nova' in l and m:
        streak = int(m.group(1)); break
    elif 'NENHUMA vaga nova' in l:
        streak += 1
    else:
        break
a = []
if hoje_l and not oks:
    a.append('ALERTA: nenhuma rodada ok hoje — loop pode estar preso em erro/quota.')
if streak >= 3:
    a.append('ALERTA: %dx rodadas vazias seguidas — considerar pular o site atual por 24h.' % streak)
if len(estouros) >= 2:
    a.append('ALERTA: %d timeouts hoje — rodadas estourando o limite, rever META de tempo.' % len(estouros))
if len(quotas) >= 3:
    a.append('INFO: %d sinais de quota hoje — avaliar reordenar a cascata de modelos.' % len(quotas))
if erros:
    a.append('INFO: %d erro(s) de sessao/modelo hoje (ver loop.log).' % len(erros))
print('\n'.join(a))
")
python3 -c "
import json, os
d = json.loads(os.environ['DIGEST_JSON'])
md = os.environ['DIGEST_MARKDOWN'] == '1'
if md:
    print('# Resumo do dia ' + d['hoje'])
    print('')
    print('- Aplicadas hoje: **%d**' % d['aplicadas_hoje'])
    for v in d['aplicadas_hoje_lista']: print('  - ' + v)
    print('- Bloqueadas hoje: **%d**' % d['bloqueadas_hoje'])
    print('- Total: %d aplicadas / %d bloqueadas' % (d['total_aplicadas'], d['total_bloqueadas']))
    print('- Rodízio atual: próximo **%s** (última rodada: %s)' % (d['proximo'], d['ultima_rodada'] or '—'))
    print('- Próximo passo: rodar o site **%s** (ver rodizio.proximo em aplicadas.json)' % d['proximo'])
else:
    print('Resumo do dia ' + d['hoje'])
    print('Aplicadas hoje: %d' % d['aplicadas_hoje'])
    for v in d['aplicadas_hoje_lista']: print('  - ' + v)
    print('Bloqueadas hoje: %d' % d['bloqueadas_hoje'])
    print('Total: %d aplicadas / %d bloqueadas' % (d['total_aplicadas'], d['total_bloqueadas']))
    print('Rodízio atual: próximo %s (última rodada: %s)' % (d['proximo'], d['ultima_rodada'] or '—'))
    print('Próximo passo: rodar o site %s (ver rodizio.proximo em aplicadas.json)' % d['proximo'])
"
# Alertas de anomalia (vazio se nenhuma regra disparou).
if [ -n "$DIGEST_ALERTAS" ]; then
  if [ "$MARKDOWN" -eq 1 ]; then echo -e "\n## Alertas"; else echo "--- alertas ---"; fi
  echo "$DIGEST_ALERTAS"
fi
# Trecho recente do loop.log (contexto, sem segredos: só últimas linhas de status).
if [ -f "$LOOPLOG" ]; then
  if [ "$MARKDOWN" -eq 1 ]; then echo -e "\n## Últimas linhas do loop.log"; else echo "--- últimas linhas do loop.log ---"; fi
  tail -n 5 "$LOOPLOG"
fi

# Envio opcional ao Telegram (só com as duas envs; token nunca impresso/logado).
if [ "$SEND" -eq 1 ]; then
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    TEXT=$(python3 -c "
import json, os
d = json.loads(os.environ['DIGEST_JSON'])
print('Resumo %s: %d aplicadas hoje, %d bloqueadas hoje. Rodízio: próximo %s.' % (d['hoje'], d['aplicadas_hoje'], d['bloqueadas_hoje'], d['proximo']))
")
    curl -s -o /dev/null -w '%{http_code}\n' --max-time 15 \
      -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=${TEXT}" \
      "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"
  else
    echo "(Telegram não configurado: defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID para --send)" >&2
  fi
fi
