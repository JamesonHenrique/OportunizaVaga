#!/bin/bash
# bot/sites/_template.sh — contrato comum de adaptador.
SITE_ID="TEMPLATE"
SITE_LABEL="Template (exemplo)"
SITE_HOME="https://exemplo.com"
SEARCH_URL_TEMPLATE="https://exemplo.com/vagas?q=SEU_TERMO&remoto=true&ordem=recentes"
SITE_REMOTE_HINT="badge/checkbox Remoto ou Home office no card e no topo da vaga"

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
