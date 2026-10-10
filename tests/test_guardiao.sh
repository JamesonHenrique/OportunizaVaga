#!/bin/bash
# tests/test_guardiao.sh — bot/guardiao.sh nao mata as cegas quem segura o lock (saida TAP).
# Copia o guardiao para uma arvore temporaria com loop.sh/chrome falsos; curl falso diz que o CDP esta de pe.
# Uso: bash tests/test_guardiao.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK=/tmp/oportunizavaga-loop.lock
if pgrep -f "bot/loop\.sh" >/dev/null || fuser "$LOCK" >/dev/null 2>&1; then
  echo "1..0 # SKIP loop real ativo nesta maquina (o teste usa o mesmo lock)"; exit 0
fi
command -v fuser >/dev/null || { echo "1..0 # SKIP fuser ausente"; exit 0; }

TOTAL=3
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMPD="$(mktemp -d)"
PIDS=()
trap 'kill "${PIDS[@]}" 2>/dev/null; rm -rf "$TMPD"' EXIT
mkdir -p "$TMPD/bot" "$TMPD/browser" "$TMPD/bin"
cp "$ROOT/bot/guardiao.sh" "$TMPD/bot/"
printf '#!/bin/bash\necho subiu >> "%s/subidas"\n' "$TMPD" > "$TMPD/bot/loop.sh"
printf '#!/bin/bash\nexit 0\n' > "$TMPD/browser/chrome-real.sh"
printf '#!/bin/bash\nexit 0\n' > "$TMPD/bin/curl"
chmod +x "$TMPD/bot/loop.sh" "$TMPD/browser/chrome-real.sh" "$TMPD/bin/curl"
G() { PATH="$TMPD/bin:$PATH" bash "$TMPD/bot/guardiao.sh"; sleep 0.5; }
subidas() { if [ -f "$TMPD/subidas" ]; then wc -l < "$TMPD/subidas"; else echo 0; fi; }

# a python child still working, holding the lock fd (like descobrir.py inheriting fd 9)
python3 -c 'import fcntl,time; f=open("/tmp/oportunizavaga-loop.lock","a"); fcntl.flock(f, fcntl.LOCK_EX); time.sleep(60)' &
PIDS+=($!); sleep 0.5
G
kill -0 "${PIDS[0]}" 2>/dev/null && [ "$(subidas)" -eq 0 ]
relata $? "orfao recente trabalhando: nao e morto e o loop nao sobe por cima"

OV_GUARDIAO_ORFAO_S=0 PATH="$TMPD/bin:$PATH" bash "$TMPD/bot/guardiao.sh"; sleep 0.5
! kill -0 "${PIDS[0]}" 2>/dev/null && [ "$(subidas)" -eq 1 ]
relata $? "orfao alem do limite: morto e o loop sobe"

( exec 9>>"$LOCK"; flock 9; exec sleep 60 ) &
PIDS+=($!); sleep 0.5
G
! kill -0 "${PIDS[1]}" 2>/dev/null && [ "$(subidas)" -eq 2 ]
relata $? "sleep orfao segurando o lock: morto na hora"

exit $((FAIL > 0))
