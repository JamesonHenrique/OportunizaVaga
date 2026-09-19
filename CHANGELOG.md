# Changelog — OportunizaVaga

All notable changes to this project will be documented in this file.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Added
- Contrato comum de adaptadores (`bot/sites/lib.sh`) com descoberta automática de portais.
- Dry-run global por perfil (`--json`, `--site`, `--profile`, `--reconhecimento`).
- Estado isolado por perfil em `bot/state/<perfil>/aplicadas.json`.
- Modo reconhecimento (`OV_RECONHECIMENTO=1`): pontua vagas sem se candidatar.
- Telemetria agregada e anônima por padrão no monitor (`MONITOR_INCLUDE_DETAILS=0`).
- Schemas `config/perfil.schema.json` e `config/reconhecimento.schema.json`.
- Testes: `monitor/snapshot.test.mjs`, `tests/test_dry_run.sh` e Pester ampliado.
- Espelhos Windows (`loop.ps1`, `dry-run.ps1`, `validate.ps1`) atualizados para perfil e reconhecimento.

### Changed
- Modelo preferido da cascata movido para `openrouter/nex-agi/nex-n2.5-pro:free`
  enquanto `muse-spark-1.3` estiver no limite.

## [0.1.0] - 2026-09-18
### Added
- (A) Saúde comunitária: SECURITY, CODE_OF_CONDUCT, CONTRIBUTING, templates de issue/PR, FUNDING, CITATION.
- (B) Validação por JSON Schema + dry-run/doctor (sh/ps1) integrados ao setup e ao CI.
- (C) Onboarding global em inglês, instalador one-command, Dockerfile/devcontainer/compose demo.
- (D) Adaptadores de sites, triagem two-tier, digest/funil, perfis de exemplo, prompts EN.
- (E) Qualidade: suites TAP/Pester/node:test, CI com testes nos 2 OS, Dependabot mensal, docs/TESTES.md.
- Renomeação open-source genérica (AplicaBot → OportunizaVaga) + espelhos PowerShell/Task Scheduler.
- Painel monitor opcional (Vercel free, sem banco) + daemons de quota/keepalive.
- Docs: QUICKSTART, ARQUITETURA, CUSTO, SEGURANCA, FAQ, PROMPTS + sanitize.sh.
### Notes / Notas
- Pronto para tag v0.1.0: loop/guardião/follow-up funcionais; tag/release ainda não criadas.
