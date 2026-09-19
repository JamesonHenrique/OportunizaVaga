#!/bin/bash
SITE_ID="gupy"
SITE_LABEL="Gupy"
SITE_HOME="https://portal.gupy.io"
SEARCH_URL_TEMPLATE="https://portal.gupy.io/job-search/term=SEU_TERMO"
SITE_REMOTE_HINT="badge Remoto ou Home office no card"

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
