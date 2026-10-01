#!/bin/bash
# tests/test_estado.sh — suite minima em bash puro (sem framework), saida TAP.
# Cobre: bot/estado.py (CLI compacta de leitura/escrita atomica de aplicadas.json).
# Uso: bash tests/test_estado.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
ESTADO="bot/estado.py"

TOTAL=23
N=0
FAIL=0
echo "1..$TOTAL"

relata() { # relata <status: 0=ok> <descricao>
  N=$((N + 1))
  if [ "$1" -eq 0 ]; then
    echo "ok $N - $2"
  else
    echo "not ok $N - $2"
    FAIL=$((FAIL + 1))
  fi
}

TMP_STATE="$(mktemp -d)/aplicadas.json"
cp examples/aplicadas.example.json "$TMP_STATE"
cleanup() { rm -rf "$(dirname "$TMP_STATE")"; }
trap cleanup EXIT

# 1 — resumo roda sem erro e cita o rodizio.
OUT1="$(python3 "$ESTADO" --file "$TMP_STATE" resumo 2>&1)"
if echo "$OUT1" | grep -q "rodizio.proximo=indeed"; then
  relata 0 "resumo mostra rodizio.proximo"
else
  echo "$OUT1"
  relata 1 "resumo mostra rodizio.proximo"
fi

# 2 — add-aplicada grava e resumo passa a listar a empresa.
python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"teste-1","empresa":"AcmeCorp","vaga":"Dev Jr"}' >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" resumo | grep -q "AcmeCorp"; then
  relata 0 "add-aplicada grava a chave nova"
else
  relata 1 "add-aplicada grava a chave nova"
fi

# 3 — add-aplicada com chave repetida nao duplica (exit != 0).
python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"teste-1","empresa":"AcmeCorp","vaga":"Dev Jr"}' >/dev/null 2>&1
ST3=$?
if [ "$ST3" -ne 0 ]; then
  relata 0 "add-aplicada recusa chave duplicada"
else
  relata 1 "add-aplicada recusa chave duplicada"
fi

# 4 — add-bloqueado grava motivo e get recupera o registro.
python3 "$ESTADO" --file "$TMP_STATE" add-bloqueado "teste-2" '{"motivo":"CPF ausente"}' >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" get "teste-2" | grep -q "CPF ausente"; then
  relata 0 "add-bloqueado + get recuperam o motivo"
else
  relata 1 "add-bloqueado + get recuperam o motivo"
fi

# 5 — set-quase-la grava e null remove.
python3 "$ESTADO" --file "$TMP_STATE" set-quase-la "teste-3" '{"falta":"telefone"}' >/dev/null
HAS_ANTES="$(python3 "$ESTADO" --file "$TMP_STATE" tem "teste-3")"
python3 "$ESTADO" --file "$TMP_STATE" set-quase-la "teste-3" null >/dev/null
HAS_DEPOIS="$(python3 "$ESTADO" --file "$TMP_STATE" tem "teste-3")"
if [ "$HAS_ANTES" = "sim quase_la" ] && echo "$HAS_DEPOIS" | grep -q "^nao"; then
  relata 0 "set-quase-la grava e null remove"
else
  echo "antes=$HAS_ANTES depois=$HAS_DEPOIS"
  relata 1 "set-quase-la grava e null remove"
fi

# 6 — rodizio-avancar avanca proximo para o item seguinte da ordem.
python3 "$ESTADO" --file "$TMP_STATE" rodizio-avancar >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" resumo | grep -q "rodizio.proximo=linkedin"; then
  relata 0 "rodizio-avancar avanca para o proximo da ordem"
else
  relata 1 "rodizio-avancar avanca para o proximo da ordem"
fi

# 7 — descartes soma incrementos e grava total.
python3 "$ESTADO" --file "$TMP_STATE" descartes 2 1 3 >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" resumo | grep -q '"total": 6'; then
  relata 0 "descartes soma nivel+modelo+stack no total"
else
  relata 1 "descartes soma nivel+modelo+stack no total"
fi

# 8 — status com EMAIL_DATA grava email_data + fonte gmail no historico.
python3 "$ESTADO" --file "$TMP_STATE" status "teste-1" etapa_teste "" 2026-09-17 >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" get "teste-1" | tr -d ' \n' | grep -q '"email_data":"2026-09-17","fonte":"gmail"'; then
  relata 0 "status com EMAIL_DATA grava email_data + fonte gmail"
else
  relata 1 "status com EMAIL_DATA grava email_data + fonte gmail"
fi

# 9 — status sem EMAIL_DATA (follow-up manual) nao grava fonte.
python3 "$ESTADO" --file "$TMP_STATE" status "teste-1" entrevista >/dev/null
if python3 "$ESTADO" --file "$TMP_STATE" get "teste-1" | tr -d ' \n' | grep -q '"para":"entrevista","em":"[^"]*"}'; then
  relata 0 "status sem EMAIL_DATA nao grava fonte"
else
  relata 1 "status sem EMAIL_DATA nao grava fonte"
fi

# 10 — resumo compacto: bloqueado aparece so como empresa (sem o motivo); ja-visto traz o detalhe.
python3 "$ESTADO" --file "$TMP_STATE" add-bloqueado "zeta_backend_jr" '{"empresa":"ZetaSoft","vaga":"Desenvolvedor Backend Java","motivo":"exige CPF ausente"}' >/dev/null
OUT10="$(python3 "$ESTADO" --file "$TMP_STATE" resumo)"
if echo "$OUT10" | grep -q "ZetaSoft" && ! echo "$OUT10" | grep -q "exige CPF ausente"; then
  relata 0 "resumo lista bloqueado so por empresa, sem motivo"
else
  relata 1 "resumo lista bloqueado so por empresa, sem motivo"
fi

# 11 — ja-visto: mesma vaga (titulo parecido) x mesma empresa (outro titulo).
OUT11A="$(python3 "$ESTADO" --file "$TMP_STATE" ja-visto "Zeta Soft" "Backend Java Junior")"
OUT11B="$(python3 "$ESTADO" --file "$TMP_STATE" ja-visto "ZetaSoft" "Analista de Marketing")"
if echo "$OUT11A" | grep -q "^MESMA VAGA provavel | bloqueados" && echo "$OUT11B" | grep -q "^mesma empresa"; then
  relata 0 "ja-visto separa MESMA VAGA provavel de mesma empresa"
else
  echo "A=$OUT11A B=$OUT11B"
  relata 1 "ja-visto separa MESMA VAGA provavel de mesma empresa"
fi

# 12 — ja-visto de empresa desconhecida.
OUT12="$(python3 "$ESTADO" --file "$TMP_STATE" ja-visto "EmpresaInexistenteXyz" "Dev")"
if [ "$OUT12" = "nao visto: pode avaliar" ]; then
  relata 0 "ja-visto empresa desconhecida -> nao visto"
else
  relata 1 "ja-visto empresa desconhecida -> nao visto"
fi

# 13-15 — add-aplicada grava a cobertura ATS sozinho (anuncio salvo < 20 min); anuncio velho ou sem CV = nada.
# check_ats.py real precisa de PDF + extrator; aqui um stub imprime as MESMAS linhas (formato conferido no teste 15).
ATS_D="$(mktemp -d)"
trap 'cleanup; rm -rf "$ATS_D"' EXIT
cat > "$ATS_D/check_ats_stub.py" <<'PYEOF'
import sys
print("termos tecnicos no anuncio: 8 (perfil: 5 | fora do perfil: 3)")
print("cobertura geral do CV: 62%")
print("cobertura dos termos DO PERFIL: 80%")
PYEOF
: > "$ATS_D/CV_Teste.pdf"
echo "Vaga Desenvolvedor Backend Junior Python remoto" > "$ATS_D/anuncio.txt"
export OV_CHECK_ATS="$ATS_D/check_ats_stub.py"
ANUNCIO_FILE="$ATS_D/anuncio.txt" python3 "$ESTADO" --file "$TMP_STATE" add-aplicada "{\"chave\":\"ats-1\",\"empresa\":\"AtsCo\",\"vaga\":\"Dev Jr\",\"cv\":\"$ATS_D/CV_Teste.pdf\"}" >/dev/null
python3 "$ESTADO" --file "$TMP_STATE" get ats-1 | tr -d ' \n' | grep -q '"ats":{"geral":62,"perfil":80}'
relata $? "add-aplicada grava ats {geral, perfil} com anuncio recente"

touch -d '-1 hour' "$ATS_D/anuncio.txt"
ANUNCIO_FILE="$ATS_D/anuncio.txt" python3 "$ESTADO" --file "$TMP_STATE" add-aplicada "{\"chave\":\"ats-2\",\"empresa\":\"AtsCo2\",\"vaga\":\"Dev Jr 2\",\"cv\":\"$ATS_D/CV_Teste.pdf\"}" >/dev/null
ANUNCIO_FILE="$ATS_D/anuncio.txt" python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"ats-3","empresa":"AtsCo3","vaga":"Dev Jr 3"}' >/dev/null
! python3 "$ESTADO" --file "$TMP_STATE" get ats-2 | grep -q '"ats"' && ! python3 "$ESTADO" --file "$TMP_STATE" get ats-3 | grep -q '"ats"'
relata $? "anuncio velho (> 20 min) ou registro sem CV_*.pdf: nada e gravado"

unset OV_CHECK_ATS
grep -q 'cobertura geral do CV: %d%%' bot/check_ats.py && grep -q 'cobertura dos termos DO PERFIL: %d%%' bot/check_ats.py
relata $? "formato lido do check_ats.py real continua igual ao que estado.py espera"

# 16 — status fora do padrao e recusado (add-aplicada e status).
python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"teste-st","empresa":"X","vaga":"Y","status":"enviada - pendente"}' >/dev/null 2>&1
A=$?; python3 "$ESTADO" --file "$TMP_STATE" status teste-1 inventado >/dev/null 2>&1; B=$?
[ "$A" -ne 0 ] && [ "$B" -ne 0 ] && ! python3 "$ESTADO" --file "$TMP_STATE" tem teste-st >/dev/null 2>&1
relata $? "status fora do padrao e recusado (nada gravado)"

# 17 — del-aplicada arquiva em aplicadas_removidas (nao apaga).
python3 "$ESTADO" --file "$TMP_STATE" del-aplicada teste-1 "duplicata de teste" >/dev/null
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert not any(a['chave']=='teste-1' for a in d['aplicadas']) and d['aplicadas_removidas'][-1]['motivo_remocao']=='duplicata de teste'" "$TMP_STATE"
relata $? "del-aplicada arquiva o registro com o motivo"

# 18 — argumento faltando mostra so o uso do comando, sem traceback.
OUT18="$(python3 "$ESTADO" --file "$TMP_STATE" add-bloqueado 2>&1)"
echo "$OUT18" | grep -q "add-bloqueado CHAVE JSON" && ! echo "$OUT18" | grep -q Traceback
relata $? "argumento faltando: uso do comando, sem traceback"

# 19 — resumo-candidato: campos principais, documentos fora.
OUT19="$(DADOS_CANDIDATO_FILE=examples/dados_candidato.example.json python3 "$ESTADO" resumo-candidato)"
echo "$OUT19" | grep -q "^nome: " && echo "$OUT19" | grep -q "fora do resumo.*documentos" && ! echo "$OUT19" | grep -q '"cpf"'
relata $? "resumo-candidato traz o essencial e deixa documentos fora"

# 20 — dado CAMPO.SUB le um campo aninhado.
DADOS_CANDIDATO_FILE=examples/dados_candidato.example.json python3 "$ESTADO" dado experiencia.tecnologias | grep -q .
relata $? "dado le campo aninhado do dados_candidato"

if # 21 — descartes: placeholder copiado e recusado sem traceback; rotulos aceitos.
OUT21="$(python3 "$ESTADO" --file "$TMP_STATE" descartes NIVEL MODELO STACK 2>&1)"; A=$?
python3 "$ESTADO" --file "$TMP_STATE" descartes nivel 1 modelo 2 stack 3 >/dev/null 2>&1; B=$?
[ "$A" -ne 0 ] && [ "$B" -eq 0 ] && ! echo "$OUT21" | grep -q Traceback \
  && python3 -c "import json,sys;assert json.load(open(sys.argv[1]))['descartes_listagem']['stack']>=3" "$TMP_STATE"
relata $? "descartes: placeholder recusado sem traceback, rotulos aceitos"

# 22 — add-aplicada sem status grava "enviada" (o funil nao perde a candidatura).
python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"z_dev_77","empresa":"Z","vaga":"Dev","url":"https://z.example/77"}' >/dev/null 2>&1
python3 -c "import json,sys;assert [a for a in json.load(open(sys.argv[1]))['aplicadas'] if a['chave']=='z_dev_77'][0]['status']=='enviada'" "$TMP_STATE"
relata $? "add-aplicada sem status grava enviada"

# 23 — OV_RODADA vira "rodada" no registro; set-campo grava um campo (JSON ou texto).
OV_RODADA=R9 python3 "$ESTADO" --file "$TMP_STATE" add-aplicada '{"chave":"y_dev_78","empresa":"Y","vaga":"Dev"}' >/dev/null 2>&1
python3 "$ESTADO" --file "$TMP_STATE" set-campo y_dev_78 caminho fila >/dev/null 2>&1
python3 -c "import json,sys;a=[a for a in json.load(open(sys.argv[1]))['aplicadas'] if a['chave']=='y_dev_78'][0];assert a['rodada']=='R9' and a['caminho']=='fila',a" "$TMP_STATE"
relata $? "OV_RODADA carimba rodada; set-campo grava campo"

[ "$FAIL" -eq 0 ]; then
  echo "# verde: $N/$TOTAL"
  exit 0
else
  echo "# FALHAS: $FAIL/$TOTAL"
  exit 1
fi
