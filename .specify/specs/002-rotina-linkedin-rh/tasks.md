# Tarefas 002 — Rotina LinkedIn RH

- [ ] **T1 — Schema + exemplo** (C3; bloqueia T3)
  Navegar: `.specify/specs/002-rotina-linkedin-rh/spec.md` (FR-02, FR-06–FR-08).
  Criar: `config/linkedin-schema.json`, `config/linkedin.example.json`.
  Validar: `scripts/validate-config.sh config/linkedin.example.json`.

- [ ] **T2 — Libs compartilhadas** (C4, C5; reusadas da 001)
  Navegar: `.specify/specs/002-rotina-linkedin-rh/plan.md` (D1).
  Criar: `scripts/lib/backoff.sh`, `scripts/lib/browser-lock.sh` (se ainda não existirem da 001).
  Validar: teste de fumaça de cada função.

- [ ] **T3 — Runner diário** (C1; depende de T1, T2)
  Navegar: spec FR-01, FR-07, FR-08, FR-09, FR-10.
  Criar: `scripts/linkedin-day.sh`.
  Validar: `bash -n`; dry-run com Chrome fechado (deve falhar com mensagem clara, sem enviar nada).

- [ ] **T4 — Prompt template** (C2)
  Navegar: spec FR-03, FR-04, FR-05, FR-11.
  Criar: `config/linkedin-prompt.template.md`.
  Validar: renderizar com `.env` de exemplo e conferir placeholders.

- [ ] **T5 — Testes de aceite** (T-01…T-04 do plan)
  Navegar: plan (Plano de testes).
  Executar: AC-02, AC-03, AC-04 simulados + 5 dias reais p/ AC-01.
  Validar: registrar resultado em `docs/TESTES.md`.
