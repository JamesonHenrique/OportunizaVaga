# TESTES — OportunizaVaga (Parte E)

Três suites, sem instalar nada além do que o projeto já exige
(bash + python3 no Linux, PowerShell no Windows, node 20+).

## 1. Linux / macOS / git-bash — suite TAP

```bash
bash tests/test_validate.sh
bash tests/test_dry_run.sh
```

`tests/test_validate.sh` tem 6 testes (saída TAP `ok`/`not ok`, exit 0 = verde):

1. `scripts/validate.sh` passa (exit 0) com os exemplos válidos;
2. fixture `dados_candidato.valido.json` tem `email`;
3. `scripts/validate.sh` falha (exit ≠ 0) com `dados_candidato.sem-email.json`;
4. fixture `aplicadas.valida.json` tem `rodizio.proximo`;
5. `scripts/validate.sh` falha (exit ≠ 0) com `aplicadas.sem-rodizio-proximo.json`;
6. `bot/dry-run.sh --json` sai com exit 0 e JSON parseável por python (`ok == true`).

`tests/test_dry_run.sh` tem 3 testes do plano global sem risco:

1. `dry-run.sh --json` lista os 6 adaptadores sem abrir browser;
2. `--profile` deriva o slug (`Frontend Teste` → `frontend-teste`) e usa estado isolado;
3. `--site indeed` restringe o plano a um único adaptador.

Os testes de fixture copiam o arquivo por cima de `examples/` e restauram
via `trap` — o repo volta intacto mesmo se o teste falhar.
Fixtures em `tests/fixtures/` (nenhum dado real, tudo `@example.com`).

## 2. Windows — espelho Pester

```powershell
Invoke-Pester -Path ./tests/validate.Tests.ps1
```

Cobre `scripts/validate.ps1` (exemplos válidos e fixtures inválidas) e
`bot/dry-run.ps1 -json` (plano global, `-Profile` com estado isolado e
`-Site` único). Não executada no Linux (sem `pwsh`); o CI Windows executa.

## 3. Monitor — node:test nativo (qualquer OS)

```bash
node --test monitor/*.test.mjs
# ou só o arquivo:
node --test monitor/funnel.test.mjs
node --test monitor/snapshot.test.mjs
```
(Glob explícito porque `node --test monitor/` com diretório puro falha
no node 24 — o runner tenta importar o diretório como módulo.)

`monitor/funnel.mjs` exporta `computaFunil(aplicadasJson)` →
`{ vistas, aplicadas, respostas, taxas }`. 4 casos: estado vazio, funil típico
com taxas, `descartes_listagem` sem `total` (soma campos), regra de resposta.

`monitor/snapshot.test.mjs` valida o retrato agregado em 2 casos:

1. `MONITOR_INCLUDE_DETAILS=0` (padrão): nenhum `applied`, `blocked`, `events`
   ou `logTail` sai; perfis isolados somam corretamente e `publisher` não expõe
   host/pid/root.
2. `MONITOR_INCLUDE_DETAILS=1` (opt-in): detalhes brutos aparecem.

## O que o CI cobre (`.github/workflows/ci.yml`)

| Job | Steps de qualidade |
|-----|--------------------|
| `linux` (ubuntu) | `bash -n` nos scripts + adaptadores, shellcheck, `node --check`, JSON válido, `scripts/validate.sh`, **`bash tests/test_validate.sh`**, **`bash tests/test_dry_run.sh`**, **`node --test monitor/`**, `sanitize.sh` |
| `windows` | PSScriptAnalyzer (só erros), `node --check`, JSON válido, `validate.ps1`, **`Pester tests/validate.Tests.ps1`**, `sanitize.sh` via git-bash |

Dependabot (`.github/dependabot.yml`): npm em `monitor/` + github-actions, mensal.

## Pré-tag v0.1.0

`CHANGELOG.md` tem `[0.1.0] - 2026-09-18` (partes A–E) e `[Unreleased]`
registrando o trabalho atual. Para lançar (manual, fora desta tarefa):

```bash
git tag -a v0.1.0 -m "v0.1.0" && git push origin v0.1.0
# release criada pelo GitHub a partir da tag
```
