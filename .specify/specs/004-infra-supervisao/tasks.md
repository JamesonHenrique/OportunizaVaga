# Tarefas 004 — Infra e supervisão

- [ ] **T1 — Regra de energia** (C2; bloqueia T2)
  Navegar: `.specify/specs/004-infra-supervisao/spec.md` (FR-04, FR-05).
  Criar: `scripts/lib/power-window.sh` (`POWER_OFF_TIME`, `POWER_OFF_DAYS`, default opt-out).
  Validar: simular seg 16h/18h e sábado (igual ao teste feito no deploy real em 19/09).

- [ ] **T2 — Guardião** (C1; depende de T1)
  Navegar: spec FR-01, FR-02, FR-03, FR-06.
  Criar: `scripts/guardian.sh`.
  Validar: AC-01 (kill -9 → ≤6 min) e AC-02 (lock órfão).

- [ ] **T3 — Doctor** (C3)
  Navegar: spec FR-07.
  Criar: `scripts/doctor.sh`.
  Validar: AC-05 (sã → 0; Chrome morto → ≠0).

- [ ] **T4 — Digest** (C4)
  Navegar: spec FR-08, risco R3.
  Criar: `scripts/digest.sh`.
  Validar: mensagem de exemplo só com agregados; grep sem dados pessoais.

- [ ] **T5 — Instalador + crontab** (C5; depende de T1–T4)
  Navegar: spec FR-09; plan D2, D3.
  Criar/ajustar: `install.sh`, `config/crontab.example`, `.env.example`.
  Validar: instalação limpa em container → `doctor.sh` exit 0; nenhum secret escrito em disco fora do `.env`.
