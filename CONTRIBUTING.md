# Contributing

## Antes de codar

- Leia `docs/SEGURANCA.md`. **Nunca** commite dados reais: use sempre os
  placeholders (`SEU_NOME`, `seu-email@example.com`, `SUA_EMPRESA`, `SEU_VALOR_BASE`,
  `https://sua-url.vercel.app`).
- Rode `./scripts/sanitize.sh` antes de cada push — ele é bloqueante.

## Padrões

- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- Shell: `bash -n` limpo; scripts resolvem `BOT_ROOT` a partir do próprio caminho
  (nada de path absoluto). Node: `node --check` limpo; dados via `CANDIDATURAS_ROOT`
  com fallback para o `bot/` do repo.
- Prompts (`.md`): mantêm o sentinel `QUOTA_EXAUSTA` e o formato de registro com
  fuso local — o `loop.sh` e o monitor dependem deles.
- Português nas docs e comentários; código/variáveis em inglês.

## Testando

```bash
bash -n bot/*.sh scripts/*.sh browser/*.sh
python3 -m json.tool config/sites_permitidos.json
node --check monitor/*.mjs
./scripts/sanitize.sh
```

## PRs

Descreva o quê mudou e o porquê, marque se testou 1 rodada manual, confirme
`sanitize.sh` verde. Sem dado pessoal nem segredo no diff — o revisor vai checar.

## Templates, CoC e Security

- Issues: use os forms em `.github/ISSUE_TEMPLATE/` (`bug_report.yml`,
  `feature_request.yml`) — informe ambiente (Linux/Windows/WSL2) e cole só
  logs sanitizados, sem dados pessoais.
- PRs: siga `.github/pull_request_template.md` (checklist: `sanitize.sh`,
  sem segredos, CI, docs, dry-run de 1 rodada se mexeu no bot).
- Conduta: respeite o `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1).
- Segurança: nunca abra issue pública para vulnerabilidade — reporte conforme
  o `SECURITY.md` e leia `docs/SEGURANCA.md` antes do primeiro commit.
