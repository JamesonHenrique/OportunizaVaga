# Plano 004 — Infra e supervisão

## Arquitetura

```
cron (CRON_TZ=America/Sao_Paulo)
 ├─ @reboot + */5 ── guardiao.sh ──┬─ pgrep loop? ── não ──▶ sobe (exceto seg–sex ≥17:30)
 │                                 ├─ lock órfão? ──▶ fuser -k + sobe
 │                                 └─ Chrome CDP? ── não ──▶ sobe (sempre)
 ├─ 0 10 * * * ── dia.sh (spec 002)
 ├─ */5 ── monitor-keepalive (spec 003)
 ├─ */10 ── pull-monitor (comandos → Telegram)
 ├─ 0 9 * * 1 ── follow-up semanal
 └─ 5 21 * * * ── digest Telegram (cron.env)
```

**Alvo open source:** `scripts/guardian.sh`, `scripts/doctor.sh`,
`scripts/digest.sh`, `install.sh` (gera crontab + `.env`), `config/crontab.example`.

## Componentes

| # | Componente | Origem real | Destino OSS |
|---|-----------|-------------|-------------|
| C1 | Guardião | `~/candidaturas/guardiao.sh` | `scripts/guardian.sh` |
| C2 | Regra de energia | `dormir_ou_desligar` + `EXPEDIENTE_ENCERRADO` | `scripts/lib/power-window.sh` (hora/dias via `.env`) |
| C3 | Doctor | `doctor.sh` | `scripts/doctor.sh` |
| C4 | Digest | `digest` 21h05 | `scripts/digest.sh` |
| C5 | Instalador | (novo; usa `install.sh` existente como base) | `install.sh` + `config/crontab.example` + `.env.example` |

## Ordem de construção

1. C2 (regra de energia parametrizável — sem ela, C1 não sabe quando não agir).
2. C1 (guardião + teste de lock órfão AC-02).
3. C3 (doctor — usa as mesmas checagens do guardião).
4. C4 (digest só com agregados — R3).
5. C5 (instalador gera tudo; roda T-03 de segurança).

## Decisões

- **D1 — pgrep, não fuser:** incidente 16/09 provou que lock ≠ processo vivo.
- **D2 — Energia via `.env`:** `POWER_OFF_TIME=17:30`, `POWER_OFF_DAYS=1-5` com
  default "desligado" (opt-in explícito; ninguém quer o PC desligando por padrão).
- **D3 — Desligar pela sessão gráfica:** sem sudo no cron; `xfce4-session-logout`
  com fallback dbus (documentar GNOME/KDE equivalentes no instalador).

## Plano de testes

- [T-01] AC-01: kill -9 → volta em ≤6 min.
- [T-02] AC-02: lock órfão simulado → limpa sem duplicar.
- [T-03] AC-03: 17:35 seg vs sáb → não sobe vs sobe.
- [T-04] AC-04: reboot → tudo de pé.
- [T-05] AC-05: doctor sã vs Chrome morto.
