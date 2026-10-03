#!/bin/bash
# tests/test_sites.sh — suite TAP dos adaptadores de bot/sites/.
# Cobre o contrato (descoberta, variaveis, site_url_busca) sem rede e sem browser:
# a URL montada e comparada com a tabela abaixo, entao um adapter errado ou com
# placeholder trocado quebra o teste.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TOTAL=0
N=0
FAIL=0

relata() { # relata <status: 0=ok> <descricao>
  N=$((N + 1))
  TOTAL=$((TOTAL + 1))
  if [ "$1" -eq 0 ]; then
    echo "ok $N - $2"
  else
    echo "not ok $N - $2"
    FAIL=$((FAIL + 1))
  fi
}

espera() { # espera <valor esperado> <valor obtido> <descricao>
  if [ "$1" = "$2" ]; then
    relata 0 "$3"
  else
    relata 1 "$3 (esperado: $1 | obtido: $2)"
  fi
}

# shellcheck source=bot/sites/lib.sh
. "$ROOT/bot/sites/lib.sh"

TERMO="analista financeiro"

# id | URL esperada com $TERMO
CASOS=(
  "vagas|https://www.vagas.com.br/vagas-de-analista-financeiro?m%5B%5D=home-office"
  "indeed|https://br.indeed.com/jobs?q=analista%20financeiro&l=Remoto&sort=date"
  "gupy|https://portal.gupy.io/job-search/term=analista%20financeiro"
  "linkedin|https://www.linkedin.com/jobs/search/?keywords=analista%20financeiro&location=Brasil&f_WT=2&sortBy=DD"
  "programathor|https://programathor.com.br/jobs?search=analista%20financeiro"
  "geekhunter|https://www.geekhunter.com.br/vagas?busca=analista%20financeiro&remoto=1"
  "catho|https://www.catho.com.br/vagas/analista-financeiro/"
  "infojobs|https://www.infojobs.com.br/vagas-de-emprego-analista%20financeiro.aspx"
  "solides|https://vagas.solides.com.br/vagas/analista-financeiro"
  "trampos|https://trampos.co/oportunidades/?tr=analista%20financeiro"
)

for linha in "${CASOS[@]}"; do
  id="${linha%%|*}"
  url_esperada="${linha#*|}"

  if site_adapter_source "$id" "$ROOT" 2>/dev/null; then
    relata 0 "$id: contrato carrega (SITE_ID/SEARCH_URL_TEMPLATE/site_url_busca)"
  else
    relata 1 "$id: contrato carrega (SITE_ID/SEARCH_URL_TEMPLATE/site_url_busca)"
    continue
  fi

  espera "$url_esperada" "$(site_adapter_url "$TERMO")" "$id: site_url_busca monta a URL"
  espera "$id" "$SITE_ID" "$id: SITE_ID bate com o nome do arquivo"
  espera "$ROOT/bot/sites/$id.sh" "$(site_adapter_file "$id" "$ROOT")" "$id: site_adapter_file aponta para o arquivo"

  [ -n "${SITE_LABEL:-}" ] && relata 0 "$id: SITE_LABEL declarado" || relata 1 "$id: SITE_LABEL declarado"
  [ -n "${SITE_REMOTE_HINT:-}" ] && relata 0 "$id: SITE_REMOTE_HINT declarado" || relata 1 "$id: SITE_REMOTE_HINT declarado"

  if declare -F site_buscar_termos >/dev/null; then
    relata 0 "$id: site_buscar_termos disponivel"
  else
    relata 1 "$id: site_buscar_termos disponivel"
  fi

  # case-insensitive na URL (o modelo digita "Java" e o portal nao liga)
  espera "$(printf '%s' "$url_esperada" | tr 'A-Z' 'a-z')" \
    "$(site_adapter_url "Analista Financeiro" | tr 'A-Z' 'a-z')" \
    "$id: URL nao depende de caixa do termo"
done <<EOF
$CASOS
EOF

# --- invariantes da arvore -------------------------------------------------
lista="$(site_adapter_list "$ROOT")"
[ "$(printf '%s\n' "$lista" | wc -l)" -ge 9 ] \
  && relata 0 "site_adapter_list acha os 9+ adaptadores" \
  || relata 1 "site_adapter_list acha os 9+ adaptadores (obtidos: $(printf '%s' "$lista" | tr '\n' ' '))"

printf '%s\n' "$lista" | grep -qx '_template' \
  && relata 1 "site_adapter_list nao devolve _template" \
  || relata 0 "site_adapter_list nao devolve _template"
printf '%s\n' "$lista" | grep -qx 'lib' \
  && relata 1 "site_adapter_list nao devolve lib" \
  || relata 0 "site_adapter_list nao devolve lib"

# todo .sh de bot/sites/ tem que estar na lista (contrato = discovered automatically)
for f in "$ROOT"/bot/sites/*.sh; do
  b="$(basename "$f" .sh)"
  [ "$b" = "_template" ] && continue
  [ "$b" = "lib" ] && continue
  printf '%s\n' "$lista" | grep -qx "$b" \
    && relata 0 "$b: entra na descoberta automatica" \
    || relata 1 "$b: entra na descoberta automatica"
done

# URL exata (assert acima) ja garante ausencia de placeholder e de espaco cru:
# a tabela de esperado nao tem nenhum dos dois. O que sobra e o contrato fechado.
# shellcheck source=bot/sites/lib.sh
. "$ROOT/bot/sites/lib.sh"

# site_adapter_source em id que nao existe tem que falhar
( site_adapter_source nao-existe "$ROOT" ) 2>/dev/null \
  && relata 1 "site_adapter_source rejeita id inexistente" \
  || relata 0 "site_adapter_source rejeita id inexistente"

echo "# verde: $((TOTAL - FAIL))/$TOTAL"
[ "$FAIL" -eq 0 ] || exit 1