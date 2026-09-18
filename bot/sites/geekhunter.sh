#!/bin/bash
# TEMPLATE de adaptador — GeekHunter. Ponto de partida documentado, NÃO
# automação pronta. Ajuste seletores ao layout atual antes de usar.
# Contrato: docs/ADAPTERS.md · base: bot/sites/_template.sh
# OBS: GeekHunter costuma exigir cadastro/perfil; parte do fluxo é manual.

SITE_ID="geekhunter"
SITE_LABEL="GeekHunter"
SITE_HOME="https://www.geekhunter.com.br"
SEARCH_URL_TEMPLATE="https://www.geekhunter.com.br/vagas?busca=SEU_TERMO&remoto=1"
SITE_REMOTE_HINT="filtro 'Remoto' na busca; confirme no topo da vaga"

# DICAS DE SELETORES (confira no DevTools):
# - lista de vagas: cards com título + empresa + faixa/senioridade
# - etiqueta de modelo: chip 'Remoto'
# - nível: senioridade explícita no card (aplique o filtro do prompt)

site_url_busca() {
  local termo="${1:-}"
  printf '%s\n' "${SEARCH_URL_TEMPLATE//SEU_TERMO/${termo// /%20}}"
}

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
  echo "# Termos genéricos (seção TERMOS do prompt_loop): veja 'TERMOS (EXEMPLO...)' em $prompt"
}
