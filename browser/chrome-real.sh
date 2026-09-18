#!/bin/bash
# Real persistent Chrome for the agent (CDP) - 1 login lasts for everything.
# Profile lives under $HOME so any user can run it; keep this profile OUT of git
# (it holds logged-in sessions). Start it before the bot; guardiao.sh restarts it.
exec google-chrome-stable \
  --user-data-dir="${XDG_CONFIG_HOME:-$HOME/.config}/oportunizavaga-chrome-real" \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --no-first-run --no-default-browser-check \
  about:blank
