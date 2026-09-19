# Tarefas 003 — Monitor e observabilidade

- [ ] **T1 — App + ingestão** (C1; bloqueia T2)
  Navegar: `.specify/specs/003-monitor-observabilidade/spec.md` (FR-01, FR-04, FR-07).
  Criar: `monitor/` (endpoint + painel com idade dos dados).
  Validar: POST com segredo grava; sem segredo dá 401 (AC-03).

- [ ] **T2 — Publicador daemon** (C2; depende de T1)
  Navegar: spec FR-02, FR-03.
  Criar: `scripts/publish-status.sh`.
  Validar: matar a rede no meio da rodada → rodada completa, log de descarte (AC-02).

- [ ] **T3 — Watchdog + alerta** (C5)
  Navegar: spec FR-03.
  Criar: `scripts/watchdog.sh` (exit 2 = STALE) + doc de setup UptimeRobot.
  Validar: parar heartbeat → exit 2 em ≤12 min (AC-01).

- [ ] **T4 — Snapshot + quota-daemon** (C3, C4)
  Navegar: spec FR-05, FR-06.
  Criar: `scripts/snapshot.sh`, `scripts/quota-daemon.sh`.
  Validar: saída de cada um validada contra o schema.

- [ ] **T5 — Auditoria de privacidade** (AC-04)
  Navegar: spec FR-07.
  Executar: grep de CPF/RG/e-mail/telefone/endereço no bundle e nos exemplos.
  Validar: zero ocorrências; registrar em `docs/SEGURANCA.md`.
