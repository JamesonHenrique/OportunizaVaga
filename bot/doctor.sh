#!/bin/bash
# bot/doctor.sh — checklist de diagnostico (saida colavel em issue).
# Checa: versao do bash, node, opencode, chrome, CDP 127.0.0.1:9222, JSONs
# presentes e validos, cron.env ausente do git, espaco em disco.
# Exit 0 = essencial ok (avisos [??] permitidos); 1 = falta algo essencial.
# So LE o sistema: nao abre browser, nao se candidata, nao altera nada.
# Uso: ./bot/doctor.sh
set -u
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT" || exit 1

FALTA_ESSENCIAL=0
ok()    { echo "  [ok] $1"; }
info()  { echo "  [..] $1"; }
aviso() { echo "  [??] $1 -- $2"; }
falha() { echo "  [FALHA] $1 -- $2"; FALTA_ESSENCIAL=1; }

echo "== OportunizaVaga — doctor =="
echo "Raiz: $BOT_ROOT"
echo "Data: $(date '+%F %T %z')"
echo

echo "-- 1) Interpretador --"
info "bash ${BASH_VERSION:-desconhecida}"
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  aviso "bash < 4" "atualize o bash (scripts usam recursos do bash 4+)."
else
  ok "bash"
fi
if command -v python3 >/dev/null 2>&1; then
  ok "python3 ($(python3 --version 2>&1))"
else
  falha "python3 ausente" "instale Python 3 (validate/dry-run precisam dele)."
fi
echo

echo "-- 2) Dependencias do loop real --"
if command -v node >/dev/null 2>&1; then
  ok "node ($(node --version 2>&1))"
else
  falha "node ausente" "instale Node 20+ (veja docs/QUICKSTART.md)."
fi
if command -v opencode >/dev/null 2>&1; then
  ok "opencode ($(command -v opencode))"
elif [ -x "$HOME/.opencode/bin/opencode" ]; then
  ok "opencode (\$HOME/.opencode/bin/opencode)"
else
  falha "opencode ausente" "instale via https://opencode.ai (veja docs/QUICKSTART.md)."
fi
CHROME_BIN=""
for c in google-chrome-stable google-chrome chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then CHROME_BIN="$c"; break; fi
done
if [ -n "$CHROME_BIN" ]; then
  ok "chrome ($CHROME_BIN)"
else
  falha "Chrome ausente" "instale o Chrome (necessario p/ browser/chrome-real.sh)."
fi
echo

echo "-- 3) Chrome CDP (127.0.0.1:9222) --"
CDP_OK=0
if command -v curl >/dev/null 2>&1; then
  curl -s --max-time 5 http://127.0.0.1:9222/json/version >/dev/null 2>&1 && CDP_OK=1
elif ( : </dev/tcp/127.0.0.1/9222 ) 2>/dev/null; then
  CDP_OK=1
else
  info "curl ausente e /dev/tcp indisponivel — pulei o teste CDP."
fi
if [ "$CDP_OK" = "1" ]; then
  ok "CDP acessivel (Chrome com remote debugging aberto)."
else
  aviso "CDP 127.0.0.1:9222 inacessivel" "suba com ./browser/chrome-real.sh & e faca login 1x (aviso: nao bloqueia nada, so o loop real precisa)."
fi
echo

echo "-- 4) JSONs (presentes e validos) --"
for f in examples/dados_candidato.example.json examples/aplicadas.example.json; do
  if [ ! -f "$f" ]; then
    falha "$f ausente" "restaure com git checkout -- $f."
  elif python3 -c "import json;json.load(open('$f',encoding='utf-8'))" 2>/dev/null; then
    ok "$f valido."
  else
    falha "$f invalido" "rode bash scripts/validate.sh p/ detalhes e corrija o JSON."
  fi
done
for f in bot/dados_candidato.json bot/aplicadas.json; do
  if [ ! -f "$f" ]; then
    info "$f ausente (normal antes do setup — sera copiado do .example)."
  elif python3 -c "import json;json.load(open('$f',encoding='utf-8'))" 2>/dev/null; then
    ok "$f valido."
  else
    falha "$f invalido" "rode bash scripts/validate.sh p/ detalhes e corrija o JSON."
  fi
done
echo

echo "-- 5) Segredos fora do git --"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  VAZOU="$(git ls-files | grep -E '(cron\.env|dados_candidato\.json|aplicadas\.json|auth\.json)$' || true)"
  if [ -n "$VAZOU" ]; then
    falha "arquivo sensivel rastreado pelo git: $VAZOU" "remova com git rm --cached <arq> e confira o .gitignore; segredo visto = comprometido."
  else
    ok "nenhum cron.env/dados/aplicadas/auth rastreado."
  fi
else
  info "fora de repo git — checagem de tracked pulada."
fi
if [ -f "$HOME/.config/opencode/cron.env" ]; then
  ok "\$HOME/.config/opencode/cron.env existe (chaves fora do repo)."
else
  aviso "cron.env ausente" "crie \$HOME/.config/opencode/cron.env com chmod 600 (veja docs/QUICKSTART.md sec. 3)."
fi
echo

echo "-- 6) Disco --"
LIVRE_MB="$(df -k "$BOT_ROOT" 2>/dev/null | awk 'NR==2 {print int($4/1024)}')"
if [ -z "$LIVRE_MB" ]; then
  info "nao foi possivel medir espaco em disco."
elif [ "$LIVRE_MB" -lt 500 ]; then
  falha "disco com ${LIVRE_MB}MB livres" "libere espaco (logs em bot/logs, perfil do Chrome)."
elif [ "$LIVRE_MB" -lt 2048 ]; then
  aviso "disco com ${LIVRE_MB}MB livres" "fique de olho; logs e perfil do Chrome crescem."
else
  ok "disco (${LIVRE_MB}MB livres)."
fi
echo

if [ "$FALTA_ESSENCIAL" -eq 0 ]; then
  echo "doctor: essencial OK (resolva os [??] se for rodar o loop real)."
else
  echo "doctor: FALHOU — resolva os itens [FALHA] acima e rode de novo."
fi
echo "Para colar numa issue: copie deste bloco para cima e confira que nao ha dados pessoais."
exit "$FALTA_ESSENCIAL"
