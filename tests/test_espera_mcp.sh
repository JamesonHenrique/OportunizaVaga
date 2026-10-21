#!/bin/bash
# tests/test_espera_mcp.sh — config/opencode-plugins/espera-mcp.ts (opencode 2 MCP race, issue #21), TAP output.
# Needs a node that runs TypeScript directly (type stripping, node >= 22.18); skips otherwise.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
echo "1..2"
if ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 23 ? 0 : 1)' 2>/dev/null; then
  echo "ok 1 # SKIP node sem type stripping"; echo "ok 2 # SKIP node sem type stripping"; exit 0
fi
# Node trata .ts como CommonJS se o package.json mais proximo nao tem "type":"module"
# (a raiz do repo nao tem), entao o `export` do plugin explode. Importamos por um
# espelho temporario .mts, que o Node le sempre como ESM — o plugin original fica intacto.
ts_tmp="$(mktemp "${TMPDIR:-/tmp}/espera-mcp.XXXXXX.mts")"
cp config/opencode-plugins/espera-mcp.ts "$ts_tmp"
out=$(node --input-type=module -e '
const p = (await import(process.argv[1])).default;
let n = 0;
const viu = await p.esperar(async () => (++n < 3 ? [{ id: "read" }] : [{ id: "playwright-chrome-real_browser_tabs" }]), 2000, 5);
const desistiu = !(await p.esperar(async () => [{ id: "read" }], 30, 5));
console.log(viu && n === 3 ? "espera" : "falhou-espera", desistiu ? "desiste" : "falhou-desiste", p.id);
' "$ts_tmp" 2>&1)
rm -f "$ts_tmp"
FAIL=0
grep -q "^espera " <<<"$out" && echo "ok 1 - espera ate as ferramentas do navegador aparecerem" || { echo "not ok 1 - espera ($out)"; FAIL=1; }
grep -q " desiste oportunizavaga.espera-mcp$" <<<"$out" && echo "ok 2 - desiste no limite e tem id proprio do projeto" || { echo "not ok 2 - limite/id ($out)"; FAIL=1; }
exit $FAIL
