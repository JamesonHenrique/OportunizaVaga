#!/bin/bash
# tests/test_cv_pronto.sh — ATS gate before attaching a per-job CV (bot/cv-pronto.sh), TAP output.
# Uses only the fictitious examples/ files; gerar_cv.py reads them through CV_BASE_FILE/DADOS_CANDIDATO_FILE.
# Uso: bash tests/test_cv_pronto.sh   (exit 0 = tudo verde; skips when reportlab is missing)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
TOTAL=4
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

if ! python3 -c 'import reportlab' 2>/dev/null; then
  for i in $(seq $TOTAL); do echo "ok $i # SKIP reportlab ausente"; done; exit 0
fi
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export CV_BASE_FILE="$ROOT/examples/cv_base.example.md" DADOS_CANDIDATO_FILE="$ROOT/examples/dados_candidato.example.json"
export OV_ATS_LOG="$T/ats.log"
cat > "$T/spec.json" <<'J'
{"empresa":"Acme","vaga":"Dev Java","titulo_alvo":"Desenvolvedor Java","resumo_custom":"Desenvolvedor Java com Spring Boot e PostgreSQL, atuando com Angular e APIs REST.","categorias_ordem":["Backend"],"so_categorias":["Backend","Frontend","Banco de dados"],"palavras_chave_vaga":["Java","Spring Boot","PostgreSQL"]}
J
echo "Requisitos: Java, Spring Boot e PostgreSQL." > "$T/anuncio.txt"

python3 bot/gerar_cv.py "$T/spec.json" "$T/CV_Teste_Acme.pdf" >/dev/null 2>&1
relata $? "gerar_cv.py gera o PDF com cv_base/dados vindos do ambiente"

out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf"); rc=$?
[ $rc -eq 0 ] && grep -q "^ANEXAR $T/CV_Teste_Acme.pdf" <<<"$out"; relata $? "aprovado: exit 0 e linha ANEXAR com o caminho"

out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/nao-existe.pdf"); rc=$?
[ $rc -eq 2 ] && ! grep -q "^ANEXAR" <<<"$out"; relata $? "PDF ausente: exit 2 e nenhuma linha ANEXAR"

[ "$(grep -c ' rc=' "$OV_ATS_LOG")" -eq 2 ] && grep -q "rc=2 cv=nao-existe.pdf" "$OV_ATS_LOG"
relata $? "cada veredito fica no log ATS"

exit $((FAIL > 0))
