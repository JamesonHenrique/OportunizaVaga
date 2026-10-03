#!/bin/bash
# bot/sites/trampos.sh — mural de vagas de comunicacao/marketing + tech.
# ATENCAO: o dominio antigo trampos.com.br cai (ERR_CONNECTION_RESET em 2026-10-03);
# a plataforma vive em trampos.co. Verificado em 2026-10-03: a busca do mural usa
# o query ?tr=<termo> e o resultado mostra o regime (Home office) no card.
SITE_ID="trampos"
SITE_LABEL="Trampos"
SITE_HOME="https://trampos.co"
SEARCH_URL_TEMPLATE="https://trampos.co/oportunidades/?tr=SEU_TERMO"
SITE_REMOTE_HINT="selo Home office no card; a URL nao tem filtro de remoto"
SEARCH_ENCODING="pct20"

site_url_busca() {
  local termo="${1:-}"
  printf '%s\n' "${SEARCH_URL_TEMPLATE//SEU_TERMO/${termo// /%20}}"
}

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
}