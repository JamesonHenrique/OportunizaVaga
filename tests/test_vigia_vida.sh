#!/bin/bash
# tests/test_vigia_vida.sh — bot/vigia-vida.sh (dead man's switch): loop parado em 2 checagens, heartbeat velho/ausente,
# MONITOR_URL opcional, estado ilegivel. Offline: servidor HTTP local no loopback, NOTIFY falso, estado em diretorio temporario.
# Uso: bash tests/test_vigia_vida.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"

TOTAL=7
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMP="$(mktemp -d)"
SRV=""
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; [ -n "${SLP:-}" ] && kill "$SLP" 2>/dev/null; rm -rf "$TMP"; }
trap cleanup EXIT

# Notificador falso: grava a mensagem recebida.
cat > "$TMP/notify.sh" <<'SH'
#!/bin/bash
printf '%s\n' "$1" >> "$NOTIF_OUT"
SH
chmod +x "$TMP/notify.sh"
export NOTIF_OUT="$TMP/notif.txt" NOTIFY="$TMP/notify.sh" VIGIA_STATE="$TMP/falhas"
cp examples/aplicadas.example.json "$TMP/aplicadas.json"
export APLICADAS_FILE="$TMP/aplicadas.json" STATE_DIR="$TMP"
unset MONITOR_URL HB_MAX_MIN

# "Loop" falso: um processo com nome unico que o padrao do vigia encontra; padrao inexistente = loop parado.
cp "$(command -v sleep)" "$TMP/loopfalso-$$"
"$TMP/loopfalso-$$" 300 & SLP=$!
VIVO="loopfalso-$$"
MORTO="loop-que-nao-existe-$$"

# 1 — tudo ok (loop vivo, sem MONITOR_URL, estado legivel): exit 0, nada notificado.
VIGIA_LOOP_PATTERN="$VIVO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC=$?
[ "$RC" -eq 0 ] && [ ! -s "$NOTIF_OUT" ]
relata $? "tudo ok: exit 0 e sem notificacao (MONITOR_URL ausente = checagem do monitor pulada)"

# 2 — loop parado: 1a checagem so conta (normal), 2a avisa.
rm -f "$VIGIA_STATE"
VIGIA_LOOP_PATTERN="$MORTO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC1=$?
VIGIA_LOOP_PATTERN="$MORTO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC2=$?
[ "$RC1" -eq 0 ] && [ "$RC2" -eq 2 ] && grep -q "loop.sh parado" "$NOTIF_OUT"
relata $? "loop parado: silencio na 1a checagem, alerta na 2a (rc $RC1/$RC2)"

# 3 — loop volta: contador zera.
VIGIA_LOOP_PATTERN="$VIVO" bash bot/vigia-vida.sh >/dev/null 2>&1
[ ! -e "$VIGIA_STATE" ]
relata $? "loop de volta zera o contador de falhas"

# Servidor local do heartbeat: /api/status?ping=1 devolve updatedAt = agora - HB_IDADE_MIN.
cat > "$TMP/srv.py" <<'PYEOF'
import datetime as D, http.server, json, os, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        idade = int(open(os.environ["HB_FILE"]).read())
        u = (D.datetime.now(D.timezone.utc) - D.timedelta(minutes=idade)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        body = json.dumps({"ok": True, "ping": True, "updatedAt": None if idade < 0 else u}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
s = http.server.HTTPServer(("127.0.0.1", 0), H)
open(os.environ["PORT_FILE"], "w").write(str(s.server_port))
s.serve_forever()
PYEOF
export HB_FILE="$TMP/hb" PORT_FILE="$TMP/port"
echo 3 > "$HB_FILE"
"$PY" "$TMP/srv.py" & SRV=$!
for _ in $(seq 1 50); do [ -s "$PORT_FILE" ] && break; sleep 0.1; done
PORT="$(cat "$PORT_FILE")"

# 4 — heartbeat recente: ok.
: > "$NOTIF_OUT"
MONITOR_URL="http://127.0.0.1:$PORT" VIGIA_LOOP_PATTERN="$VIVO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC=$?
[ "$RC" -eq 0 ] && [ ! -s "$NOTIF_OUT" ]
relata $? "heartbeat de 3 min: ok"

# 5 — heartbeat velho (60 min > HB_MAX_MIN=20): alerta.
echo 60 > "$HB_FILE"
MONITOR_URL="http://127.0.0.1:$PORT" VIGIA_LOOP_PATTERN="$VIVO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC=$?
[ "$RC" -eq 2 ] && grep -q "heartbeat do monitor ha 60 min" "$NOTIF_OUT"
relata $? "heartbeat velho: alerta com a idade"

# 6 — monitor inalcancavel / sem updatedAt: alerta 'sem heartbeat'.
: > "$NOTIF_OUT"
MONITOR_URL="http://127.0.0.1:1" VIGIA_LOOP_PATTERN="$VIVO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC=$?
[ "$RC" -eq 2 ] && grep -q "sem heartbeat" "$NOTIF_OUT"
relata $? "monitor inalcancavel: alerta 'sem heartbeat'"

# 7 — estado ilegivel ou ausente: alerta.
: > "$NOTIF_OUT"
echo '{corrompido' > "$APLICADAS_FILE"
VIGIA_LOOP_PATTERN="$VIVO" bash bot/vigia-vida.sh >/dev/null 2>&1; RC=$?
[ "$RC" -eq 2 ] && grep -q "aplicadas.json ausente ou ilegivel" "$NOTIF_OUT"
relata $? "aplicadas.json corrompido: alerta"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
