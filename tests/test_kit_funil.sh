#!/bin/bash
# Cobre: bot/kit-entrevista.py (kit 1x por status, lembrete no dia, respeita "feito") e bot/funil-fontes.py
# (envio -> retorno -> avanco por fonte; "sem resposta >21d" derivado, sem mudar status). Offline.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
N=0; FAIL=0; TOTAL=2
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

APLICADAS_FILE="$TMP/a.json" OV_GMAIL_STATUS="$TMP/g.json" python3 - "$ROOT" <<'PY'
import json, os, sys, importlib.util, datetime as D
s = importlib.util.spec_from_file_location("k", sys.argv[1] + "/bot/kit-entrevista.py"); k = importlib.util.module_from_spec(s); s.loader.exec_module(k)
msgs = []; k.avisar = lambda m, dry: msgs.append(m); k.marcar = lambda c, campo, v, dry: [a.update({campo: v}) for a in AP if a["chave"] == c]
json.dump({"achados": [{"chave": "acme_dev_1", "trecho": "Invitation: Entrevista - Acme @ Thu Oct 1, 202"}]}, open(os.environ["OV_GMAIL_STATUS"], "w"))
AP = [{"chave": "acme_dev_1", "empresa": "Acme", "vaga": "Dev Jr", "status": "entrevista"},
      {"chave": "beta_dev_2", "empresa": "Beta", "vaga": "Dev", "status": "etapa_teste", "teste_feito_em": "2026-09-30"}]
# load() returns (data, reason) since ea5e9e1 ("0 aviso(s)" must tell "nothing to do" from "could not see")
k.load = lambda p, d: ({"aplicadas": AP} if p == k.APLICADAS else json.load(open(p)), None)
k.main(hoje=D.date(2026, 9, 30), agora_h=9)
assert len(msgs) == 1 and "Acme" in msgs[0] and "01/10" in msgs[0] and "set-campo acme_dev_1" in msgs[0], msgs
k.main(hoje=D.date(2026, 10, 1), agora_h=9); assert len(msgs) == 2 and msgs[1].startswith("⏰ HOJE"), msgs
k.main(hoje=D.date(2026, 10, 1), agora_h=10); assert len(msgs) == 2, msgs
PY
relata $? "kit-entrevista: kit 1x por status, lembrete no dia, respeita feito"

python3 - "$ROOT" <<'PY'
import sys, importlib.util, datetime as D
s = importlib.util.spec_from_file_location("f", sys.argv[1] + "/bot/funil-fontes.py"); f = importlib.util.module_from_spec(s); s.loader.exec_module(f)
ap = [{"como": "Gupy", "status": "encerrada", "data": "2026-09-01"}, {"como": "Gupy", "status": "entrevista", "data": "2026-09-20"},
      {"url": "https://www.linkedin.com/jobs/view/1/", "status": "enviada", "data": "2026-09-01", "caminho": "fila"}]
p = f.funil(ap, D.date(2026, 10, 1))
assert p[("fonte", "gupy")] == {"envios": 2, "respostas": 2, "avancos": 1, "sem_resposta": 0}, p
assert p[("fonte", "linkedin")]["sem_resposta"] == 1 and p[("caminho", "fila")]["envios"] == 1, p
PY
relata $? "funil-fontes: retorno, avanco e sem resposta >21d por fonte e caminho"

[ "$FAIL" -eq 0 ] && { echo "# verde: $N/$TOTAL"; exit 0; } || { echo "# FALHAS: $FAIL/$TOTAL"; exit 1; }
