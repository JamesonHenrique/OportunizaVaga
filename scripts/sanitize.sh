#!/bin/bash
# sanitize.sh — varredura pré-commit: falha (exit 1) se achar padrão de segredo
# ou dado pessoal no que está staged ou na árvore (exceto gitignored).
# Rode manualmente ou via pre-commit: ./scripts/sanitize.sh
set -u
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT" || exit 1

PATTERNS=(
  '@gmail\.com' '@hotmail\.' '@outlook\.' '@yahoo\.'
  'home/james' '/home/[a-z]'
  'monitor-one-bice' 'vercel\.app.*[a-z0-9-]{3,}'
  'BEGIN (RSA )?PRIVATE KEY' 'AKIA[0-9A-Z]{16}' 'ghp_[A-Za-z0-9]{20,}' 'gho_[A-Za-z0-9]{20,}'
  'sk-ant-[A-Za-z0-9-]{10,}' 'sk-or-[A-Za-z0-9-]{10,}' 'xox[bpas]-[A-Za-z0-9-]{10,}'
  'OPENROUTER_API_KEY=["'"'"']?[A-Za-z0-9_-]{16,}' 'Bearer [A-Za-z0-9._-]{20,}'
  '[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}' '[0-9]{5}-[0-9]{3}'
  'R\$ ?[0-9]\.[0-9]{3}'
)
# Falsos positivos conhecidos (placeholders oficiais do projeto)
ALLOW='seu-email@example\.com|SEU_|SUA_|SUA-EMPRESA|<sua-empresa>|sua-url\.vercel\.app|\$HOME|\${BOT_ROOT}|\$BOT_ROOT|\$HOME/opensource|00000-0000|\(00\)|OPENROUTER_API_KEY=\(\.\+\)'

FAILS=0
# Exclui do scan: o próprio scanner, docs que documentam padrões e os arquivos de
# governança que trazem o contato PÚBLICO do mantenedor (CoC/Security) — de propósito.
TARGETS=$(git ls-files 2>/dev/null | grep -v -E '^(scripts/sanitize\.sh|docs/SEGURANCA\.md|CODE_OF_CONDUCT\.md|SECURITY\.md)$' || true)
[ -z "$TARGETS" ] && { echo "nada tracked — verificando árvore (sem gitignored)..."; TARGETS=$(git ls-files --others --cached --exclude-standard); }
for pat in "${PATTERNS[@]}"; do
  HITS=$(echo "$TARGETS" | xargs -r grep -nE "$pat" 2>/dev/null | grep -vE "$ALLOW" || true)
  if [ -n "$HITS" ]; then
    echo "[FALHA] padrão '$pat':"
    echo "$HITS"
    FAILS=1
  fi
done
# Arquivos que nunca podem existir no repo
for f in bot/dados_candidato.json bot/aplicadas.json config/cron.env cron.env auth.json bot/auth.json bot/*.pdf; do
  if [ -e "$f" ]; then echo "[FALHA] arquivo proibido presente: $f"; FAILS=1; fi
done
[ "$FAILS" -eq 0 ] && echo "sanitize OK: nenhum segredo ou dado pessoal detectado." || { echo "Corrija acima antes de commitar. Segredo visto = comprometido: rotacione a chave."; exit 1; }
