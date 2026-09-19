# Tarefas — 001 Motor de Candidaturas

- [ ] T01: portar `dormir_ou_desligar` + watchdog atuais do deploy para `bot/loop.sh` (verificar com `diff` + `bash -n`).
- [ ] T02: validar `examples/*.json` contra `config/*.schema.json` (verificar com `scripts/validate.sh`).
- [ ] T03: executar `dry-run.sh` e confirmar zero escrita em estado (verificar com `git status` limpo em dados de estado).
- [ ] T04: simular os 4 cenários de expediente sem halt real (verificar com log `dormiria X + DESLIGARIA`).
- [ ] T05: rodar `doctor.sh` no deploy e zerar itens essenciais (verificar com exit 0).

## Critério de pronto

Repo e deploy com o mesmo `loop.sh` lógico; dry-run limpo; P1/P2 do spec
revisados.
