#!/bin/bash
# chrome-lock.sh NAME alta|normal WAIT_S -- CMD...   — the ONE way to use the shared Chrome (CDP 9222).
# Windows twin: bot/chrome-lock.ps1 (same protocol).
#
#   PRIO=alta   (short/daily jobs: follow-up, Gmail reader) marks its turn with the flag file
#               <flagdir>/agent-chrome-9222.prio.NAME, then waits up to WAIT_S for the lock.
#   PRIO=normal (the application loop) YIELDS if any fresh priority flag of another job exists
#               (younger than 120 min), else waits up to WAIT_S.
#
# Exit: CMD's own code; 75 = lock timeout; 76 = yielded to a priority job (override with
# CHROME_LOCK_YIELD_RC, e.g. 75 so a caller that already handles "Chrome busy" needs no change);
# 2 = usage.
#
# A flag that already existed when the call started belongs to the parent job (e.g. follow-up keeps
# it for all its model attempts) and is NOT removed here; only a flag created by this call is.
# The lock is flock(2) on the same file every script uses, so old callers still interlock.
# Logs who held the Chrome and for how long (bot/logs/chrome-lock.log).
#
# Env (tests never touch the real Chrome lock): CHROME_LOCK_FILE, CHROME_LOCK_DIR, CHROME_LOCK_LOG,
# CHROME_LOCK_YIELD_RC.
LOCK=${CHROME_LOCK_FILE:-/tmp/agent-chrome-9222.lock}
FLAGS=${CHROME_LOCK_DIR:-/tmp}
LOG=${CHROME_LOCK_LOG:-$(dirname "$(readlink -f "$0")")/logs/chrome-lock.log}
NAME=${1:-} PRIO=${2:-} WAIT=${3:-}
[ $# -ge 3 ] && shift 3
[ "${1:-}" = "--" ] && shift
[ -n "$NAME" ] && [ -n "$WAIT" ] && [ $# -gt 0 ] || { echo "usage: chrome-lock.sh NAME alta|normal WAIT_S -- CMD..." >&2; exit 2; }
mkdir -p "$(dirname "$LOG")" 2>/dev/null
log() { echo "[$(date '+%F %T')] $NAME($PRIO) $*" >> "$LOG" 2>/dev/null; }

FLAG="$FLAGS/agent-chrome-9222.prio.$NAME"
case "$PRIO" in
  alta)
    if [ ! -e "$FLAG" ]; then touch "$FLAG"; trap 'rm -f "$FLAG"' EXIT; else touch "$FLAG"; fi ;;
  normal)
    outro=$(find "$FLAGS" -maxdepth 1 -name 'agent-chrome-9222.prio.*' ! -name "agent-chrome-9222.prio.$NAME" -mmin -120 2>/dev/null | head -1)
    if [ -n "$outro" ]; then log "yielded to ${outro##*.prio.}"; exit "${CHROME_LOCK_YIELD_RC:-76}"; fi ;;
  *) echo "PRIO must be alta or normal" >&2; exit 2 ;;
esac

t0=$(date +%s)
exec 7>>"$LOCK"
if ! flock -w "$WAIT" 7; then
  log "timed out waiting for the Chrome (${WAIT}s)"
  exit 75
fi
t1=$(date +%s)
[ $((t1 - t0)) -gt 5 ] && log "got the Chrome after $((t1 - t0))s waiting"
# 7>&-: the child must not inherit the lock fd (a leftover daemon would hold the Chrome forever).
"$@" 7>&-
rc=$?
log "released the Chrome after $(( $(date +%s) - t1 ))s (rc=$rc)"
exit $rc
