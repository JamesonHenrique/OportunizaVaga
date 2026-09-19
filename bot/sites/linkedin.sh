#!/bin/bash
SITE_ID="linkedin"
SITE_LABEL="LinkedIn"
SITE_HOME="https://www.linkedin.com"
SEARCH_URL_TEMPLATE="https://www.linkedin.com/jobs/search/?keywords=SEU_TERMO&location=Brasil&f_WT=2&sortBy=DD"
SITE_REMOTE_HINT="texto Remoto no card ou na pagina da vaga"

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
