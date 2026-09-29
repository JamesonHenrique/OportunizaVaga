#!/bin/bash
# tests/test_podar_sessoes.sh — bot/podar-sessoes.py com um "opencode" falso (saida TAP).
# Nunca toca o opencode real: OV_OPENCODE_BIN aponta para um script que lista sessoes sinteticas
# e registra os `session delete`.
# Uso: bash tests/test_podar_sessoes.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"

TOTAL=8
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/outra-pasta"
NOW_MS=$(( $(date +%s) * 1000 ))
DAY=86400000
OLD=$(( NOW_MS - 10 * DAY ))
NEW=$(( NOW_MS - 1 * DAY ))

cat > "$T/sessions.json" <<JSON
[
 {"id":"s_old_loop","title":"candidaturas-2026-01-01-0900","directory":"$ROOT/bot","created":$OLD,"updated":$OLD},
 {"id":"s_old_followup","title":"followup-2026-01-01","directory":"$ROOT","created":$OLD,"updated":$OLD},
 {"id":"s_old_bumped","title":"candidaturas-2026-01-02-0900","directory":"$ROOT/bot","created":$OLD,"updated":$NOW_MS},
 {"id":"s_new","title":"candidaturas-2026-09-01-0900","directory":"$ROOT/bot","created":$NEW,"updated":$NEW},
 {"id":"s_new_but_updated_old","title":"candidaturas-2026-09-02-0900","directory":"$ROOT/bot","created":$NEW,"updated":$OLD},
 {"id":"s_other_dir","title":"candidaturas-2026-01-03-0900","directory":"$T/outra-pasta","created":$OLD,"updated":$OLD},
 {"id":"s_mine","title":"minha conversa interativa","directory":"$ROOT/bot","created":$OLD,"updated":$OLD}
]
JSON
cat > "$T/opencode" <<SH
#!/bin/bash
if [ "\$1 \$2" = "session list" ]; then cat "$T/sessions.json"; exit 0; fi
if [ "\$1 \$2" = "session delete" ]; then echo "\$3" >> "$T/deleted"; exit 0; fi
exit 2
SH
chmod +x "$T/opencode"
export OV_OPENCODE_BIN="$T/opencode" OPENCODE_DB="$T/opencode.db"
: > "$OPENCODE_DB"; chmod 644 "$OPENCODE_DB"

OUT="$("$PY" "$ROOT/bot/podar-sessoes.py" --dry 3)"
[ ! -e "$T/deleted" ] && echo "$OUT" | grep -q "3 do robo com >3d (dry)"; relata $? "--dry conta 3 candidatas e nao apaga nada ($OUT)"
[ "$(stat -c %a "$OPENCODE_DB")" = "644" ]; relata $? "--dry nao mexe nas permissoes do DB"

OUT="$("$PY" "$ROOT/bot/podar-sessoes.py" 3)"
DEL="$(sort "$T/deleted" | tr '\n' ' ')"
[ "$DEL" = "s_old_bumped s_old_followup s_old_loop " ]; relata $? "apaga so as velhas do robo (apagadas: $DEL)"
! grep -q "s_new\b" "$T/deleted"; relata $? "sessao recente do robo preservada"
grep -q "s_new_but_updated_old" "$T/deleted"; [ $? -ne 0 ]; relata $? "idade vem de created, nao de updated (created recente + updated antigo fica)"
grep -q "s_old_bumped" "$T/deleted"; relata $? "created antigo + updated recente (bump em massa) e apagada"
! grep -qE "s_other_dir|s_mine" "$T/deleted"; relata $? "outra pasta e sessao interativa (titulo sem prefixo) nunca apagadas"
[ "$(stat -c %a "$OPENCODE_DB")" = "600" ]; relata $? "DB do opencode fica 600"

if [ "$FAIL" -eq 0 ]; then echo "# verde: $N/$TOTAL"; exit 0; else echo "# FALHAS: $FAIL/$TOTAL"; exit 1; fi
