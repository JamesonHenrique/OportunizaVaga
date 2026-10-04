#!/bin/bash
# bot/sites/catho.sh — generalista grande, muitas vagas CLT; area e cidade no path.
# Verificado em 2026-10-03: /vagas/<slug>/ devolve 200 com o titulo da busca e o
# slug aceita hifen no lugar de espaco. O filtro Home Office existe na tela
# (caixa "Home Office" em Modalidade) mas NAO vai para a URL: e aplicado por XHR.
SITE_ID="catho"
SITE_LABEL="Catho"
SITE_HOME="https://www.catho.com.br"
SEARCH_URL_TEMPLATE="https://www.catho.com.br/vagas/SEU_TERMO/"
SITE_REMOTE_HINT="caixa Home Office no filtro Modalidade (a URL nao muda); badge Home Office no card"
# slug de path usa hifen no lugar do espaco. Declare aqui sempre que o encoding nao for %20.
SEARCH_ENCODING="hifen"

site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
}
