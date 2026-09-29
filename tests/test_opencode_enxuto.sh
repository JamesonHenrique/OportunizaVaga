#!/bin/bash
# tests/test_opencode_enxuto.sh — bot/opencode-enxuto.py: config enxuta lida da config do opencode do usuario
# (aqui: config/opencode.jsonc.example), sem tocar em nada real. Offline.
# Uso: bash tests/test_opencode_enxuto.sh   (exit 0 = tudo verde)
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
trap 'rm -rf "$TMP"' EXIT
export ROOT OV_OPENCODE_USER_CONFIG="$ROOT/config/opencode.jsonc.example"
unset OPENCODE_CONFIG OV_BROWSER_MCP OV_ENXUTO_NEGAR OV_OPENCODE_ENXUTO
# 0 — opt-in in the public repo: without OV_OPENCODE_ENXUTO=1 nothing changes (empty output, exit 0).
S0="$("$PY" bot/opencode-enxuto.py 2>/dev/null)"; R0=$?
[ -z "$S0" ] && [ "$R0" = 0 ]
relata $? "padrao desligado: sem OV_OPENCODE_ENXUTO=1 a saida e vazia"
export OV_OPENCODE_ENXUTO=1

# 1 — JSONC do exemplo (com // dentro de URLs e comentarios) vira JSON valido; browser MCP sem 'vision', com CDP e blocklist.
"$PY" bot/opencode-enxuto.py > "$TMP/cfg.json" 2>"$TMP/err"
"$PY" - "$TMP/cfg.json" <<'PYEOF'
import json, sys
c = json.load(open(sys.argv[1]))
b = c["mcp"]["playwright-chrome-real"]
assert b["enabled"] is True and b["type"] == "local", b
cmd = b["command"]
assert "vision" not in cmd and "--caps" not in cmd, cmd
assert "--cdp-endpoint" in cmd and "--blocked-origins" in cmd, cmd
assert cmd[cmd.index("--cdp-endpoint") + 1].startswith("http://127.0.0.1"), cmd   # '//' in a URL survived the comment stripper
PYEOF
relata $? "browser MCP: sem --caps vision, CDP e --blocked-origins preservados"

# 2 — outros MCPs so desligados (nada de URL/headers copiado); permissoes negadas; write/webfetch ficam.
"$PY" - "$TMP/cfg.json" <<'PYEOF'
import json, sys
raw = open(sys.argv[1]).read()
c = json.loads(raw)
for nome in ("context7", "github", "ai-memory", "playwright-firefox"):
    assert c["mcp"][nome] == {"enabled": False}, (nome, c["mcp"][nome])
assert "Authorization" not in raw and "githubcopilot" not in raw and "GITHUB_TOKEN" not in raw
p = c["permission"]
for t in ("edit", "glob", "grep", "websearch", "task", "todowrite", "playwright-chrome-real_browser_close"):
    assert p[t] == "deny", t
assert p["*"] == "allow" and "write" not in p and "webfetch" not in p, p
PYEOF
relata $? "outros MCPs so desligados (sem segredo copiado); ferramentas nao usadas negadas; write/webfetch mantidos"

# 3 — interruptor e fail-open: OV_OPENCODE_ENXUTO=0, config ausente, MCP ausente, JSON invalido => saida vazia, exit 0.
S1="$(OV_OPENCODE_ENXUTO=0 "$PY" bot/opencode-enxuto.py)"; R1=$?
S2="$(OV_OPENCODE_USER_CONFIG="$TMP/nao-existe.jsonc" OPENCODE_CONFIG="" HOME="$TMP" "$PY" bot/opencode-enxuto.py 2>/dev/null)"; R2=$?
S3="$(OV_BROWSER_MCP=nao-existe "$PY" bot/opencode-enxuto.py 2>/dev/null)"; R3=$?
echo '{ "mcp": ' > "$TMP/ruim.jsonc"
S4="$(OV_OPENCODE_USER_CONFIG="$TMP/ruim.jsonc" "$PY" bot/opencode-enxuto.py 2>/dev/null)"; R4=$?
[ -z "$S1$S2$S3$S4" ] && [ "$R1$R2$R3$R4" = "0000" ]
relata $? "desligado/ausente/invalido => vazio e exit 0 (o robo segue com a config dele)"

# 4 — comentarios /* */, virgula final e '//' dentro de string.
cat > "$TMP/c.jsonc" <<'JSONC'
{
  /* bloco */ "mcp": {
    "meu-browser": { "type": "local", "command": ["npx", "x", "--caps=vision,pdf", "--url", "http://h//p",], "enabled": true }, // fim
    "outro": { "type": "remote", "url": "https://a.example/mcp" },
  },
}
JSONC
OV_OPENCODE_USER_CONFIG="$TMP/c.jsonc" OV_BROWSER_MCP=meu-browser "$PY" bot/opencode-enxuto.py | "$PY" -c "
import json, sys
c = json.load(sys.stdin)
assert c['mcp']['meu-browser']['command'] == ['npx', 'x', '--caps=pdf', '--url', 'http://h//p'], c
assert c['mcp']['outro'] == {'enabled': False}
assert c['permission']['meu-browser_browser_close'] == 'deny'
"
relata $? "JSONC com /* */, virgula final, '//' em string e --caps=vision,pdf (so vision sai)"

# 5 — lista de negacao configuravel.
OV_ENXUTO_NEGAR="grep,glob" "$PY" bot/opencode-enxuto.py | "$PY" -c "
import json, sys
p = json.load(sys.stdin)['permission']
assert p.get('grep') == 'deny' and p.get('glob') == 'deny' and 'edit' not in p, p
"
relata $? "OV_ENXUTO_NEGAR troca a lista de ferramentas negadas"

# 6 — loop.sh: OV_OPENCODE_CONFIG_CONTENT explicito tem precedencia sobre o script; os 4 lançadores usam o script.
grep -q 'OC_CFG="\$OV_OPENCODE_CONFIG_CONTENT"' bot/loop.sh && grep -q 'opencode-enxuto' bot/followup.sh \
  && grep -q 'opencode-enxuto' bot/loop.ps1 && grep -q 'opencode-enxuto' bot/followup.ps1
relata $? "loop/followup (sh e ps1) chamam opencode-enxuto e o override explicito vence"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
