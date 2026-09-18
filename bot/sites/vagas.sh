#!/bin/bash
# TEMPLATE de adaptador — Vagas.com.br. Ponto de partida documentado, NÃO
# automação pronta. Ajuste seletores ao layout atual antes de usar.
# Contrato: docs/ADAPTERS.md · base: bot/sites/_template.sh

SITE_ID="vagas"
SITE_LABEL="Vagas.com.br"
SITE_HOME="https://www.vagas.com.br"
SEARCH_URL_TEMPLATE="https://www.vagas.com.br/vagas-de-SEU_TERMO?m%5B%5D=home-office"
SITE_REMOTE_HINT="filtro 'Home office' (m[]=home-office) na URL; confirme no card"

# DICAS DE SELETORES (confira no DevTools):
# - lista de vagas: itens da listagem (título + empresa + local)
# - etiqueta de modelo: 'Home office' no local da vaga
# - ordenação: opção 'mais recentes' quando disponível

site_url_busca() {
  local termo="${1:-}"
  # Vagas.com.br usa termo com hífen no path (ex.: vagas-de-desenvolvedor-java).
  printf '%s\n' "${SEARCH_URL_TEMPLATE//SEU_TERMO/${termo// /-}}"
}

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
  echo "# Termos genéricos (seção TERMOS do prompt_loop): veja 'TERMOS (EXEMPLO...)' em $prompt"
}
