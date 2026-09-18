# SEGURANÇA — leia antes do primeiro commit

## Regra Zero

**Antes de tudo, varra segredos em texto claro** (tokens, chaves de API, webhooks).
Segredo visto = **comprometido**: rotacione imediatamente no provedor e migre para
`~/.config/opencode/cron.env` (chmod 600) ou variável de ambiente. Remover do git
**não apaga o histórico**.

## Nunca entra no repo

- `bot/dados_candidato.json`, `bot/aplicadas.json` (seus dados + estado)
- `cron.env`, `auth.json` e qualquer arquivo com chave/token (só `.example`)
- CVs em PDF (`CV_*.pdf`), logs (`*.log`, `logs/`)
- Perfil do browser (`chrome-real` user-data-dir: sessões logadas!)
- Backups `*.bak-*`, `.playwright-mcp/`

O `.gitignore` já bloqueia tudo isso. Confira com `git status` antes de cada push.

## Verificação

```bash
./scripts/sanitize.sh   # greps por @gmail, /home/, vercel real, PRIVATE KEY, AKIA, CPF, CEP, R$...
```

Rode antes de commitar. O script falha (exit 1) se achar qualquer padrão — trate
como bloqueante. Sugestão: instale como pre-commit hook:

```bash
ln -s ../../scripts/sanitize.sh .git/hooks/pre-commit
```

## Princípios do robô

- **Nunca inventa dados**: campo ausente em `dados_candidato.json` vira `bloqueado`
  com o motivo — nunca chute CPF, RG, tempo de experiência ou idioma.
- **Allowlist de domínios**: o browser só acessa sites de vaga BR
  (`config/sites_permitidos.json` + `--allowed-origins`); o resto nem é requisitado.
- **Monitor sem dado sensível**: o snapshot envia contadores, eventos e caudas de log
  — nunca CPF, documentos ou segredos.

## Se vazar

1. Rotacione a chave/senha **no provedor** (novo token, revogue o antigo).
2. Remova do código e commite a remoção.
3. Se foi pushado: considere o segredo queimado mesmo após `git filter-repo` —
   a rotação (passo 1) é o que realmente protege.
