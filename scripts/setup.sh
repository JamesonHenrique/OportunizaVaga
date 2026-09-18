#!/bin/bash
# setup.sh — instalador interativo do OportunizaVaga.
# Copia os .example, valida dependências e imprime o crontab sugerido.
# Seguro: nunca apaga arquivo existente sem perguntar, nunca commita nada.
set -u
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT" || exit 1

ok()   { echo "  [ok] $1"; }
warn() { echo "  [!!] $1"; }

echo "== OportunizaVaga — setup =="
echo "Raiz: $BOT_ROOT"
echo

copiar() { # $1 = origem .example, $2 = destino
  if [ -f "$2" ]; then
    echo "  [pq] $2 já existe — mantido."
  else
    cp "$1" "$2"
    echo "  [ok] criado $2 (PREENCHA com seus dados — nunca commite)."
  fi
}

echo "-- 1) Arquivos de dados (gitignored) --"
copiar examples/dados_candidato.example.json bot/dados_candidato.json
copiar examples/aplicadas.example.json bot/aplicadas.json
if [ -f "$HOME/.config/opencode/cron.env" ]; then
  ok "~/.config/opencode/cron.env existe (chaves fora do repo)."
else
  warn "~/.config/opencode/cron.env AUSENTE — crie com suas chaves (chmod 600):"
  echo "       OPENROUTER_API_KEY=... (só se USAR_OPENROUTER=1 em bot/loop.sh)"
fi
echo

echo "-- 2) Dependências --"
HAVE_ALL=1
for bin in bash python3 node flock fuser curl git timeout setsid; do
  if command -v "$bin" >/dev/null 2>&1; then ok "$bin"; else warn "$bin NÃO encontrado"; HAVE_ALL=0; fi
done
[ -x "$HOME/.opencode/bin/opencode" ] && ok "opencode" || { warn "opencode ausente em ~/.opencode/bin (https://opencode.ai)"; HAVE_ALL=0; }
command -v google-chrome-stable >/dev/null 2>&1 && ok "google-chrome-stable" || { warn "Chrome ausente (necessário p/ browser/chrome-real.sh)"; HAVE_ALL=0; }
echo

echo "-- 3) Permissão de execução --"
chmod +x bot/*.sh browser/*.sh scripts/*.sh
ok "scripts marcados como executáveis."
echo

echo "-- 4) Validação rápida --"
bash -n bot/loop.sh && bash -n bot/guardiao.sh && bash -n bot/followup.sh \
  && bash -n scripts/monitor-keepalive.sh && bash -n scripts/pull-monitor.sh \
  && ok "todos os .sh passam em bash -n." || warn "falha em bash -n (veja acima)."
python3 -m json.tool config/sites_permitidos.json >/dev/null && ok "sites_permitidos.json válido." || warn "sites_permitidos.json inválido."
echo

echo "-- 5) Crontab sugerido (ajuste BOT_DIR se o clone mudar de lugar) --"
echo "   TZ=${BOT_TZ:-America/Sao_Paulo}"
echo "   BOT_DIR=$BOT_ROOT"
sed "s|\$HOME/opensource/oportunizavaga|$BOT_ROOT|; s|^TZ=.*|TZ=${BOT_TZ:-America/Sao_Paulo}|; s|^BOT_DIR=.*|BOT_DIR=$BOT_ROOT|" config/crontab.example
echo
[ "$HAVE_ALL" -eq 1 ] && echo "Setup pronto. Próximo passo: docs/QUICKSTART.md" || echo "Resolva os itens [!!] acima e rode de novo."
