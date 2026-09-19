# Spec 002 — Rotina LinkedIn RH (convites diários)

- **Tipo:** batch diário assistido (1 rodada/dia, meta ≤10 convites)
- **Status:** rascunho (extraído do deploy real `~/linkedin-rh` em 2026-09-19)
- **Relacionadas:** 001 (disputa o mesmo Chrome), 004 (cron 10h), 005 (publicar versão genérica)

## 1. Visão geral

Todo dia útil às 10h o `dia.sh` roda **uma rodada única** de convites de conexão
para recrutadores de tecnologia no LinkedIn. Diferente do motor 001 (loop
contínuo com rodízio), aqui é **um site, um público, volume fixo e baixo**:
máximo 10 convites/dia, meta 70/semana. A trava anti-duplicata não é um campo
de contador, e sim o **mtime de `conectados.json`**: se o arquivo não mudou em
24h após uma rodada com envios, o dia encerra (incidente 17/09: timeout matou a
rodada depois dos envios mas antes do registro → 5 convites duplicados no dia
seguinte; a trava mtime foi a correção).

## 2. Usuários e personas

- **Candidato:** quer rede com RHs que contratam o seu perfil, sem risco de restrição da conta.
- **Guardião da conta:** o próprio script — qualquer sinal de `LIMITE_LINKEDIN`
  encerra o dia imediatamente, sem tentar contornar.

## 3. Escopo

### Dentro

- 1 rodada/dia via `opencode run` com `prompt_dia.md`, timeout 55 min
  (10 convites × delay 60–180 s entre ações ≈ 50 min reais).
- Registro de cada aceite em `conectados.json` (`conectados`, `pular_perfis`,
  `bloqueios`, `meta`), com campo `data` local em toda entrada.
- Backoff de quota em 3 degraus (15/30/60 min, máx 4 tentativas); `QUOTA_EXAUSTA` aborta.
- Lock de browser compartilhado com 001 (`flock -w 1800 -E 75`); se o motor de
  candidaturas segurar o Chrome >15 min, a rodada do dia é adiada, não forçada.

### Fora

- Mensagens de follow-up para conexões aceitas (pós-MVP).
- Endossos, posts, interação com feed.
- Múltiplas contas / múltiplos perfis.

## 4. Requisitos funcionais

- [FR-01] `dia.sh` executa no máximo 1 rodada/dia (cron `0 10 * * *`), com lock
  de instância; segunda invocação no mesmo dia sai em silêncio.
- [FR-02] Limite rígido: **≤10 convites/dia**, meta 70/semana (`meta` em `conectados.json`).
- [FR-03] Público-alvo: **somente RH ativo** (recrutador/talent acquisition/headhunter
  com atividade recente) de empresas que contratam o perfil do candidato
  (Java Jr remoto BR, no deploy real).
- [FR-04] Delay 60–180 s entre convites (anti-detecção).
- [FR-05] Nota personalizada quando houver quota de notas; se a quota de notas
  da conta gratuita esgotar, enviar **sem nota** (nunca travar o dia por isso).
- [FR-06] Antes de cada convite, checar `conectados` e `pular_perfis`; nunca
  reconvidar.
- [FR-07] Trava anti-duplicata: ao fim de rodada com envios, o mtime de
  `conectados.json` deve ser posterior ao início da rodada; se o arquivo não
  mudou em 24h após envios, encerrar o dia (não reenviar).
- [FR-08] `LIMITE_LINKEDIN` (aviso de limite semanal da plataforma) → encerrar o
  dia imediatamente e registrar em `bloqueios`.
- [FR-09] `QUOTA_EXAUSTA` do modelo → backoff 900/1800/3600 s, no máx 4 tentativas (~2h).
- [FR-10] Conflito de lock com 001 (status 75) → retry com backoff; 3 falhas seguidas encerram o dia.
- [FR-11] Resposta da rodada em ≤10 linhas (alvos, enviados, bloqueados); sem HTML/snapshot.
- [FR-12] `conectados.json` íntegro ao fim (parse `python3 -m json.tool`); backup antes de migração de schema.

## 5. Requisitos não funcionais

- [NFR-01] Conta do usuário jamais em risco: volume baixo, delays humanos, parada
  imediata em qualquer aviso da plataforma.
- [NFR-02] Zero duplicatas entre dias (trava mtime, FR-07).
- [NFR-03] Rodada cabe em 55 min (timeout = limite, não meta).

## 6. Critérios de aceite

- [AC-01] 5 dias seguidos com 10/10 convites registrados, zero duplicatas, zero avisos da plataforma.
- [AC-02] Simular `LIMITE_LINKEDIN` → dia encerra em ≤1 min, `bloqueios` atualizado.
- [AC-03] Matar o processo após 5 envios sem escrita → dia seguinte não reenvia (trava mtime atua).
- [AC-04] Conta gratuita sem quota de notas → 10 envios sem nota, dia conta como ok.

## 7. Riscos e perguntas abertas

| # | Risco / pergunta | Mitigação / resposta |
|---|------------------|----------------------|
| R1 | Mudança nos seletores do LinkedIn quebra a rodada | Pre-filtro por card; falhar com `bloqueado:motivo`, nunca insistir |
| R2 | Restrição temporária da conta | FR-08; volume conservador (10/dia << limite conhecido) |
| R3 | Timeout 55 min vira rotina se delays aumentarem | Alerta se 3 dias seguidos baterem no timeout |
| Q1 | Follow-up pós-aceite entra no MVP? | Não — pós-MVP |
