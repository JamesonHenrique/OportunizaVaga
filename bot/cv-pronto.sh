#!/usr/bin/env bash
# cv-pronto.sh <anuncio.txt> <cv.pdf> — ATS gate before attaching a per-job CV (prompt_cv.md step 4).
# Prints "ANEXAR <path>" and exits 0 only when check_ats.py approves (exit 0). Exit 1 = rejected,
# exit 2 = not verifiable; neither is ever an approval. Each verdict goes to the ATS log for the audit.
set -u
[ $# -eq 2 ] || { echo "uso: cv-pronto.sh <anuncio.txt> <cv.pdf>" >&2; exit 2; }
# check_ats.py next to the CALLED path: a private install symlinks both into its own dir, and check_ats.py finds
# dados_candidato.json next to the path it was called by (the real bot/ dir has no profile there).
AQUI=$(cd "$(dirname "$0")" && pwd)
[ -e "$AQUI/check_ats.py" ] || AQUI=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
LOG=${OV_ATS_LOG:-${BOT_ROOT:-$AQUI/..}/logs/ats.log}
saida=$(python3 "$AQUI/check_ats.py" "$1" "$2"); rc=$?
printf '%s\n' "$saida"
mkdir -p "$(dirname "$LOG")" 2>/dev/null
printf '%s rc=%s cv=%s %s\n' "$(date '+%FT%T%z')" "$rc" "$(basename "$2")" \
  "$(printf '%s' "$saida" | grep -m1 'DO PERFIL' | tr -d '\n')" >> "$LOG" 2>/dev/null
if [ "$rc" -eq 0 ]; then
  echo "ANEXAR $(readlink -f "$2")"
else
  echo "NAO ANEXE este PDF (check_ats rc=$rc)."
fi
exit "$rc"
