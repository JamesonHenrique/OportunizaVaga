#!/bin/bash
# bot/sites/infojobs.sh — generalista BR, bom volume em todos os niveis.
# Verificado em 2026-10-03: o path canonico e /vagas-de-emprego-<termo>.aspx (e o que a
# propria pagina usa no alerta de vaga); %20 funciona igual a +. A sidebar NAO tem facet
# de remoto/teletrabalho (sao area, tipo de contrato, jornada, nivel, deficiencia), entao
# o remoto so vale se o card ou a pagina da vaga afirmar.
SITE_ID="infojobs"
SITE_LABEL="InfoJobs"
SITE_HOME="https://www.infojobs.com.br"
SEARCH_URL_TEMPLATE="https://www.infojobs.com.br/vagas-de-emprego-SEU_TERMO.aspx"
SITE_REMOTE_HINT="sem facet de remoto na busca; so aceite se o card ou a pagina disser Remoto/Teletrabalho/Home office"

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
}
