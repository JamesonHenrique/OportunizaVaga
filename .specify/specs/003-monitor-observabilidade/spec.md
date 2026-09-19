# Spec 003 — Monitor e observabilidade

- **Tipo:** serviço web (Next.js na Vercel) + publicadores locais
- **Status:** rascunho (extraído de `~/monitor` RUNBOOK + `~/candidaturas/monitor/` em 2026-09-19)
- **Relacionadas:** 001, 002 (publicam eventos), 004 (keepalive/watchdog no cron)

## 1. Visão geral

Um painel web mostra em tempo real: quantas candidaturas/convites saíram, o que
travou, e — o mais importante — **se o sistema ainda está vivo**. O design separa
**publicação** (scripts locais empurram estado via HTTP) de **apresentação**
(app Next.js que só lê). O coração é o **heartbeat com watchdog**: o publicador
local envia sinal de vida a cada poucos minutos; se o sinal atrasa, o monitor
marca STALE (exit 2) em vez de mostrar dados velhos como se fossem novos —
a falha mais perigosa de um painel de automação é parecer saudável quando o
robô morreu.

## 2. Usuários e personas

- **Candidato:** abre o painel no celular para ver o funil do dia.
- **On-call (o próprio candidato):** recebe o alerta de STALE e age (cap. 004).

## 3. Escopo

### Dentro

- Endpoint de ingestão autenticado (`MONITOR_SECRET`) para eventos: rodada ok,
  rodada vazia, enviada, bloqueada, quota, erro, heartbeat.
- Painel: funil do dia/semana, últimas rodadas, lista de bloqueadas com motivo,
  status vivo/stale por componente (loop, dia, chrome, publicador).
- Watchdog: `exit 2` = STALE; UptimeRobot (ou similar) observa e alerta.
- Publicadores locais idempotentes: `publish-status` (daemon), `publish-once`,
  `snapshot`, `quota-daemon`.

### Fora

- Controle remoto (disparar rodada pelo painel — Comandos 004 é só pull de status).
- Autenticação multiusuário (single-tenant por deploy).
- Métricas de custo de API em tempo real (pós-MVP).

## 4. Requisitos funcionais

- [FR-01] Ingestão via HTTP POST com segredo (`MONITOR_SECRET` em env, nunca no repo).
- [FR-02] Publicadores locais nunca derrubam a rodada: falha de rede → log + segue.
- [FR-03] Heartbeat ≤5 min por componente; atraso >2 intervalos = STALE (watchdog exit 2).
- [FR-04] Painel mostra: enviadas (dia/semana), vazias seguidas, quota hits, último erro, idade dos dados.
- [FR-05] `snapshot` gera estado completo sob demanda (debug sem abrir o servidor).
- [FR-06] `quota-daemon` publica degrau atual de backoff (visibilidade do cap. 001/002).
- [FR-07] Nenhum dado pessoal no painel público: empresa + vaga + data apenas;
  sem CPF, endereço, e-mail, telefone.

## 5. Requisitos não funcionais

- [NFR-01] Deploy em 1 clique (Vercel ou `docker compose up`).
- [NFR-02] Custo zero adicional (tier gratuito).
- [NFR-03] Sem falsos "tudo bem": dado velho sempre rotulado com idade/STALE.

## 6. Critérios de aceite

- [AC-01] Matar o loop → painel marca STALE em ≤12 min.
- [AC-02] Derrubar a rede do publicador → rodada completa normalmente, evento é descartado com log.
- [AC-03] POST sem segredo → 401, nada é gravado.
- [AC-04] Auditoria do painel: zero dados pessoais (grep RG/CPF/e-mail/telefone no bundle).

## 7. Riscos e perguntas abertas

| # | Risco / pergunta | Mitigação / resposta |
|---|------------------|----------------------|
| R1 | Segredo vaza no repo | `.env` + `.gitignore` + gitleaks no CI (ver 005) |
| R2 | Painel público expõe estratégia de busca | Deploy com senha ou URL não listada; FR-07 |
| Q1 | WebSocket ou polling? | Polling primeiro (simplicidade); socket pós-MVP |
