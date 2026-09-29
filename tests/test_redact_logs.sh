#!/bin/bash
# tests/test_redact_logs.sh — bot/redact-logs.py com vazamentos SINTETICOS (saida TAP).
# Os "segredos" sao montados em tempo de execucao (nada com formato real fica no arquivo).
# Uso: bash tests/test_redact_logs.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
RL="$ROOT/bot/redact-logs.py"

TOTAL=10
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/logs"

PW_FILE="Cred#pass$(printf 'x%.0s' 1 2 3)77"      # password stored in the credentials file
PW_NEW="Novo#pass$(printf 'y%.0s' 1 2 3)55"       # password only typed in a printf (not in the file yet)
PW_FIELD="Campo#pass$(printf 'z%.0s' 1 2 3)33"    # password typed into a form field
TG="123456789:$(printf 'A%.0s' $(seq 35))"
KEY="sk-""or-""v1-$(printf 'b%.0s' $(seq 40))"
CPF="$(printf '%s.%s.%s-%s' 111 222 333 44)"

printf 'site.example\tuser@example.org\t%s\n' "$PW_FILE" > "$T/credenciais.tsv"
export OV_CREDENTIALS_FILE="$T/credenciais.tsv"
export OV_REDACT_GLOBS="$T/logs/*.log:$T/logs/*.log.gz"
[ "$(uname -s | cut -c1-5)" = "MINGW" ] && export OV_REDACT_GLOBS="$T/logs/*.log;$T/logs/*.log.gz"

cat > "$T/leaky.txt" <<TXT
tool browser_navigate {"url":"https://jobs.example/vaga/1234567890"}
Error: element not found for selector #apply
chave: gupy_9876543 empresa Acme vaga 4829131
login ok with $PW_FILE on the page
tool fill_form {"fields":[{"label":"Nome","value":"Fulano Teste"},{"label":"Senha","value":"$PW_FIELD"}]}
+ printf "%s\t%s\t%s\n" "site.example" "user@example.org" "$PW_NEW" >> /tmp/x/credenciais.tsv
telegram bot $TG and key $KEY
CPF do candidato $CPF no formulario
Seu código de verificação é 605817, use em 10 minutos
TXT

novo_log() { cp "$T/leaky.txt" "$1"; touch -d "${2:-2 hours ago}" "$1"; }
novo_log "$T/logs/velho.log"
OUT="$("$PY" "$RL")"
LOG="$(cat "$T/logs/velho.log")"

! echo "$LOG$OUT" | grep -qF -e "$PW_FILE" -e "$PW_FIELD" -e "$PW_NEW"; relata $? "senhas (arquivo de credenciais, campo de formulario, printf) mascaradas"
! echo "$LOG" | grep -qF -e "$TG" -e "$KEY" -e "$CPF" -e "605817"; relata $? "token de bot, chave de API, CPF e codigo de 6 digitos mascarados"
echo "$LOG" | grep -q 'browser_navigate {"url":"https://jobs.example/vaga/1234567890"}' \
  && echo "$LOG" | grep -q '^Error: element not found for selector #apply$' \
  && echo "$LOG" | grep -q 'chave: gupy_9876543 empresa Acme vaga 4829131' \
  && echo "$LOG" | grep -q '"value":"Fulano Teste"'; relata $? "IDs de vaga, linhas Error:/browser_navigate e campos comuns sobrevivem"
echo "$OUT" | grep -q "1 limpos"; relata $? "saida so tem contagens ($OUT)"

# idempotent: a clean file is not rewritten
M1="$(stat -c %Y "$T/logs/velho.log")"; sleep 1
"$PY" "$RL" >/dev/null
[ "$M1" = "$(stat -c %Y "$T/logs/velho.log")" ]; relata $? "segunda varredura nao reescreve arquivo limpo"

# fresh log (< 30 min): skipped unless --forcar
novo_log "$T/logs/ativo.log" "now"
"$PY" "$RL" >/dev/null
grep -qF "$PW_FILE" "$T/logs/ativo.log"; relata $? "log modificado ha < 30 min nao e tocado"
"$PY" "$RL" --forcar "$T/logs/ativo.log" >/dev/null
! grep -qF "$PW_FILE" "$T/logs/ativo.log"; relata $? "--forcar limpa o log da rodada que acabou de fechar"

# gzip
cp "$T/leaky.txt" "$T/logs/rot.log"; gzip -f "$T/logs/rot.log"; touch -d '2 hours ago' "$T/logs/rot.log.gz"
"$PY" "$RL" >/dev/null
! gzip -dc "$T/logs/rot.log.gz" | grep -qF "$PW_FILE" && gzip -dc "$T/logs/rot.log.gz" | grep -q 'browser_navigate'; relata $? ".gz e limpo e continua valido"

# file mode preserved, no tmp left behind
chmod 640 "$T/logs/velho.log"; novo_log "$T/logs/modo.log"; chmod 640 "$T/logs/modo.log"; touch -d '2 hours ago' "$T/logs/modo.log"
"$PY" "$RL" >/dev/null
[ "$(stat -c %a "$T/logs/modo.log")" = "640" ] && [ -z "$(find "$T" -name '*.redact.tmp')" ]; relata $? "permissoes preservadas e sem .redact.tmp"

# without a credentials file the pattern-based masking still works
OV_CREDENTIALS_FILE="$T/nao-existe.tsv" "$PY" "$RL" --forcar "$T/logs/ativo.log" >/dev/null 2>&1
relata $? "arquivo de credenciais ausente nao quebra a varredura"

if [ "$FAIL" -eq 0 ]; then echo "# verde: $N/$TOTAL"; exit 0; else echo "# FALHAS: $FAIL/$TOTAL"; exit 1; fi
