# Plano 002 — Rotina LinkedIn RH

## Arquitetura (deploy real → alvo open source)

```
cron (0 10 * * *)
  └─ dia.sh ── flock dia.lock ── ensure_chrome ─┐
      ├─ flock -w 1800 browser.lock ── opencode run + prompt_dia.md (RUN_TIMEOUT 55m)
      └─ valida conectados.json ── publica monitor
```

**Alvo open source:** `scripts/linkedin-day.sh` + `config/linkedin-prompt.template.md` +
`config/linkedin-schema.json` (conectados, pular_perfis, bloqueios, meta) — sem URL,
delay e quota parametrizáveis via `.env`.

## Componentes

| # | Componente | Origem real | Destino OSS |
|---|-----------|-------------|-------------|
| C1 | Runner diário + trava mtime | `~/linkedin-rh/dia.sh` | `scripts/linkedin-day.sh` |
| C2 | Prompt do operador | `prompt_dia.md` | `config/linkedin-prompt.template.md` |
| C3 | Schema + exemplo | `conectados.json` (estrutura) | `config/linkedin-schema.json`, `config/linkedin.example.json` |
| C4 | Backoff quota | `QUOTA_STEPS` em `dia.sh` | `scripts/lib/backoff.sh` (compartilhada com 001) |
| C5 | Lock browser compartilhado | `BROWSER_LOCK` | `scripts/lib/browser-lock.sh` (compartilhada com 001) |

## Ordem de construção

1. C3 (schema primeiro — trava mtime depende dos campos).
2. C4 + C5 (libs compartilhadas com 001; construir uma vez, reusar).
3. C1 (runner + FR-07 trava mtime + FR-08 `LIMITE_LINKEDIN`).
4. C2 (prompt com placeholders `{{MAX_DAY}}`, `{{TARGET}}`, `{{DELAY_MIN}}`…).
5. Teste de duplicata (AC-03) e teste `LIMITE_LINKEDIN` (AC-02).

## Decisões

- **D1 — mtime, não contador:** a trava anti-duplicata usa mtime do JSON porque
  sobrevive a mortes do processo em qualquer ponto (incidente 17/09).
- **D2 — Sem nota ≠ falha:** conta gratuita esgota quota de notas; o dia segue
  sem nota (FR-05). Perder o dia seria pior que perder a nota.

## Plano de testes

- [T-01] AC-01: 5 dias 10/10, zero dup, zero avisos.
- [T-02] AC-02: `LIMITE_LINKEDIN` simulado → encerra ≤1 min.
- [T-03] AC-03: kill -9 após 5 envios sem escrita → dia seguinte não reenvia.
- [T-04] AC-04: sem quota de notas → 10 envios sem nota, dia ok.
