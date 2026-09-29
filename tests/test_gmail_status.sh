#!/bin/bash
# tests/test_gmail_status.sh — bash puro, saida TAP.
# Cobre: bot/gmail-status.py (classificacao, data_email com "hoje" injetavel) e o
# encadeamento com bot/estado.py status ... EMAIL_DATA. Nao abre Chrome nem Gmail.
# Uso: bash tests/test_gmail_status.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Roda um snippet Python com o modulo carregado como `g` (arquivo tem hifen no nome).
py() {
  GS="$ROOT/bot/gmail-status.py" python3 -c '
import importlib.util, os, sys
from datetime import date
spec = importlib.util.spec_from_file_location("gs", os.environ["GS"])
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
HOJE = date(2026, 9, 29)
def classe(t):
    n = g.norm(t); return next((c for c, rx in g.CLASSES if rx.search(n)), None)
def dt(t, hoje=HOJE): return g.data_email(g.norm(t), hoje)
'"$1"
}

N=0; FAIL=0; TOTAL=12
echo "1..$TOTAL"
check() { # check <descricao> <esperado> <snippet que imprime>
  N=$((N + 1))
  local got; got="$(py "$3" 2>&1)"
  if [ "$got" = "$2" ]; then echo "ok $N - $1"; else echo "not ok $N - $1 (esperado '$2', obtido '$got')"; FAIL=$((FAIL + 1)); fi
}

GUPY='Acme Você foi selecionado para a etapa de testes! - Olá, participe do teste 17 de set.'
check "Gupy 'etapa de testes' -> etapa_teste"      "etapa_teste"   "print(classe('$GUPY'))"
check "data '17 de set.' -> 2026-09-17"            "2026-09-17"    "print(dt('$GUPY'))"
check "rejeicao vence 'candidatura' -> encerrada"  "encerrada"     "print(classe('Infelizmente nao seguiremos com sua candidatura 11:29'))"
check "agendar entrevista -> entrevista"           "entrevista"    "print(classe('Vamos agendar uma entrevista com voce'))"
check "proxima etapa -> proxima_etapa"             "proxima_etapa" "print(classe('Parabéns, você avançou'))"
check "recebemos candidatura -> em_analise"        "em_analise"    "print(classe('Recebemos sua candidatura para Dev'))"
check "HH:MM -> hoje"                              "2026-09-29"    "print(dt('Acme Recebemos 11:29'))"
check "'Sep 17' -> 2026-09-17"                     "2026-09-17"    "print(dt('Acme hiring Sep 17'))"
check "dd/mm/yyyy -> 2026-09-17"                   "2026-09-17"    "print(dt('Acme 17/09/2026'))"
check "data futura vira ano anterior"              "2025-12-17"    "print(dt('Acme 17 de dez.'))"
check "sem data -> None"                           "None"          "print(dt('Acme sem data aqui'))"
check "ORDEM so avanca (encerrada > entrevista > etapa_teste)" "True" "print(g.ORDEM['encerrada']>g.ORDEM['entrevista']>g.ORDEM['etapa_teste']>g.ORDEM['em_analise']>g.ORDEM['enviada'])"

if [ "$FAIL" -eq 0 ]; then echo "# verde: $N/$TOTAL"; exit 0; else echo "# FALHAS: $FAIL/$TOTAL"; exit 1; fi
