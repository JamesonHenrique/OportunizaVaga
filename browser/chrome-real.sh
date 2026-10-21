#!/bin/bash
# Real persistent Chrome for the agent (CDP) - 1 login lasts for everything.
# Profile lives under $HOME so any user can run it; keep this profile OUT of git
# (it holds logged-in sessions). Start it before the bot; guardiao.sh restarts it.
# Binario detectado como no doctor.sh: Chrome de verdade (google-chrome*), com
# fallback para o Chromium puro de quem instalou via apt/choco sem o Chrome.
# Override manual: OV_BROWSER=/caminho/do/navegador ./browser/chrome-real.sh
BROWSER_BIN="${OV_BROWSER:-}"
if [ -z "$BROWSER_BIN" ]; then
  for cand in google-chrome-stable google-chrome chromium-browser chromium; do
    command -v "$cand" >/dev/null 2>&1 && { BROWSER_BIN="$cand"; break; }
  done
fi
if [ -z "$BROWSER_BIN" ]; then
  echo "ERRO: nenhum Chromium/Chrome encontrado (procurei google-chrome-stable, google-chrome, chromium-browser, chromium)." >&2
  echo "Instale o Google Chrome ou rodar: OV_BROWSER=/caminho/do/navegador $0" >&2
  exit 1
fi
exec "$BROWSER_BIN" \
  --user-data-dir="${XDG_CONFIG_HOME:-$HOME/.config}/oportunizavaga-chrome-real" \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --no-first-run --no-default-browser-check \
  about:blank
