#!/bin/bash
# bot/lib/opencode-erros.sh — provider error of ONE robot's opencode runs: "quota", "transitorio" or nothing.
#   erro_opencode_log SINCE_ISO [DIR]   DIR = working directory of the runs to consider (default $BASE)
# The opencode log is shared by every agent on the machine: only runs whose instance started in DIR count.
# Why the split: a bare AI_APICallError used to count as quota, so a transient 503 "Service Unavailable" or a
# header timeout put the best model on a long cooldown and the round fell to weaker models. Transient errors
# (5xx, overload, timeouts) are reported apart so the caller can retry the SAME model instead.
OC_LOG_DIR=${OC_LOG_DIR:-$HOME/.local/share/opencode/log}
erro_opencode_log() {
  local f dir=${2:-$BASE}
  f=$(ls -t "$OC_LOG_DIR"/*.log 2>/dev/null | head -1)
  [ -n "$f" ] || return 0
  tail -c 8000000 "$f" | awk -v since="$1" -v dir="$dir" '
    /message="creating instance"/ {
      if (match($0, /run=[0-9a-f]+/)) { r = substr($0, RSTART + 4, RLENGTH - 4) }
      if (index($0, "directory=" dir) && !index($0, "directory=" dir "/")) mine[r] = 1
      next
    }
    /level=ERROR/ {
      if (!match($0, /run=[0-9a-f]+/)) next
      r = substr($0, RSTART + 4, RLENGTH - 4)
      if (!(r in mine)) next
      if (!match($0, /timestamp=[0-9T:.-]+Z/)) next
      if (substr($0, RSTART + 10, RLENGTH - 10) < since) next
      if ($0 ~ /Rate limit exceeded|[Tt]oo [Mm]any [Rr]equests|429|[Qq]uota|[Ee]xhausted|RateLimitError/) q = 1
      else if ($0 ~ /Service Unavailable|Bad Gateway|Gateway Timeout|Internal Server Error|50[0234]|[Oo]verloaded|HeaderTimeout|ETIMEDOUT|ECONNRESET|socket hang up/) t = 1
    }
    END { if (q) print "quota"; else if (t) print "transitorio" }
  '
}
