# Plano 003 — Monitor e observabilidade

## Arquitetura

```
loop.sh / dia.sh ── publish-status (daemon) ──POST+SECRET──▶ Next.js (Vercel)
snapshot (sob demanda) ──▶ arquivo local          ▲
quota-daemon ──▶ degrau de backoff ───────────────┘          │
                                                    UptimeRobot ──▶ alerta STALE
```

**Alvo open source:** `monitor/` (app Next.js mínimo) + `scripts/publish-*.sh` +
`monitor/Dockerfile` alternativo + `.env.example` com `MONITOR_SECRET`.

## Componentes

| # | Componente | Origem real | Destino OSS |
|---|-----------|-------------|-------------|
| C1 | App + endpoint ingestão | `~/monitor` | `monitor/` |
| C2 | Publicador daemon | `monitor/publish-status` | `scripts/publish-status.sh` |
| C3 | Publicador único + snapshot | `publish-once`, `snapshot` | `scripts/publish-once.sh`, `scripts/snapshot.sh` |
| C4 | Publicador de quota | `quota-daemon` | `scripts/quota-daemon.sh` |
| C5 | Watchdog + keepalive | `monitor-keepalive.sh`, watchdog exit 2 | `scripts/watchdog.sh` + exemplo UptimeRobot em `docs/` |

## Ordem de construção

1. C1 (endpoint + painel mínimo com idade dos dados).
2. C2 (daemon com retry que nunca falha a rodada — FR-02).
3. C5 (watchdog exit 2 + doc UptimeRobot).
4. C3 + C4.
5. Testes AC-01…AC-04.

## Decisões

- **D1 — Push, não pull:** o servidor pessoal não tem IP público; os scripts
  locais empurram estado para a nuvem (funciona atrás de NAT).
- **D2 — Falha do monitor nunca falha a rodada:** observabilidade é acessória;
  o funil real está nos JSONs locais.

## Plano de testes

- [T-01] AC-01: kill loop → STALE ≤12 min.
- [T-02] AC-02: sem rede → rodada ok, log de descarte.
- [T-03] AC-03: POST sem segredo → 401.
- [T-04] AC-04: grep de dados pessoais no bundle → zero.
