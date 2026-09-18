#!/bin/bash
# install.sh — one-line installer for OportunizaVaga (Linux / macOS / WSL2).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.sh | bash
#   curl -fsSL .../install.sh -o install.sh && bash install.sh ~/my-bot   # custom dir
# Clones the repo to $HOME/oportunizavaga (or $1) and runs scripts/setup.sh.
# Safe: never overwrites an existing checkout, never commits anything.
set -u

REPO_URL="https://github.com/JamesonHenrique/OportunizaVaga"
DEST="${1:-$HOME/oportunizavaga}"

if ! command -v git >/dev/null 2>&1; then
  echo "[!!] git not found — install git first (https://git-scm.com) and rerun." >&2
  exit 1
fi

if [ -e "$DEST" ]; then
  if [ -d "$DEST/.git" ]; then
    echo "[ok] existing checkout at $DEST — pulling latest."
    git -C "$DEST" pull --ff-only || { echo "[!!] git pull failed in $DEST." >&2; exit 1; }
  else
    echo "[!!] $DEST exists but is not a git checkout — pass another directory." >&2
    exit 1
  fi
else
  echo "[..] cloning $REPO_URL to $DEST ..."
  git clone "$REPO_URL" "$DEST" || { echo "[!!] git clone failed." >&2; exit 1; }
fi

echo "[..] running setup ..."
bash "$DEST/scripts/setup.sh"
echo
echo "Next: fill in $DEST/bot/dados_candidato.json (never commit it)"
echo "and follow docs/QUICKSTART.md inside $DEST."
