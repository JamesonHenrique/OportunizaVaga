#!/bin/bash
# tests/test_opencode_erros.sh — bot/lib/opencode-erros.sh: quota x transient x other robot (TAP output).
# Synthetic opencode log only; never reads the real one.
# Uso: bash tests/test_opencode_erros.sh   (exit 0 = tudo verde)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOTAL=5; N=0; FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/oc"
{
  echo "timestamp=2026-09-30T13:00:00.000Z level=INFO run=aa11 message=\"creating instance\" directory=$T/robo"
  echo "timestamp=2026-09-30T13:00:01.000Z level=INFO run=bb22 message=\"creating instance\" directory=/outro/robo"
  echo 'timestamp=2026-09-30T13:20:48.262Z level=ERROR run=aa11 message="stream error" error.error="AI_APICallError: Service Unavailable"'
  echo 'timestamp=2026-09-30T13:30:00.000Z level=ERROR run=bb22 message="stream error" error.error="Rate limit exceeded"'
} > "$T/oc/opencode.log"
eo() { OC_LOG_DIR="$T/oc" BASE="$T/robo" bash -c ". '$ROOT/bot/lib/opencode-erros.sh'; erro_opencode_log $1 ${2:-}"; }
[ "$(eo 2026-09-30T13:10:00.000Z)" = transitorio ]; relata $? "503 = transitorio (nao e cota)"
[ -z "$(eo 2026-09-30T13:25:00.000Z)" ]; relata $? "cota de OUTRO robo nao conta"
echo 'timestamp=2026-09-30T13:40:00.000Z level=ERROR run=aa11 message="x" error.error="AI_APICallError: Too Many Requests 429"' >> "$T/oc/opencode.log"
[ "$(eo 2026-09-30T13:35:00.000Z)" = quota ]; relata $? "429 = quota"
[ "$(eo 2026-09-30T13:10:00.000Z)" = quota ]; relata $? "cota vence transitorio na mesma janela"
grep -q 'lib/opencode-erros.sh' "$ROOT/bot/loop.sh"; relata $? "loop.sh usa a lib"
# 06/10: is_quota existe na lib (o loop.sh chama; antes dava 127 = "nao e cota") e so le o que a rodada imprimiu
printf 'tool ok\nQUOTA_EXAUSTA\n' > "$T/r1.log"; printf 'anuncio: trial credits, rate limit de vagas\n' > "$T/r2.log"
printf 'Error from provider: Rate limit exceeded\n' > "$T/r3.log"
bash -c ". '$ROOT/bot/lib/opencode-erros.sh'; is_quota '$T/r1.log' && ! is_quota '$T/r2.log' && is_quota '$T/r3.log'"
relata $? "is_quota: sentinela e erro do provider contam; texto de vaga nao"
for f in $(grep -o '\bis_quota\b\|\berro_opencode_log\b' "$ROOT/bot/loop.sh" | sort -u); do
  grep -q "^$f()" "$ROOT/bot/lib/opencode-erros.sh" || { echo "loop.sh chama $f que a lib nao define"; false; }
done; relata $? "toda funcao da lib que o loop.sh chama existe"
[ "$FAIL" -eq 0 ]
