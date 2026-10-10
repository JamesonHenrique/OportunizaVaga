#!/bin/bash
# tests/test_notificar.sh — dedupe do scripts/notificar.sh (saida TAP). curl falso no PATH: nada sai da maquina.
# Uso: bash tests/test_notificar.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TOTAL=4
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT
mkdir -p "$TMPD/bin"
# fake curl: counts calls; exit code comes from $TMPD/rc (22 = what curl -f returns on HTTP 4xx/5xx)
cat > "$TMPD/bin/curl" <<SH
#!/bin/bash
echo x >> "$TMPD/chamadas"
exit \$(cat "$TMPD/rc" 2>/dev/null || echo 0)
SH
chmod +x "$TMPD/bin/curl"
export PATH="$TMPD/bin:$PATH" TELEGRAM_BOT_TOKEN=fake TELEGRAM_CHAT_ID=1 OV_NOTIFY_STATE="$TMPD/notify-sent"
envios() { wc -l < "$TMPD/chamadas" 2>/dev/null || echo 0; }

bash scripts/notificar.sh "validate-rodada reprovou as 10:02 (3 itens)"
bash scripts/notificar.sh "validate-rodada reprovou as 10:22 (5 itens)"
[ "$(envios)" -eq 1 ]; relata $? "mesmo alerta com numeros diferentes sai uma vez so na janela"

bash scripts/notificar.sh "monitor parado"
[ "$(envios)" -eq 2 ]; relata $? "alerta diferente sai"

echo 22 > "$TMPD/rc"
bash scripts/notificar.sh "chrome caiu"
echo 0 > "$TMPD/rc"
bash scripts/notificar.sh "chrome caiu"
[ "$(envios)" -eq 4 ]; relata $? "envio recusado pela API (curl -f != 0) nao conta: a proxima tentativa sai"

OV_NOTIFY_JANELA_S=0 bash scripts/notificar.sh "monitor parado"
[ "$(envios)" -eq 5 ]; relata $? "janela configuravel (OV_NOTIFY_JANELA_S)"

exit $((FAIL > 0))
