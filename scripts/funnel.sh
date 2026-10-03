#!/bin/bash
# funnel.sh — casca do funil de candidatura. A lógica está em bot/funil.py (fonte
# única, compartilhada com o espelho Windows e coberta por tests/test_funil.sh).
# Uso: ./scripts/funnel.sh [--aplicadas PATH] [--csv [PATH]] [--json] [--markdown [PATH]]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APLICADAS="${BOT_APLICADAS:-$BOT_ROOT/bot/aplicadas.json}"

while [ $# -gt 0 ]; do
  case "$1" in
    --aplicadas) APLICADAS="$2"; shift 2 ;;
    # --csv e --markdown aceitam caminho opcional: sem valor, usam o nome padrao.
    --csv)       CSV="${2:-funil.csv}"; if [ "${2:-}" = "--" ] || [ -z "${2:-}" ] || [ "${2:0:1}" = "-" ]; then shift; else shift 2; fi ;;
    --markdown)  MD="${2:-funil.md}";    if [ "${2:-}" = "--" ] || [ -z "${2:-}" ] || [ "${2:0:1}" = "-" ]; then shift; else shift 2; fi ;;
    --json)      JSON=1; shift ;;
    -h|--help)   sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

PY=""
for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "funnel.sh: python3 nao encontrado no PATH" >&2; exit 1; }

ARGS=("$BOT_ROOT/bot/funil.py" --aplicadas "$APLICADAS")
[ -n "${JSON:-}" ] && ARGS+=(--json)
[ -n "${CSV:-}" ] && ARGS+=(--csv "$CSV")
[ -n "${MD:-}" ] && ARGS+=(--markdown "$MD")
exec "$PY" "${ARGS[@]}"