#!/bin/bash
SITE_ID="indeed"
SITE_LABEL="Indeed"
SITE_HOME="https://br.indeed.com"
SEARCH_URL_TEMPLATE="https://br.indeed.com/jobs?q=SEU_TERMO&l=Remoto&sort=date"
SITE_REMOTE_HINT="texto Remoto ou Home office no card ou na pagina da vaga"

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
