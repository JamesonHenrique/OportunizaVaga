#!/bin/bash
# setup-wizard.sh — cria bot/dados_candidato.json e bot/perfil.json por perguntas,
# sem editar JSON na mão. Parte do exemplo oficial (estrutura completa) e só sobrescreve o que
# você responder. Os arquivos gerados são gitignored e NUNCA vão ao repo.
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
ask objetivo    "Objetivo (ex.: tech lead remoto, advogado pleno remoto)"
ask resumo      "Resumo profissional (3-4 linhas verdadeiras)"
ask techs       "Tecnologias que você domina (separadas por vírgula)"
ask nivel       "Níveis aceitos, separados por vírgula (estágio, trainee, júnior, pleno, sênior, especialista, líder, gestor, diretor)"

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
  | (if ($nivel|length) > 0 then .situacao_profissional.nivel = ($nivel | split(",") | map(gsub("^\\s+|\\s+$";"")) | join("|")) else . end)
  ' "$EXEMPLO" > "$tmp"

mv "$tmp" "$DESTINO"
echo
echo "Gerado: $DESTINO (gitignored — não commite)."

# ---- Perfil de busca (bot/perfil.json): nível, área, modelo e termos ----
PERFIL="bot/perfil.json"
gera_perfil=1
if [ -f "$PERFIL" ]; then
  read -r -p "$PERFIL já existe. Sobrescrever? [s/N] " ok
  case "$ok" in s|S|sim|Sim) : ;; *) gera_perfil=0 ;; esac
fi
if [ "$gera_perfil" -eq 1 ]; then
  echo
  echo "Perfil de busca (o que o robô aceita/recusa):"
  ask area       "Área de atuação (ex.: tecnologia, jurídico, marketing, saúde)"
  ask modelos    "Modelos aceitos, separados por vírgula (remoto, híbrido, presencial) [remoto]"
  ask cidades    "Cidades p/ híbrido/presencial, separadas por vírgula (Enter = ${local:-sua cidade})"
  ask termos     "Termos de busca, separados por vírgula (ex.: tech lead remoto, advogado pleno)"
  ask pular      "Tipos de vaga a pular, separados por vírgula (opcional)"
  python3 - "$PERFIL" "${nivel:-}" "${area:-}" "${modelos:-}" "${cidades:-}" "${termos:-}" "${pular:-}" "${objetivo:-}" <<'PY'
import json, sys
sys.path.insert(0, "bot")
import perfil_render as r
destino, nivel, area, modelos, cidades, termos, pular, objetivo = sys.argv[1:]
lista = lambda s: [x.strip() for x in s.split(",") if x.strip()]
niveis = [n for n in (r.nivel_canonico(x) for x in lista(nivel)) if n] or ["junior", "trainee"]
termos_l = lista(termos) or ([objetivo] if objetivo.strip() else [])
if not termos_l:
    sys.exit("perfil: informe ao menos um termo de busca (ou o objetivo) e rode de novo.")
perfil = {
    "nome_perfil": "-".join([niveis[-1], (area or "tecnologia").split()[0].lower()]),
    "niveis": niveis,
    "area": area.strip() or "tecnologia",
    "modelos": r.modelos_do_perfil({"modelos": lista(modelos)}),
    "termos": termos_l,
    "pular_tipos": lista(pular),
}
if lista(cidades):
    perfil["cidades"] = lista(cidades)
open(destino, "w", encoding="utf-8").write(json.dumps(perfil, ensure_ascii=False, indent=2) + "\n")
print("Gerado: %s (gitignored). Confira: python3 bot/perfil_render.py info %s" % (destino, destino))
PY
fi

# Valida contra o schema, se o validador existir.
if [ -x scripts/validate.sh ]; then
  echo "Validando..."
  ./scripts/validate.sh || echo "validate.sh apontou pendências acima — ajuste $DESTINO."
fi

echo "Próximo: ./browser/chrome-real.sh &  então  ./bot/dry-run.sh  (ver docs/QUICKSTART.md)."
