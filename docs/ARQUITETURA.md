# ARQUITETURA

```
                        ┌─────────────────────────────────────────────┐
cron */5 ──────────────▶│ bot/guardiao.sh (supervisor idempotente)    │
@reboot ───────────────▶│  ├─ loop.sh vivo? senão sobe                │
                        │  └─ Chrome CDP :9222 vivo? senão sobe       │
                        └──────────────┬──────────────────────────────┘
                                       │ flock (instância única)
                        ┌──────────────▼──────────────────────────────┐
                        │ bot/loop.sh (loop infinito)                 │
                        │  1. fingerprint(aplicadas.json) antes       │
                        │  2. escolhe 1 site do rodízio               │
                        │  3. opencode run (cascata de modelos free)  │
                        │     com bot/prompt_loop.md ──▶ Chrome :9222 │
                        │  4. watchdog de quota (mata rodada travada) │
                        │  5. fingerprint depois: mudou? achou vaga   │
                        │     nova → dorme 20min; senão backoff 1h→2h…│
                        │  6. publica snapshot (monitor opcional)     │
                        └──────────────┬──────────────────────────────┘
                                       │ estado durável
                        ┌──────────────▼──────────────────────────────┐
                        │ bot/aplicadas.json (FONTE DA VERDADE)       │
                        │  aplicadas, bloqueados, rodizio, descartes, │
                        │  pular_empresas/tipos, contas_criadas       │
                        │ O modelo NÃO tem memória entre rodadas:     │
                        │ cada rodada é sessão nova que lê/escreve    │
                        │ este arquivo.                               │
                        └─────────────────────────────────────────────┘
```

## Componentes

| Arquivo | Papel |
|---|---|
| `bot/loop.sh` | Loop principal: 1 site/rodada, cascata de modelos, backoffs, watchdog, rotação de log |
| `bot/guardiao.sh` | Supervisor via cron (sem systemd): loop + Chrome; limpa lock órfão |
| `bot/followup.sh` | Rotina semanal (só leitura de status, nunca se candidata) |
| `bot/prompt_*.md` | O "cérebro": regras, rodízio, pré-filtros, canais, formato de registro |
| `browser/chrome-real.sh` | Chrome persistente com CDP :9222 (login 1x vale p/ tudo) |
| `config/sites_permitidos.json` | Allowlist BR em 2 camadas: `--allowed-origins` + regra 7 do prompt |
| `monitor/*.mjs` | `snapshot` (lê JSON+logs) → `publish-status` (heartbeat) / `publish-once` (evento) → Vercel |
| `monitor/quota-daemon.mjs` | Mede cota diária OpenRouter `:free` (único provider com API de uso) |
| `scripts/monitor-keepalive.sh` | Dono único do publisher (sobe se cair) |
| `scripts/pull-monitor.sh` | Fast-forward do painel + restart do publisher se o código mudou |

## Decisões-chave

- **Sessão nova por rodada** (`opencode run`, sem `session --continue`): o histórico
  não carrega nada que `aplicadas.json` não tenha; rodada travada não contamina a próxima.
- **Fingerprint em vez de mtime**: o rodízio sempre regrava o arquivo, então "mudou"
  = soma de aplicadas + bloqueados + descartes. Mtime mentia.
- **Quota só conta em linha de erro**: varrer o corpo da rodada gerava falso positivo
  (anúncio de vaga com "trial"/"credit" mandava o loop dormir).
- **Watchdog via log interno**: o opencode entra em retry silencioso sem imprimir nada
  no stdout; o erro só existe no log interno — sem o watchdog, cada rodada bloqueada
  queimava 20 min de timeout.
- **Descarte de listagem ≠ bloqueado**: título/card filtrado vira contador
  (`descartes_listagem`), não entrada — bloqueados é só p/ vaga real com motivo concreto.
- **Monitor sem banco**: a Vercel guarda só o último snapshot em memória (custo zero);
  o heartbeat repõe tudo em segundos após cold start.
