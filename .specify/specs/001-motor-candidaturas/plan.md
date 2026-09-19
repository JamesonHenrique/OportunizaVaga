# Plano — 001 Motor de Candidaturas

## Constituição aplicável

§1 (rodadas sem estado), §2 (nunca inventar), §3 (fuso Fortaleza), §4 (custo
zero), §5 (instância única), §6 (ruído ≠ bloqueio), §9 (observabilidade).

## Arquitetura / abordagem

```
loop.sh ── flock instância ── ensure_chrome (CDP :9222) ── cascata MODELOS
   │── timeout 20m + watchdog (quota silenciosa) ── opencode run (prompt_loop)
   └── pós-rodada: classifica saída (ok / vazia / quota / erro / lock)
        └── dormir_ou_desligar (respeita expediente 17:30 seg–sex)
```

Manter shell portátil (bash, `flock`, `timeout`, `date -d`); lógica de decisão
no agente via prompt; estado só em JSON com schemas em `config/`.

## Passo a passo

1. Reconciliar `bot/loop.sh` do repo com o deploy pessoal (o pessoal tem
   `dormir_ou_desligar` e watchdog mais novos — portar para o repo).
2. Cobrir `dry-run.sh` para simular rodada sem aplicar (usado na demo).
3. Validar schemas `aplicadas.schema.json` / `dados_candidato.schema.json`
   contra exemplos em `examples/`.
4. Rodar `doctor.sh` + `validate.sh` no deploy pessoal após cada mudança.

## Testes e validação

- `bash -n bot/loop.sh` → sintaxe OK.
- `./bot/dry-run.sh` → rodada simulada, zero escrita em estado real.
- `bot/doctor.sh` → exit 0 (essencial ok).
- Simulação de expediente: 4 cenários (sono cruza/não cruza 17:30, dia
  útil/fim de semana) sem executar halt de verdade.

## Rollback

Backups `.bak-<data>` ao lado do original + `git stash`/revert no repo;
cron anterior em `crontab.bak-*`; restart do loop via guardião (≤5 min).
