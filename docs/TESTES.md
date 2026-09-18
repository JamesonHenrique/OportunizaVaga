# TESTES — OportunizaVaga (Parte E)

Três suites, sem instalar nada além do que o projeto já exige
(bash + python3 no Linux, PowerShell no Windows, node 20+).

## 1. Linux / macOS / git-bash — suite TAP

```bash
bash tests/test_validate.sh
```

6 testes em bash puro (saída TAP `ok`/`not ok`, exit 0 = verde):

1. `scripts/validate.sh` passa (exit 0) com os exemplos válidos;
2. fixture `dados_candidato.valido.json` tem `email`;
3. `scripts/validate.sh` falha (exit ≠ 0) com `dados_candidato.sem-email.json`;
4. fixture `aplicadas.valida.json` tem `rodizio.proximo`;
5. `scripts/validate.sh` falha (exit ≠ 0) com `aplicadas.sem-rodizio-proximo.json`;
6. `bot/dry-run.sh --json` sai com exit 0 e JSON parseável por python (`ok == true`).

Os testes 3 e 5 copiam a fixture por cima de `examples/` e restauram
via `trap` — o repo volta intacto mesmo se o teste falhar.
Fixtures em `tests/fixtures/` (nenhum dado real, tudo `@example.com`).

## 2. Windows — espelho Pester

```powershell
Invoke-Pester -Path ./tests/validate.Tests.ps1
```

Mesma cobertura da suite TAP para `scripts/validate.ps1` + `bot/dry-run.ps1 -json`
(sintaxe `Should Be` legada: roda em Pester v3/v4/v5 e PowerShell 5.1+).
Não executada no Linux (sem `pwsh`); o CI Windows executa.

## 3. Funil do monitor — node:test nativo (qualquer OS)

```bash
node --test monitor/*.test.mjs
# ou só o arquivo:
node --test monitor/funnel.test.mjs
```
(Glob explícito porque `node --test monitor/` com diretório puro falha
no node 24 — o runner tenta importar o diretório como módulo.)

`monitor/funnel.mjs` exporta `computaFunil(aplicadasJson)` →
`{ vistas, aplicadas, respostas, taxas }`. É duplicação deliberada da
lógica de `scripts/funnel.sh` (que continua intacto, sem refator) para o
teste importar sem depender de shell. 4 casos: estado vazio, funil típico
com taxas, `descartes_listagem` sem `total` (soma campos), regra de resposta
(`enviada` pura não conta; `status` ≠ `enviada`, `respondida_em` ou
`desfecho` contam).

## O que o CI cobre (`.github/workflows/ci.yml`)

| Job | Steps de qualidade |
|-----|--------------------|
| `linux` (ubuntu) | `bash -n` nos scripts, shellcheck, `node --check`, JSON válido, `scripts/validate.sh`, **`bash tests/test_validate.sh`**, **`node --test monitor/`**, `sanitize.sh` |
| `windows` | PSScriptAnalyzer (só erros), `node --check`, JSON válido, `validate.ps1`, **`Pester tests/validate.Tests.ps1`**, `sanitize.sh` via git-bash |

Dependabot (`.github/dependabot.yml`): npm em `monitor/` + github-actions, mensal.

## Pré-tag v0.1.0

`CHANGELOG.md` já tem `[0.1.0] - 2026-09-18` (partes A–E) e `[Unreleased]`
vazia no topo. Para lançar (manual, fora desta tarefa):

```bash
git tag -a v0.1.0 -m "v0.1.0" && git push origin v0.1.0
# release criada pelo GitHub a partir da tag
```
