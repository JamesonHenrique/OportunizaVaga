#!/bin/bash
# TEMPLATE — ponto de partida documentado, NÃO automação pronta.
# Como usar: copie este arquivo, ajuste SEARCH_URL_TEMPLATE e os seletores ao
# layout atual do site e chame site_buscar_termos dentro da sua rotina manual.
# Detalhes do fluxo (rodízio, termos, pré-filtro): docs/PROMPTS.md e
# bot/prompt_loop.md (seção b). Este template NÃO abre browser sozinho.
#
# Sem dados pessoais, sem segredos, sem caminho absoluto hardcoded:
# usa $BOT_ROOT (exportado pelos scripts) com fallback para o clone.

SITE_ID="gupy"
# Template de busca (padrão público já documentado em bot/prompt_loop.md):
# troque SEU_TERMO pelo termo da rodada, mantendo o filtro remoto na página.
SEARCH_URL_TEMPLATE="https://portal.gupy.io/job-search/term=SEU_TERMO"

# SELECTORS_DICAS (comentários — confira no DevTools, o site muda):
# - campo de busca: input de termo na página de job-search
# - lista de vagas: cards da listagem (título + empresa + etiquetas)
# - etiqueta de modelo: badge "remoto"/"home office" no card
# - paginação/sort: controle de mais recentes primeiro, se existir

# Imprime os termos do prompt_loop para este site (um por linha).
# Uso: site_buscar_termos [arquivo_prompt]
site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/bot/prompt_loop.md}"
  awk '/^[[:space:]]*-[[:space:]]*gupy:/{p=1; print; next} p&&/^[[:space:]]*-[[:space:]]*[a-z]+:/{p=0} p' "$prompt" 2>/dev/null
  echo "# Termos genéricos (seção TERMOS do prompt_loop): consulte a linha 'TERMOS (EXEMPLO...)' em $prompt"
}
