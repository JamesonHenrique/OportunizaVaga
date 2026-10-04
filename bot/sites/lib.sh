#!/bin/bash

site_adapter_root() {
  local self="${BASH_SOURCE[0]}"
  printf '%s\n' "$(cd "$(dirname "$self")/../.." && pwd)"
}

site_adapter_list() {
  local root="${1:-$(site_adapter_root)}"
  local file
  for file in "$root"/bot/sites/*.sh; do
    [ -f "$file" ] || continue
    [ "$(basename "$file")" = "_template.sh" ] && continue
    [ "$(basename "$file")" = "lib.sh" ] && continue
    printf '%s\n' "$(basename "$file" .sh)"
  done | LC_ALL=C sort
}

site_adapter_file() {
  local id="$1"
  local root="${2:-$(site_adapter_root)}"
  printf '%s\n' "$root/bot/sites/$id.sh"
}

site_adapter_source() {
  local id="$1"
  local root="${2:-$(site_adapter_root)}"
  local file
  file="$(site_adapter_file "$id" "$root")"
  [ -r "$file" ] || return 1
  # Each adapter starts clean. Without this, an adapter that declares nothing inherits the previous
  # one's value: sourcing catho.sh (SEARCH_ENCODING="hifen") then infojobs.sh (declares nothing) left
  # "hifen" set, and infojobs silently built hyphenated URLs. tests/test_sites.sh caught this.
  unset SITE_ID SITE_LABEL SITE_HOME SEARCH_URL_TEMPLATE SEARCH_ENCODING SITE_TERM_ENCODING SITE_REMOTE_HINT
  BOT_ROOT="$root" source "$file"
  [ -n "${SITE_ID:-}" ] || return 1
  [ -n "${SEARCH_URL_TEMPLATE:-}" ] || return 1
  # An adapter is DATA. Both functions used to live in every sites/*.sh, byte-identical in all 11, and
  # site_buscar_termos was then overwritten right here — so one of the two copies never ran at all.
  # They are generated here now. A site that still defines its own keeps it (declare -F || define).
  if ! declare -F site_url_busca >/dev/null; then
    site_url_busca() {
      local termo="${1:-}"
      local encoded
      # A term in a PATH segment must not carry a literal space: catho, solides and vagas declare
      # "hifen" and their own copies of this function used it. The other 8 declare nothing and always
      # used %20. Both spellings return 200 where they were checked, but the declared intent wins:
      # a URL that depends on the server being lenient is not a URL to keep.
      case "${SEARCH_ENCODING:-${SITE_TERM_ENCODING:-pct20}}" in
        hifen|hyphen) encoded="${termo// /-}" ;;
        plus)         encoded="${termo// /+}" ;;
        *)            encoded="${termo// /%20}" ;;
      esac
      printf '%s\n' "${SEARCH_URL_TEMPLATE//SEU_TERMO/$encoded}"
    }
  fi
  site_buscar_termos() {
    local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
    python3 - "$prompt" "$SITE_ID" <<'PY'
import re, sys
prompt, site_id = sys.argv[1:]
lines = open(prompt, encoding='utf-8').read().splitlines()
start = None
for i, line in enumerate(lines):
    if re.match(r'^\s*-\s*' + re.escape(site_id) + r'\s*:', line):
        start = i + 1
        break
if start is None:
    raise SystemExit(0)
quoted = []
for line in lines[start:start + 3]:
    if re.match(r'^\s*-\s*[a-z]+\s*:', line):
        break
    if not line.strip() or re.match(r'^\s*(?:c\)|PASSO|ANTI-|Site que|Todos brasileiros)', line):
        continue
    quoted.extend(re.findall(r'"([^"]+)"|\'([^\']+)\'', line))
for match in quoted:
    print(match[0] or match[1])
PY
  }
  declare -F site_buscar_termos >/dev/null || return 1
}

site_adapter_terms() {
  local prompt="${1:-${BOT_ROOT:-$(site_adapter_root)}/bot/prompt_loop.md}"
  local line trimmed
  while IFS= read -r line; do
    trimmed="${line#"${line%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    [ -n "$trimmed" ] || continue
    [[ "$trimmed" == \#* ]] && continue
    printf '%s\n' "$trimmed"
  done <<EOF
$(site_buscar_termos "$prompt" 2>/dev/null || true)
EOF
}

site_adapter_url() {
  local termo="${1:-}"
  site_url_busca "$termo"
}
