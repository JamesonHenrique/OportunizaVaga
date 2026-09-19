# 001 — Motor de Candidaturas

## Visão geral

Loop contínuo que aplica o candidato a vagas JR/trainee remotas brasileiras,
1 site por rodada, com estado em `aplicadas.json`. Roda no PC do candidato a
custo zero via modelos gratuitos em cascata.

## Estado atual (comportamento observado)

- `bot/loop.sh` (deploy pessoal: `~/candidaturas/loop.sh`, 379 linhas):
  lock de instância (`flock -n /tmp/candidaturas-loop.lock`); garante Chrome
  CDP `127.0.0.1:9222` (sobe `browser/chrome-real.sh` com `DISPLAY=:0` se
  cair); cascata de modelos `MODELOS[]` → OpenRouter `:free` → NVIDIA →
  Copilot opcional; `timeout 20m` + watchdog anti-retry-silencioso (checa
  `quota_in_opencode_log` + tamanho do log a cada 15 s após espera mínima).
- Espera entre rodadas: 20 min após envio; vazias seguidas com teto
  (`VAZIA_STEPS`, ex. 120 min após 2 seguidas); quota com `QUOTA_STEPS`
  + `MAX_QUOTA_RETRIES`; `fail_wait` exponencial com teto para erros.
- Fim de expediente (2026-09-19): `dormir_ou_desligar` — seg–sex, se o sono
  passar das 17:30, dorme até 17:30 e desliga via sessão XFCE.
- Prompt (`bot/prompt_loop.md`): regras 1–8 (só remoto, nunca `pular_empresas`,
  só JR/trainee, nunca inventar, máx. 3/rodada, economia de RAM/abas, só sites
  BR da allowlist, foco). Rodízio circular em `rodizio.proximo`; recência em
  2 níveis (≤14 dias, fallback 15–21); pré-filtro de listagem (nível/modelo/
  stack) com contadores `descartes_listagem`; canais por prioridade; CV por
  vaga só quando o canal anexa arquivo (nunca no Gupy); registro com `data`
  local + `enviada_em` com fuso; regra anti-ruído de `bloqueados`.
- `sites_permitidos.json`: allowlist aplicada em 2 camadas (MCP
  `--allowed-origins` + regra 7). Domínio entra como `https://x` E `https://*.x`.
- Satélites: `followup.sh` (seg 09h, só lê status), `digest.sh` (21h05,
  Telegram opcional via env), `funnel.sh`/`funil.csv`, `doctor.sh`,
  `validate.sh` (schemas em `config/`), `dry-run.sh`.

## Requisitos funcionais

- [ ] RF-01: rodada lê estado, usa 1 site do rodízio, grava estado, fecha abas.
- [ ] RF-02: só vaga remota + JR/trainee + BR + ≤21 dias; resto é descarte contado.
- [ ] RF-03: todo envio registrado com `data` + `enviada_em` locais antes de fechar abas.
- [ ] RF-04: cascata de modelos sem custo; quota nunca derruba o loop.
- [ ] RF-05: instância única; segunda tentativa sai silenciosa (exit 0).
- [ ] RF-06: seg–sex, sono que cruze 17:30 vira desligamento; guardião não ressuscita.

## Requisitos não funcionais

- [ ] RNF-01: rodada útil cabe em ~8 min (meta anti-timeout).
- [ ] RNF-02: custo operacional zero (só modelos gratuitos).
- [ ] RNF-03: `loop.log` legível (só resumos); dumps em `logs/` com rotação.

## Contratos de estado (JSON)

`aplicadas.json`: `aplicadas[]` (`chave, empresa, vaga, remota, como, cv,
data: YYYY-MM-DD, enviada_em: ISO-com-fuso`), `bloqueados{}` (+`bloqueado_em`),
`bloqueados_arquivados`, `pular_empresas[]`, `pular_tipos[]`, `rodizio
{proximo, ultima_rodada}`, `descartes_listagem{nivel, modelo, stack, total}`,
`contas_criadas`, `manutencao_gupy`, `log_rodada_*`, `log_rodadas[]`.

## Cenários de aceite

1. **Rodada com envio**: Given rodízio no Gupy e JR remota nova, When rodada
   executa, Then ≤3 aplicadas registradas com carimbo local e abas fechadas.
2. **Rodada vazia**: Given zero JR nova, When rodada executa, Then só
   `rodizio.proximo` avança, sem tocar em `bloqueados`.
3. **Quota total**: Given todos os modelos no teto, When detectado, Then
   espera `QUOTA_STEPS` e tenta de novo, até `MAX_QUOTA_RETRIES`.
4. **Expediente**: Given segunda 16h + sono de 2h, When aplicar espera,
   Then dorme até 17:30 e desliga; guardião não religa.

## Fora de escopo

Dashboard web (spec 003), rotina LinkedIn (spec 002), supervisão cron (004).

## Riscos (P1/P2)

- P1: sessão de site expira e trava canal (LinkedIn/Indeed login) — sem senha
  no escopo, só re-login manual resolve.
- P2: sites esgotam para JR remota (programathor 4 rodadas); anti-bot/captcha;
  retry silencioso do modelo mascarando quota (mitigado pelo watchdog).
