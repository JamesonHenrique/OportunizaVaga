#!/bin/bash
SITE_ID="vagas"
SITE_LABEL="Vagas.com.br"
SITE_HOME="https://www.vagas.com.br"
SEARCH_URL_TEMPLATE="https://www.vagas.com.br/vagas-de-SEU_TERMO?m%5B%5D=home-office"
SITE_REMOTE_HINT="filtro Home office na URL; confirme no card"

site_url_busca() {
  local termo="${1:-}"
  printf '%s\n' "${SEARCH_URL_TEMPLATE//SEU_TERMO/${termo// /-}}"
}

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
}
