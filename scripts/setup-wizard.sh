#!/bin/bash
# setup-wizard.sh — cria bot/dados_candidato.json por perguntas, sem editar JSON
# na mão. Parte do exemplo oficial (estrutura completa) e só sobrescreve o que
# você responder. O arquivo gerado é gitignored e NUNCA vai ao repo.
#
# Uso: ./scripts/setup-wizard.sh
set -euo pipefail
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT"

EXEMPLO="examples/dados_candidato.example.json"
DESTINO="bot/dados_candidato.json"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq não encontrado. Instale (ex.: sudo apt install jq) ou edite $DESTINO à mão"
  echo "a partir de $EXEMPLO. Guia: docs/QUICKSTART.md"
  exit 1
fi
[ -f "$EXEMPLO" ] || { echo "faltando $EXEMPLO"; exit 1; }

if [ -f "$DESTINO" ]; then
  read -r -p "$DESTINO já existe. Sobrescrever? [s/N] " ok
  case "$ok" in s|S|sim|Sim) : ;; *) echo "cancelado."; exit 0 ;; esac
fi

echo "Preencha com dados REAIS. Deixe em branco o que não quiser informar —"
echo "campo vazio faz o robô registrar 'bloqueado' em vez de inventar. (Enter pula.)"
echo

# pergunta VAR "texto" -> lê em resposta_VAR
ask() { local __v="$1" __p="$2" __in; read -r -p "$__p: " __in; printf -v "$__v" '%s' "$__in"; }

ask nome        "Nome completo"
ask email       "E-mail"
ask telefone    "Telefone (+55 (00) 90000-0000)"
ask linkedin    "URL do LinkedIn"
ask github      "URL do GitHub"
ask local       "Cidade/UF"
ask formacao    "Formação (curso - instituição - período)"
ask idiomas     "Idiomas (só o real, ex.: Português nativo; Inglês intermediário)"
ask objetivo    "Objetivo (ex.: desenvolvedor júnior remoto)"
ask resumo      "Resumo profissional (3-4 linhas verdadeiras)"
ask techs       "Tecnologias que você domina (separadas por vírgula)"
ask nivel       "Nível (ex.: júnior)"

# Converte lista separada por vírgula em array JSON (trim de espaços).
techs_json="$(printf '%s' "${techs:-}" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length>0))')"

tmp="$(mktemp)"
jq \
  --arg nome "${nome:-}" --arg email "${email:-}" --arg telefone "${telefone:-}" \
  --arg linkedin "${linkedin:-}" --arg github "${github:-}" --arg local "${local:-}" \
  --arg formacao "${formacao:-}" --arg idiomas "${idiomas:-}" --arg objetivo "${objetivo:-}" \
  --arg resumo "${resumo:-}" --arg nivel "${nivel:-}" --argjson techs "$techs_json" '
  .nome = ($nome // .nome)
  | .email = ($email // .email)
  | .telefone = ($telefone // .telefone)
  | .linkedin = ($linkedin // .linkedin)
  | .github = ($github // .github)
  | .local = ($local // .local)
  | .formacao = ($formacao // .formacao)
  | .idiomas = ($idiomas // .idiomas)
  | .objetivo = ($objetivo // .objetivo)
  | .resumo = ($resumo // .resumo)
  | (if ($techs | length) > 0 then .experiencia.tecnologias = $techs | .palavras_chave_ats = $techs else . end)
  | (if ($nivel|length) > 0 then .situacao_profissional.nivel = $nivel else . end)
  ' "$EXEMPLO" > "$tmp"

mv "$tmp" "$DESTINO"
echo
echo "Gerado: $DESTINO (gitignored — não commite)."

# Valida contra o schema, se o validador existir.
if [ -x scripts/validate.sh ]; then
  echo "Validando..."
  ./scripts/validate.sh || echo "validate.sh apontou pendências acima — ajuste $DESTINO."
fi

echo "Próximo: ./browser/chrome-real.sh &  então  ./bot/dry-run.sh  (ver docs/QUICKSTART.md)."
