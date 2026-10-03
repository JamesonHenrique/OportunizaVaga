#!/bin/bash
# tests/test_funil.sh — suite TAP do funil de candidatura (bot/funil.py).
#
# O que estes testes travam, e por que cada caso existe:
#   - "respondeu" NAO e "status diferente de enviada": `enviada` e o status de quem
#     ainda nao respondeu. Inclui-lo fazia a taxa de resposta valer sempre ~100%.
#   - convites e entrevistas sao etapas separadas (antes viravam o mesmo numero).
#   - `encerrada`/`sem_retorno_verificavel` ficam fora: nao da para saber se houve
#     retorno, e escolher um lado sem evidencia inventa numero.
#   - status desconhecido nao vira resposta, mas aparece no diagnostico em vez de sumir.
#   - as etapas sao cumulativas e monotonicas: entrevista <= convite <= resposta <= aplicada.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

N=0
FAIL=0
relata() {
  N=$((N + 1))
  if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi
}
espera() { # espera <esperado> <obtido> <descricao>
  if [ "$1" = "$2" ]; then relata 0 "$3"
  else relata 1 "$3 (esperado: $1 | obtido: $2)"; fi
}
j() { # j <saida json> <expressao python sobre d>
  printf '%s' "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); print($2)"
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- 1: funil completo, uma candidatura por estagio -------------------------------
cat >"$TMP/aplicadas.json" <<'EOF'
{
  "aplicadas": [
    { "chave": "a1", "vaga": "enviada",      "status": "enviada",             "remota": true,  "data": "2026-09-01" },
    { "chave": "a2", "vaga": "respondida",   "status": "respondida",          "remota": false, "data": "2026-09-20" },
    { "chave": "a3", "vaga": "em analise",   "status": "em_analise",          "remota": true,  "data": "2026-09-25" },
    { "chave": "a4", "vaga": "etapa teste",  "status": "etapa_teste",         "remota": true,  "data": "2026-09-28" },
    { "chave": "a5", "vaga": "proxima",      "status": "proxima_etapa",       "remota": false, "data": "2026-10-01" },
    { "chave": "a6", "vaga": "entrevista",   "status": "entrevista",          "remota": true,  "data": "2026-10-02" },
    { "chave": "a7", "vaga": "encerrada",    "status": "encerrada",           "remota": false, "data": "2026-09-30" },
    { "chave": "a8", "vaga": "sem resposta", "status": "sem_resposta",        "remota": false, "data": "2026-09-15" },
    { "chave": "a9", "vaga": "sem retorno",  "status": "sem_retorno_verificavel", "remota": false, "data": "2026-09-15" }
  ],
  "bloqueados": { "b1": { "vaga": "inexistente" }, "b2": { "vaga": "exclusiva OAB" } },
  "descartes_listagem": { "total": 30 },
  "quase_la": { "q1": { "vaga": "quase la" } }
}
EOF

OUT="$(python3 bot/funil.py --aplicadas "$TMP/aplicadas.json" --json)"
if [ $? -eq 0 ]; then relata 0 "funil --json sai com exit 0"; else relata 1 "funil --json sai com exit 0"; fi

espera 41 "$(j "$OUT" "d['contagens']['vistas']")"      "vistas = descartes(30) + aplicadas(9) + bloqueadas(2)"
espera 9  "$(j "$OUT" "d['contagens']['aplicadas']")"   "aplicadas = toda entrada de aplicadas[]"
# respondidas: a2,a3,a4,a5,a6,a8 = 6. Fora: a1 (ainda enviada), a7 e a9 (ambiguos).
espera 6  "$(j "$OUT" "d['contagens']['respondidas']")" "respondidas = status que saiu de enviada (6, sem contar a1)"
espera 4  "$(j "$OUT" "d['contagens']['convites']")"    "convites = em_analise + etapa_teste + proxima_etapa + entrevista"
espera 1  "$(j "$OUT" "d['contagens']['entrevistas']")" "entrevistas = so status entrevista"

# o bug antigo: `enviada` nao pode entrar em respondidas
TX_RESP="$(j "$OUT" "round(d['taxas']['respondidas'], 1)")"
espera "66.7" "$TX_RESP" "taxa aplicadas->respondidas = 6/9, nao 100%"

# a7/a9 ficam fora de respondidas e sao reportadas a parte
espera 2 "$(j "$OUT" "d['retorno_equivocado']")" "encerrada + sem_retorno_verificavel ficam fora das etapas (ambiguo)"

# recorte de silencio: so a1 esta 'enviada' e e antiga (data 2026-09-01, corte em 21 dias)
espera 1 "$(j "$OUT" "d['sem_resposta_antiga']")" "sem_resposta_antiga = ainda enviada com data > 21 dias"

# execucao remota: a3,a4,a6 sao remotas e chegaram a etapa de processo = 3 (a5 e remota=false)
espera 3 "$(j "$OUT" "d['execucao_remota']")" "execucao_remota conta so remotas que chegaram a etapa de processo"

ORDEM="$(j "$OUT" "'sim' if all(x>=y for x,y in zip([d['contagens'][k] for k in ('vistas','aplicadas','respondidas','convites','entrevistas')],[d['contagens'][k] for k in ('aplicadas','respondidas','convites','entrevistas','entrevistas')])) else 'nao'")"
espera "sim" "$ORDEM" "etapas sao monotonicas e cumulativas"

espera 1 "$(j "$OUT" "d['quase_la']")" "quase_la sai no diagnostico"

# --- 2: status desconhecido -------------------------------------------------------
cat >"$TMP/estranho.json" <<'EOF'
{
  "aplicadas": [
    { "chave": "x1", "status": "enviada", "data": "2026-10-01" },
    { "chave": "x2", "status": "status_que_nao_existe", "data": "2026-10-01" }
  ]
}
EOF
OUT2="$(python3 bot/funil.py --aplicadas "$TMP/estranho.json" --json)"
espera "status_que_nao_existe" "$(j "$OUT2" "','.join(d['status_desconhecidos'])")" "status desconhecido aparece no diagnostico"
espera 2 "$(j "$OUT2" "d['contagens']['aplicadas']")" "aplicadas conta entrada com status desconhecido"
# x1 esta enviada (nao e resposta), x2 tem status desconhecido (tambem nao): 0 respostas.
espera 0 "$(j "$OUT2" "d['contagens']['respondidas']")" "status desconhecido NAO vira resposta (fail-closed)"
espera 0 "$(j "$OUT2" "d['contagens']['convites']")" "status desconhecido NAO vira convite"

# --- 3: sem chave status (registro antigo) ----------------------------------------
cat >"$TMP/sem-status.json" <<'EOF'
{ "aplicadas": [ { "chave": "z1" }, { "chave": "z2", "data": "2026-09-01" } ] }
EOF
OUT3="$(python3 bot/funil.py --aplicadas "$TMP/sem-status.json" --json)"
espera 2 "$(j "$OUT3" "d['contagens']['aplicadas']")" "sem status: conta como aplicada (existe no array)"
espera 0 "$(j "$OUT3" "d['contagens']['respondidas']")" "sem status: trata como ainda enviada, nao como resposta"

# --- 4: saida de texto ------------------------------------------------------------
TXT="$(python3 bot/funil.py --aplicadas "$TMP/aplicadas.json")"
if printf '%s' "$TXT" | grep -q "entrevistas" && printf '%s' "$TXT" | grep -q "aplicadas -> respondidas"; then
  relata 0 "saida de texto lista as etapas e as taxas"
else
  relata 1 "saida de texto lista as etapas e as taxas"
fi
if printf '%s' "$TXT" | grep -q "ambiguo"; then
  relata 0 "saida de texto sinaliza o retorno ambiguo"
else
  relata 1 "saida de texto sinaliza o retorno ambiguo"
fi

# --- 5: CSV e markdown ------------------------------------------------------------
CSV="$TMP/funil.csv"
python3 bot/funil.py --aplicadas "$TMP/aplicadas.json" --csv "$CSV" >/dev/null
if head -1 "$CSV" | grep -q "etapa,quantidade" && grep -q "^entrevistas," "$CSV"; then
  relata 0 "--csv escreve o cabecalho e uma linha por etapa"
else
  relata 0 "--csv escreve o cabecalho e uma linha por etapa"
fi

MD="$TMP/funil.md"
python3 bot/funil.py --aplicadas "$TMP/aplicadas.json" --markdown "$MD" >/dev/null
if grep -q "| etapa | quantidade |" "$MD" && grep -q "entrevistas" "$MD"; then
  relata 0 "--markdown escreve tabela de etapas"
else
  relata 1 "--markdown escreve tabela de etapas"
fi

# --- 6: entradas degeneradas ------------------------------------------------------
echo '{"aplicadas":[]}' >"$TMP/vazio.json"
if python3 bot/funil.py --aplicadas "$TMP/vazio.json" >/dev/null 2>&1; then
  relata 0 "aplicadas vazio: exit 0 (sem divisao por zero)"
else
  relata 1 "aplicadas vazio: exit 0 (sem divisao por zero)"
fi

if python3 bot/funil.py --aplicadas "$TMP/nao-existe.json" >/dev/null 2>&1; then
  relata 1 "arquivo inexistente: exit != 0"
else
  relata 0 "arquivo inexistente: exit != 0"
fi

echo 'not json' >"$TMP/ruim.json"
if python3 bot/funil.py --aplicadas "$TMP/ruim.json" >/dev/null 2>&1; then
  relata 1 "json invalido: exit != 0"
else
  relata 0 "json invalido: exit != 0"
fi

echo '{"sem_aplicadas": 1}' >"$TMP/sem-chave.json"
if python3 bot/funil.py --aplicadas "$TMP/sem-chave.json" >/dev/null 2>&1; then
  relata 1 "json sem a chave aplicadas: exit != 0"
else
  relata 0 "json sem a chave aplicadas: exit != 0"
fi

echo "# verde: $((N - FAIL))/$N"
[ "$FAIL" -eq 0 ] || exit 1