#!/bin/bash
# tests/test_cv_pronto.sh — ATS gate before attaching a per-job CV (bot/cv-pronto.sh), TAP output.
# Uses only the fictitious examples/ files; gerar_cv.py reads them through CV_BASE_FILE/DADOS_CANDIDATO_FILE.
# Uso: bash tests/test_cv_pronto.sh   (exit 0 = tudo verde; skips when reportlab is missing)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
TOTAL=9
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
export OV_RESUME_MATCHER_MANIFEST_DIR="$T/manifests"
cat > "$T/spec.json" <<'J'
{"empresa":"Acme","vaga":"Dev Java","titulo_alvo":"Desenvolvedor Java","resumo_custom":"Desenvolvedor Java com Spring Boot e PostgreSQL, atuando com Angular e APIs REST.","categorias_ordem":["Backend"],"so_categorias":["Backend","Frontend","Banco de dados"],"palavras_chave_vaga":["Java","Spring Boot","PostgreSQL"]}
J
echo "Requisitos: Java, Spring Boot e PostgreSQL." > "$T/anuncio.txt"

python3 bot/gerar_cv.py "$T/spec.json" "$T/CV_Teste_Acme.pdf" >/dev/null 2>&1
relata $? "gerar_cv.py gera o PDF com cv_base/dados vindos do ambiente"

out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf"); rc=$?
[ $rc -eq 0 ] && grep -q "^ANEXAR $T/CV_Teste_Acme.pdf" <<<"$out"; relata $? "aprovado: exit 0 e linha ANEXAR com o caminho"

cat > "$T/fake-resume-matcher" <<'PY'
#!/usr/bin/env python3
import json, os, sys
if os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("unexpected credential in child environment")
checks = [{"id": "text_layer", "category": "extraction", "severity": "high", "status": "pass"}]
print(json.dumps({"extractability": "full", "overall_score": 96, "page_count": 1, "checks": checks}))
PY
chmod +x "$T/fake-resume-matcher"
export OV_RESUME_MATCHER_REQUIRED=1 OV_RESUME_MATCHER_CLI="$T/fake-resume-matcher"
export OV_RESUME_MATCHER_DATA_DIR="$T/rm-data" OPENAI_API_KEY="test-only-must-not-propagate"
export OV_RESUME_MATCHER_REVISION=d480551798b7aa97f5b57ba1972ee383bd882238
out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf"); rc=$?
[ $rc -eq 0 ] && grep -q '"status": "APPROVED"' <<<"$out" && grep -q '"manifest_id":' <<<"$out" \
  && grep -q "^ANEXAR $T/CV_Teste_Acme.pdf" <<<"$out" && [ "$(find "$T/manifests" -name '*.json' | wc -l)" -eq 1 ]
relata $? "Resume-Matcher aprovado persiste e revalida o par exato vaga/PDF antes de liberar"

cat > "$T/fake-resume-matcher" <<'PY'
#!/usr/bin/env python3
import json
print(json.dumps({"extractability":"full","overall_score":96,"page_count":1,
  "checks":[{"id":"multi_column","category":"layout","severity":"medium","status":"warn"}]}))
PY
chmod +x "$T/fake-resume-matcher"
out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf"); rc=$?
[ $rc -eq 1 ] && grep -q '"status": "NEEDS_REVIEW"' <<<"$out" && ! grep -q '^ANEXAR ' <<<"$out"
relata $? "aviso do Resume-Matcher bloqueia anexo até revisão"

cat > "$T/fake-resume-matcher" <<'PY'
#!/usr/bin/env python3
import json
print(json.dumps({"extractability":"full","overall_score":96,"page_count":1,
  "checks":[{"id":"text_layer","category":"extraction","severity":"high","status":"pass"}]}))
PY
chmod +x "$T/fake-resume-matcher"
unset OV_RESUME_MATCHER_REVISION
out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf"); rc=$?
[ $rc -eq 2 ] && grep -q 'OV_RESUME_MATCHER_REVISION' <<<"$out" && ! grep -q '^ANEXAR ' <<<"$out"
relata $? "sem commit pinado, manifesto e anexo ficam UNVERIFIABLE"
export OV_RESUME_MATCHER_REVISION=d480551798b7aa97f5b57ba1972ee383bd882238

export OV_RESUME_MATCHER_CLI="$T/nao-existe"
out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf"); rc=$?
[ $rc -eq 2 ] && grep -q '"status": "UNVERIFIABLE"' <<<"$out" && ! grep -q '^ANEXAR ' <<<"$out"
relata $? "CLI indisponível retorna UNVERIFIABLE e bloqueia anexo"

cat > "$T/fake-resume-matcher" <<'PY'
#!/usr/bin/env python3
import json
print(json.dumps({"extractability":"full","overall_score":96,"page_count":1,
  "checks":[{"id":"text_layer","category":"extraction","severity":"high","status":"pass"}]}))
PY
chmod +x "$T/fake-resume-matcher"
export OV_RESUME_MATCHER_CLI="$T/fake-resume-matcher"
out=$(OV_ATS_LOG=/dev/full bot/cv-pronto.sh "$T/anuncio.txt" "$T/CV_Teste_Acme.pdf" 2>/dev/null); rc=$?
[ $rc -eq 2 ] && grep -q 'AUDIT_LOG_UNAVAILABLE' <<<"$out" && ! grep -q '^ANEXAR ' <<<"$out"
relata $? "falha ao registrar a auditoria transforma aprovação em UNVERIFIABLE"

out=$(bot/cv-pronto.sh "$T/anuncio.txt" "$T/nao-existe.pdf"); rc=$?
[ $rc -eq 2 ] && ! grep -q "^ANEXAR" <<<"$out"; relata $? "PDF ausente: exit 2 e nenhuma linha ANEXAR"

[ "$(grep -c ' rc=' "$OV_ATS_LOG")" -eq 6 ] && grep -q "rc=2 cv=nao-existe.pdf" "$OV_ATS_LOG" \
  && grep -q 'rm_status=APPROVED' "$OV_ATS_LOG" && grep -q 'rm_status=NEEDS_REVIEW' "$OV_ATS_LOG" \
  && grep -q 'rm_status=UNVERIFIABLE' "$OV_ATS_LOG"
relata $? "cada veredito fica no log ATS"

exit $((FAIL > 0))
