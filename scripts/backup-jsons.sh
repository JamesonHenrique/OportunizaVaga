#!/bin/bash
# backup-jsons.sh — cópia versionada dos JSONs-estado (aplicadas.json,
# dados_candidato.json, por perfil). Só LÊ os arquivos vivos e ESCREVE em
# bot/backups/ (nunca toca no original). Guarda as últimas 14 cópias por arquivo.
# Cron sugerido 2x/dia:
#   0 8,12 * * * $BOT_DIR/scripts/backup-jsons.sh >> $BOT_DIR/bot/backups/backup.log 2>&1
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST="${OV_BACKUP_DIR:-$BOT_ROOT/bot/backups}"
mkdir -p "$DEST" || exit 1
STAMP=$(date '+%Y%m%d-%H%M')
KEEP=14

backup_file() {  # $1 = origem, $2 = prefixo do nome no backup
  local src="$1" prefix="$2" dest
  [ -f "$src" ] || return 0   # perfil/arquivo ainda nao existe: nada a fazer, sem alarde
  dest="$DEST/${prefix}.$STAMP.json"
  if cp "$src" "$dest"; then
    echo "[$STAMP] ok: $src -> ${dest#$DEST/}"
  else
    echo "[$STAMP] FALHA ao copiar: $src" >&2
    return 1
  fi
  # rotação: mantém as 14 mais recentes
  ls -1t "$DEST/${prefix}".*.json 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
}

# 1) estado raiz (perfil default / sem perfil)
backup_file "$BOT_ROOT/bot/aplicadas.json" aplicadas
backup_file "$BOT_ROOT/bot/dados_candidato.json" dados_candidato

# 2) estado isolado de CADA perfil ativo (bot/state/<slug>/), se houver.
for estado in "$BOT_ROOT"/bot/state/*/aplicadas.json; do
  [ -f "$estado" ] || continue
  slug="$(basename "$(dirname "$estado")")"
  state_dir="$(dirname "$estado")"
  backup_file "$estado" "aplicadas.perfil-$slug"
  backup_file "$state_dir/dados_candidato.json" "dados.perfil-$slug"
done
