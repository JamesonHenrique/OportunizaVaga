#!/bin/bash
# bot/lib/opencode-erros.sh — provider error of ONE robot's opencode runs: "quota", "transitorio" or nothing.
#   erro_opencode_log SINCE_ISO [DIR]   DIR = working directory of the runs to consider (default $BASE)
# The opencode log is shared by every agent on the machine: only runs whose instance started in DIR count.
# Why the split: a bare AI_APICallError used to count as quota, so a transient 503 "Service Unavailable" or a
# header timeout put the best model on a long cooldown and the round fell to weaker models. Transient errors
# (5xx, overload, timeouts) are reported apart so the caller can retry the SAME model instead.
#   is_quota ARQUIVO                     true when the round's OWN log names a quota or the QUOTA_EXAUSTA sentinel
# Two sources, not the same question: is_quota reads what the run PRINTED (the prompt makes the model write
# QUOTA_EXAUSTA when it gives up; the provider's complaint lands on the round's stdout) and never scans the body
# of the round (a job posting saying "trial credits" must not put the loop to sleep); erro_opencode_log reads
# opencode's INTERNAL log, for a client stuck in a silent retry that prints nothing.
# 06/10: is_quota was lost when this file was extracted from loop.sh, but bot/loop.sh kept calling it — bash
# answered 127 ("command not found"), read as "not quota", so a quota printed in the round log never counted.
is_quota() {
  grep -qE '^[[:space:]]*QUOTA_EXAUSTA|Error from provider.*([Rr]ate limit|[Qq]uota|429|[Ee]xhausted|[Tt]oo [Mm]any)|AI_RetryError|RateLimitError' "$1"
}

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
