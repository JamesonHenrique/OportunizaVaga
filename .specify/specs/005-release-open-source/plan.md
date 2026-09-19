# Plano 005 — Release open source

## Arquitetura (pipeline de publicação)

```
deploy pessoal (~/candidaturas, ~/linkedin-rh)
  ── sanitize.sh ──▶ exemplos/schemas públicos ──▶ repo origem (OportunizaVaga)
                                                        │  CI: gitleaks + validate + bash -n
                                                        └─▶ espelho (diff vazio)
```

## Componentes

| # | Componente | Origem real | Destino OSS |
|---|-----------|-------------|-------------|
| C1 | Sanitizador | `scripts/sanitize.sh` (existe, revisar) | `scripts/sanitize.sh` + relatório |
| C2 | Validador | `scripts/validate-config.sh` (existe) | idem + CI |
| C3 | Instalador | `install.sh` + `install.ps1` (existem) | revisados p/ FR-07 |
| C4 | CI | (novo) | `.github/workflows/ci.yml` (gitleaks, validate, bash -n, drift check) |
| C5 | Docs de release | docs existentes | revisão + CHANGELOG.md |

## Ordem de construção

1. C1 (sem sanitizador confiável, nada anda) + teste AC-02.
2. Consolidação das cópias (FR-06, AC-04) — decidir origem única.
3. C3 (instalação limpa testada em container — AC-01).
4. C4 (CI trava regressões: segredo, drift, exemplo inválido).
5. C5 + checagem de histórico (R1) + AC-05.

## Decisões

- **D1 — Origem única:** propor `OportunizaVaga` como origem (mais completo:
  tem `sites/*.sh`, docs e wizard que a cópia não tem); confirmar com o dono.
- **D2 — Histórico:** auditar `git log -p` por segredos antes de anunciar; se
  achar, republicar com histórico limpo (BFG) — anunciar só depois.
- **D3 — Defaults éticos travados:** limites de volume ficam no código com os
  valores conservadores; afrouxar exige edição consciente.

## Plano de testes

- [T-01] AC-01: instalação limpa em container → doctor verde.
- [T-02] AC-02: sanitize → zero valores reais nos exemplos.
- [T-03] AC-03: token fake → CI vermelho.
- [T-04] AC-04: origem×espelho sem drift.
- [T-05] AC-05: revisão externa/checklist de release.
