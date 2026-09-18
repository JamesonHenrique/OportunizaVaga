#!/bin/bash
# ============================================================================
# TEMPLATE DE ADAPTADOR DE SITE — copie este arquivo para criar um novo portal.
# ============================================================================
# Um adaptador NÃO é automação pronta: é um "descritor" do portal que o loop e
# o modelo usam para montar a busca. Quem abre o browser e aplica é o modelo,
# seguindo bot/prompt_loop.md. O adaptador só padroniza: como é a URL de busca,
# onde fica o filtro remoto e onde ficam os termos daquela rodada.
#
# CONTRATO (ver docs/ADAPTERS.md):
#   SITE_ID              obrigatório  slug curto, sem espaço (ex.: "programathor")
#   SITE_LABEL           opcional     nome amigável para logs/monitor
#   SITE_HOME            opcional     home do portal (usada em docs, nunca aberta sozinha)
#   SEARCH_URL_TEMPLATE  obrigatório  URL de busca com o marcador SEU_TERMO
#   SITE_REMOTE_HINT     opcional     como o portal marca "remoto" (texto do filtro)
#   site_url_busca TERMO             imprime a URL de busca com o termo aplicado
#   site_buscar_termos [PROMPT]      imprime, um por linha, os termos desta rodada
#
# REGRAS FIXAS (o CI/sanitize.sh cobra):
#   - Sem dado pessoal, sem segredo, sem caminho absoluto (/home/...).
#   - Resolva a raiz por $BOT_ROOT com fallback para o próprio caminho.
#   - Comentários em português; código e nomes em inglês.
#   - `bash -n` limpo e `shellcheck` sem erro.
# ============================================================================

SITE_ID="TEMPLATE"
SITE_LABEL="Template (exemplo)"
SITE_HOME="https://exemplo.com"

# URL de busca. Mantenha o marcador literal SEU_TERMO — site_url_busca o troca.
# Deixe o filtro remoto embutido quando o portal permite (ex.: &remoto=true).
SEARCH_URL_TEMPLATE="https://exemplo.com/vagas?q=SEU_TERMO&remoto=true&ordem=recentes"

# Como o portal expõe "remoto"/"home office" (dica para o modelo confirmar na página).
SITE_REMOTE_HINT="badge/checkbox 'Remoto' ou 'Home office' no card e no topo da vaga"

# DICAS DE SELETORES (confira no DevTools — o site muda com o tempo):
# - campo de busca: input de termo
# - lista de vagas: cards (título + empresa + etiquetas)
# - etiqueta de modelo: badge remoto/home office
# - ordenação: por data (mais recentes primeiro), se existir

# Imprime a URL de busca já com o termo da rodada aplicado.
# Uso: site_url_busca "desenvolvedor java junior"
site_url_busca() {
  local termo="${1:-}"
  # URL-encode mínimo dos espaços; o modelo faz o encode fino se precisar.
  printf '%s\n' "${SEARCH_URL_TEMPLATE//SEU_TERMO/${termo// /%20}}"
}

# Imprime os termos deste site declarados em bot/prompt_loop.md (um por linha).
# Bloco esperado no prompt: uma linha "- <SITE_ID>:" seguida dos termos.
# Uso: site_buscar_termos [arquivo_prompt]
site_buscar_termos() {
  local prompt="${1:-${BOT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/bot/prompt_loop.md}"
  awk -v id="$SITE_ID" '
    $0 ~ "^[[:space:]]*-[[:space:]]*"id":" {p=1; print; next}
    p && /^[[:space:]]*-[[:space:]]*[a-z]+:/ {p=0}
    p' "$prompt" 2>/dev/null
  echo "# Termos genéricos (seção TERMOS do prompt_loop): veja 'TERMOS (EXEMPLO...)' em $prompt"
}
