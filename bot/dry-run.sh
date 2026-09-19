#!/bin/bash
# bot/dry-run.sh — simula uma rodada global sem aplicar ou abrir browser.
set -u

JSON_OUT=0
SITE_FILTER=""
PROFILE_FILE=""
RECONHECIMENTO=0
PERFIL_EXPLICITO=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --json) JSON_OUT=1; shift ;;
    --site)
      [ "$#" -lt 2 ] && { echo "opcao --site requer argumento" >&2; exit 2; }
      SITE_FILTER="$2"; shift 2 ;;
    --profile)
      [ "$#" -lt 2 ] && { echo "opcao --profile requer argumento" >&2; exit 2; }
      PROFILE_FILE="$2"; PERFIL_EXPLICITO=1; shift 2 ;;
    --reconhecimento) RECONHECIMENTO=1; shift ;;
    -h|--help)
      echo "Uso: bot/dry-run.sh [--json] [--site SITE_ID] [--profile CAMINHO] [--reconhecimento]"
      echo "Plano global: todos os adaptadores; nada e escrito, nenhum browser e aberto."
      exit 0 ;;
    *) echo "opcao desconhecida: $1 (use --help)" >&2; exit 2 ;;
  esac
done

BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT/bot" || exit 1
source "$BOT_ROOT/bot/sites/lib.sh"

if [ -z "$PROFILE_FILE" ]; then
  PROFILE_FILE="${BOT_PERFIL:-}"
fi
if [ -z "$PROFILE_FILE" ] && [ -f "$BOT_ROOT/bot/perfil.json" ]; then
  PROFILE_FILE="$BOT_ROOT/bot/perfil.json"
fi
if [ -z "$PROFILE_FILE" ]; then
  PROFILE_FILE="$BOT_ROOT/config/perfis/junior-backend.example.json"
fi
[ -f "$PROFILE_FILE" ] || { echo "perfil nao encontrado: $PROFILE_FILE" >&2; exit 1; }
[ "$PROFILE_FILE" != "$BOT_ROOT/config/perfis/junior-backend.example.json" ] && PERFIL_EXPLICITO=1

DADOS_FILE="$BOT_ROOT/bot/dados_candidato.json"
[ -f "$DADOS_FILE" ] || DADOS_FILE="$BOT_ROOT/examples/dados_candidato.example.json"
APLICADAS_FILE="$BOT_ROOT/bot/aplicadas.json"
if [ "$PERFIL_EXPLICITO" -eq 1 ]; then
  PERFIL_NOME="$(python3 - "$PROFILE_FILE" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8')).get('nome_perfil', 'perfil'))
PY
)"
  PERFIL_SLUG="$(printf '%s' "$PERFIL_NOME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48)"
  [ -n "$PERFIL_SLUG" ] || PERFIL_SLUG="perfil"
  STATE_DIR="$BOT_ROOT/bot/state/$PERFIL_SLUG"
  [ -f "$STATE_DIR/aplicadas.json" ] && APLICADAS_FILE="$STATE_DIR/aplicadas.json"
else
  PERFIL_NOME="default"
  PERFIL_SLUG="default"
  STATE_DIR="$BOT_ROOT/bot"
fi
[ -f "$APLICADAS_FILE" ] || APLICADAS_FILE="$BOT_ROOT/examples/aplicadas.example.json"

TERMO_FILE="$(mktemp)"
SITE_FILE="$(mktemp)"
trap 'rm -f "$TERMO_FILE" "$SITE_FILE"' EXIT

python3 - "$PROFILE_FILE" "$DADOS_FILE" "$APLICADAS_FILE" "$BOT_ROOT/bot/prompt_loop.md" "$TERMO_FILE" <<'PY'
import json, os, re, sys

perfil_path, dados_path, aplic_path, prompt_path, out_path = sys.argv[1:]
erros = []
try:
    perfil = json.load(open(perfil_path, encoding='utf-8'))
except Exception as exc:
    perfil, perfil = {}, None
    erros.append('perfil: JSON invalido ou ilegivel (%s)' % exc)
if perfil is not None:
    for key in ('nome_perfil', 'nivel', 'termos', 'pular_tipos'):
        if key not in perfil:
            erros.append('perfil: chave obrigatoria ausente: %s' % key)
    if not isinstance(perfil.get('termos'), list) or not perfil.get('termos'):
        erros.append('perfil: termos precisa ser uma lista nao vazia')
    if not isinstance(perfil.get('pular_tipos'), list):
        erros.append('perfil: pular_tipos precisa ser uma lista')

try:
    dados = json.load(open(dados_path, encoding='utf-8'))
except Exception as exc:
    dados, dados = {}, None
    erros.append('dados_candidato: JSON invalido ou ilegivel (%s)' % exc)
if dados is not None:
    for key in ('nome', 'email', 'telefone', 'linkedin', 'local'):
        if key not in dados:
            erros.append('dados_candidato: chave obrigatoria ausente: %s' % key)

try:
    aplic = json.load(open(aplic_path, encoding='utf-8'))
except Exception as exc:
    aplic, aplic = {}, None
    erros.append('aplicadas: JSON invalido ou ilegivel (%s)' % exc)
if aplic is not None:
    if not isinstance(aplic.get('aplicadas'), list):
        erros.append('aplicadas: chave obrigatoria ausente: aplicadas')
    rodizio = aplic.get('rodizio')
    if not isinstance(rodizio, dict) or not rodizio.get('proximo'):
        erros.append('aplicadas: chave obrigatoria ausente: rodizio.proximo')

prompt = open(prompt_path, encoding='utf-8').read() if os.path.isfile(prompt_path) else ''
termos_perfil = perfil.get('termos', []) if isinstance(perfil, dict) else []
with open(out_path, 'w', encoding='utf-8') as out:
    json.dump({'termos_perfil': termos_perfil, 'prompt': prompt, 'perfil': perfil,
               'dados': dados, 'aplic': aplic, 'erros': erros}, out, ensure_ascii=False)
PY

if [ "$(python3 - "$TERMO_FILE" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1], encoding='utf-8')).get('erros', [])))
PY
)" -ne 0 ]; then
  if [ "$JSON_OUT" -eq 1 ]; then
    python3 - "$TERMO_FILE" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding='utf-8'))
print(json.dumps({'ok': False, 'dry_run': True, 'erros': doc['erros']}, ensure_ascii=False))
PY
  else
    echo 'dry-run: FALHOU — corrija antes de rodar o loop real:'
    python3 - "$TERMO_FILE" <<'PY'
import json, sys
for item in json.load(open(sys.argv[1], encoding='utf-8'))['erros']:
    print('  [FALHA] ' + item)
PY
  fi
  exit 1
fi

for site_id in $(site_adapter_list "$BOT_ROOT"); do
  [ -n "$SITE_FILTER" ] && [ "$site_id" != "$SITE_FILTER" ] && continue
  if ! site_adapter_source "$site_id" "$BOT_ROOT"; then
    echo "adaptador invalido: $site_id" >&2
    exit 1
  fi
  {
    printf '%s\t%s\t%s\t' "$site_id" "${SITE_LABEL:-$site_id}" "${SITE_HOME:-}"
    site_adapter_terms "$BOT_ROOT/bot/prompt_loop.md" | tr '\n' '|'
    printf '\t'
    url_busca="$(site_adapter_url "$(python3 - "$TERMO_FILE" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['termos_perfil'][0])
PY
)")"
    printf '%s\n' "$url_busca"
  } >> "$SITE_FILE"
done

python3 - "$TERMO_FILE" "$SITE_FILE" "$PROFILE_FILE" "$DADOS_FILE" "$APLICADAS_FILE" "$PERFIL_NOME" "$PERFIL_SLUG" "$STATE_DIR" "$JSON_OUT" "$RECONHECIMENTO" "$SITE_FILTER" <<'PY'
import json, os, sys

termo_path, site_path, perfil_path, dados_path, aplic_path, perfil_nome, perfil_slug, state_dir, json_out, reconhecimento, site_filter = sys.argv[1:]
termo = json.load(open(termo_path, encoding='utf-8'))
sites = []
with open(site_path, encoding='utf-8') as fh:
    for line in fh:
        site_id, label, home, raw_terms, url = line.rstrip('\n').split('\t', 4)
        terms = [x for x in raw_terms.split('|') if x]
        if not terms:
            terms = list(termo['perfil'].get('termos', []))
        sites.append({
            'site_id': site_id,
            'label': label,
            'home': home,
            'termos': terms,
            'url_busca': url,
        })
aplic = termo['aplic'] or {}
rodizio = aplic.get('rodizio', {}) if isinstance(aplic, dict) else {}
resultado = {
    'ok': True,
    'dry_run': True,
    'global': not bool(site_filter),
    'modo': 'reconhecimento' if reconhecimento == '1' else 'candidaturas',
    'perfil': {
        'nome': perfil_nome,
        'slug': perfil_slug,
        'arquivo': perfil_path,
        'nivel': termo['perfil'].get('nivel'),
        'termos': termo['perfil'].get('termos', []),
        'pular_tipos': termo['perfil'].get('pular_tipos', []),
    },
    'estado': {
        'diretorio': state_dir,
        'arquivo_aplicadas': aplic_path,
        'isolado': perfil_slug != 'default',
        'aplicadas_registradas': len(aplic.get('aplicadas', [])) if isinstance(aplic, dict) else 0,
        'proximo_site': rodizio.get('proximo'),
    },
    'sites': sites,
    'site_count': len(sites),
    'limite_candidaturas': int(os.environ.get('OV_MAX_CANDIDATURAS', '3')),
    'limite_reconhecimento': int(os.environ.get('OV_RECONHECIMENTO_LIMIT', '10')),
    'modelo_preferido': os.environ.get('OV_MODELO_PREFERIDO', 'openrouter/nex-agi/nex-n2.5-pro:free'),
    'browser_aberto': False,
    'candidaturas_enviadas': 0,
    'telemetria': {
        'modo': os.environ.get('OV_TELEMETRY_MODE', 'aggregate'),
        'detalhes': os.environ.get('OV_MONITOR_INCLUDE_DETAILS', '0') == '1',
    },
}
if json_out == '1':
    print(json.dumps(resultado, ensure_ascii=False))
else:
    print('dry-run global: plano de uma rodada (nada foi enviado, nenhum browser aberto).')
    print('  perfil: %s | estado isolado: %s' % (perfil_nome, resultado['estado']['isolado']))
    print('  sites: %d | proximo do rodizio: %s' % (len(sites), resultado['estado']['proximo_site'] or 'nao definido'))
    for site in sites:
        print('  - %s: %s' % (site['site_id'], site['url_busca']))
PY
