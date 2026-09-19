# Tarefas 005 — Release open source

- [ ] **T1 — Sanitizador confiável** (C1; bloqueia as demais)
  Navegar: `.specify/specs/005-release-open-source/spec.md` (FR-02), plan D2.
  Revisar: `scripts/sanitize.sh` contra a lista de arquivos do deploy real.
  Validar: AC-02 (sanitize → grep de valores reais vazio).

- [ ] **T2 — Consolidação das cópias** (FR-06)
  Navegar: spec FR-06; plan D1.
  Executar: diff completo origem×cópia, portar o que falta, espelhar.
  Validar: AC-04 (`diff -r` vazio).

- [ ] **T3 — Instalação limpa** (C3; depende de T1, T2)
  Navegar: spec FR-07, FR-09.
  Executar: `install.sh` em container Ubuntu limpo.
  Validar: AC-01 (`doctor.sh` exit 0 em <15 min).

- [ ] **T4 — CI** (C4)
  Navegar: spec FR-01, FR-03, FR-04.
  Criar: `.github/workflows/ci.yml` (gitleaks + validate + `bash -n` + drift check).
  Validar: AC-03 (token fake → CI vermelho).

- [ ] **T5 — Auditoria de histórico + release** (C5; depende de T1–T4)
  Navegar: spec FR-05, FR-08, risco R1.
  Executar: `git log -p` por segredos; revisar docs; escrever CHANGELOG.
  Validar: AC-05 (checklist de release assinado). Só então anunciar.
