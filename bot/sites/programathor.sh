#!/bin/bash
# TEMPLATE de adaptador — Programathor. Ponto de partida documentado, NÃO
# automação pronta. Ajuste seletores ao layout atual antes de usar.
# Contrato: docs/ADAPTERS.md · base: bot/sites/_template.sh

SITE_ID="programathor"
SITE_LABEL="Programathor"
SITE_HOME="https://programathor.com.br"
# Portal só de vagas de tecnologia; muitas já são remotas por padrão.
SEARCH_URL_TEMPLATE="https://programathor.com.br/jobs?search=SEU_TERMO"
SITE_REMOTE_HINT="etiqueta 'Home Office'/'Remoto' no card; filtro de modalidade na lateral"

# DICAS DE SELETORES (confira no DevTools):
# - lista de vagas: cards de job (título + empresa + tags de stack)
# - etiqueta de modelo: tag 'Home Office' no card
# - nível: procure 'Júnior'/'Trainee' no título (o modelo aplica o filtro do prompt)

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
