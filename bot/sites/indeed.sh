#!/bin/bash
# TEMPLATE — ponto de partida documentado, NÃO automação pronta.
# Como usar: copie este arquivo, ajuste SEARCH_URL_TEMPLATE e os seletores ao
# layout atual do site e chame site_buscar_termos dentro da sua rotina manual.
# Detalhes do fluxo (rodízio, termos, pré-filtro): docs/PROMPTS.md e
# bot/prompt_loop.md (seção b). Este template NÃO abre browser sozinho.
#
# Sem dados pessoais, sem segredos, sem caminho absoluto hardcoded:
# usa $BOT_ROOT (exportado pelos scripts) com fallback para o clone.

SITE_ID="indeed"
# Template de busca (padrão público já documentado em bot/prompt_loop.md):
# l=Remoto = filtro remoto; sort=date = mais recentes primeiro.
SEARCH_URL_TEMPLATE="https://br.indeed.com/jobs?q=SEU_TERMO&l=Remoto&sort=date"

# SELECTORS_DICAS (comentários — confira no DevTools, o site muda):
# - campo de busca: input q (termo) + input l (local = Remoto)
# - lista de vagas: cards da listagem (título + empresa + snippet)
# - etiqueta de modelo: texto "Remoto"/"Home office" no card ou na página
# - paginação/sort: sort=date já ordena por data (mais recentes primeiro)

# Imprime os termos do prompt_loop para este site (um por linha).
# Uso: site_buscar_termos [arquivo_prompt]
site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/bot/prompt_loop.md}"
  awk '/^[[:space:]]*-[[:space:]]*indeed:/{p=1; print; next} p&&/^[[:space:]]*-[[:space:]]*[a-z]+:/{p=0} p' "$prompt" 2>/dev/null
  echo "# Termos genéricos (seção TERMOS do prompt_loop): consulte a linha 'TERMOS (EXEMPLO...)' em $prompt"
}
