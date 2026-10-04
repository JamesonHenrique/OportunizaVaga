#!/bin/bash
# bot/sites/solides.sh — portal de vagas da Sólides (ATS, ex-Kenoby), todas as areas.
# Verificado em 2026-10-03: o buscador fica em vagas.solides.com.br e o path e
# /vagas/<slug-hifenado> (o www.solides.com.br e o site institucional e responde 403).
# Nao ha filtro de remoto na URL: a modalidade vem na descricao da vaga.
SITE_ID="solides"
SITE_LABEL="Sólides Vagas"
SITE_HOME="https://vagas.solides.com.br"
SEARCH_URL_TEMPLATE="https://vagas.solides.com.br/vagas/SEU_TERMO"
SITE_REMOTE_HINT="modalidade (Remoto/Home office/Hibrido) no card ou na descricao da vaga"
# slug de path usa hifen no lugar do espaco. Declare sempre que o encoding nao for %20.
SEARCH_ENCODING="hifen"

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
}
