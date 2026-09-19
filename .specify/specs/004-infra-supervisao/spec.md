# Spec 004 — Infra e supervisão (cron, guardião, ciclo de energia)

- **Tipo:** camada de operação da máquina pessoal (sem systemd: cron como supervisor)
- **Status:** rascunho (extraído do crontab + `guardiao.sh` em 2026-09-19)
- **Relacionadas:** 001, 002 (supervisionados), 003 (keepalive), 005 (instalador gera tudo)

## 1. Visão geral

A máquina pessoal não tem systemd, então o **cron é o supervisor**: `@reboot` e
`*/5` ressuscitam o que morreu, horários fixos disparam o que é periódico. O
`guardiao.sh` é idempotente (se já roda, não faz nada) e distingue **processo
vivo** de **lock preso** (incidente 16/09: `sleep` órfão segurava o fd do flock
e o guardião achava que estava tudo bem — desde então ele checa `pgrep`,
não só `fuser`). Completa o ciclo a regra de **fim de expediente** (19/09):
seg–sex, se o sono do loop passar das 17:30, a máquina desliga e o guardião
não ressuscita o loop — o dono religa manualmente.

## 2. Usuários e personas

- **Dono da máquina:** quer "ligar e esquecer"; o sistema se mantém sozinho e
  desliga sozinho no fim do dia útil.
- **Guardião:** cron + script, sem inteligência — só garante presença.

## 3. Escopo

### Dentro

- Tabela cron completa (`CRON_TZ=America/Sao_Paulo`): guardião `@reboot`+`*/5`,
  `dia.sh` 10h diária, `monitor-keepalive` `*/5`, `pull-monitor` `*/10`,
  follow-up seg 09h, digest Telegram 21h05.
- `guardiao.sh`: sobe loop + Chrome CDP se caídos; limpa lock órfão; não
  ressuscita o loop seg–sex após 17:30; log com rotação simples.
- `dormir_ou_desligar` (no loop 001): sono que cruza 17:30 seg–sex vira
  desligamento via sessão gráfica (sem sudo).
- Digest diário Telegram 21h05 (via `cron.env`, secrets só em env).
- `doctor.sh`: checagem de saúde manual (Chrome, locks, JSONs, espaço).

### Fora

- Systemd units (a máquina real não tem; pós-MVP pode ganhar alternativa).
- Wake-on-LAN / ligar sozinho de manhã (o dono liga).
- Múltiplas máquinas.

## 4. Requisitos funcionais

- [FR-01] `guardiao.sh` idempotente: 2ª instância simultânea não duplica loop nem Chrome.
- [FR-02] Detecção por `pgrep` (processo), não só `fuser` (lock) — lição do incidente 16/09.
- [FR-03] Lock órfão (lock preso sem processo) → `fuser -k`, espera 2 s, sobe de novo, tudo logado.
- [FR-04] Seg–sex a partir de 17:30: guardião **não** sobe o loop (mas mantém checagem do Chrome).
- [FR-05] Fim de semana: supervisão normal, sem desligamento programado.
- [FR-06] `guardiao.log` com rotação (teto ~256 KB).
- [FR-07] `doctor.sh` retorna 0 = saudável, ≠0 = problema, com mensagem por checagem.
- [FR-08] Digest 21h05 envia resumo do dia no Telegram; sem secrets no comando (só env).
- [FR-09] Instalador (`install.sh`) gera crontab + `.env` a partir de exemplos, nunca com valores reais.

## 5. Requisitos não funcionais

- [NFR-01] Reboot às 3h da manhã → às 3h06 tudo rodando sem toque humano.
- [NFR-02] Guardião roda em <5 s (é chamado a cada 5 min).
- [NFR-03] Nenhum comando destrutivo sem confirmação (vale p/ instalador).

## 6. Critérios de aceite

- [AC-01] `kill -9` no loop → em ≤6 min está rodando de novo, log registra "loop caido, subindo".
- [AC-02] Simular lock órfão (sleep segurando fd) → guardião limpa e sobe, sem duplicar.
- [AC-03] Seg–sex 17:35 com loop morto → guardião NÃO sobe; sáb mesmo horário → sobe.
- [AC-04] Reboot simulado → cron `@reboot` + ciclo `*/5` restauram loop e Chrome.
- [AC-05] `doctor.sh` numa máquina sã → exit 0; com Chrome morto → ≠0 citando o Chrome.

## 7. Riscos e perguntas abertas

| # | Risco / pergunta | Mitigação / resposta |
|---|------------------|----------------------|
| R1 | Cron duplica por overlap `@reboot` + `*/5` | FR-01 (idempotência + flock) |
| R2 | Desligamento 17:30 perde rodada em curso | Regra só age no sono ENTRE rodadas, nunca no meio |
| R3 | Digest vaza dados no Telegram | Só agregados (números + títulos de vaga); sem dados pessoais |
| Q1 | Suporte a systemd como alternativa? | Pós-MVP (timers espelhando o cron) |
