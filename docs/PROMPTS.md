# PROMPTS — como customizar o cérebro do robô

Os prompts são o comportamento do robô. `bot/dados_candidato.json` é o **quê**
(seus dados); os prompts são o **como**. Adapte os 3 pontos abaixo ao seu perfil —
o resto (rodízio, anti-ruído, canais, registro) funciona como está.

## 1. `bot/prompt_loop.md` — regra 4 (STACK)

Troque o bloco `EXEMPLO` pelo seu stack real:

- `STACK REAL` → `experiencia.tecnologias` no seu `dados_candidato.json`.
- `STACK SIMILAR-JR` → similares que você topa atuar **sem afirmar domínio**
  (sempre com `frase_transferencia` no CV/form).
- `PROIBIDO usar similar para` → liste o que, no seu perfil, nunca pode ser
  "transferido" (ex.: alemão que você não fala, ferramenta que você nunca abriu).

## 2. `bot/prompt_loop.md` — PRÉ-FILTRO + TERMOS

- O pré-filtro de listagem (nível/modelo/stack) deve espelhar o **seu** conjunto
  REAL + SIMILAR-JR — é ele que economiza leitura de modelo (e quota).
- `TERMOS`: priorize o seu stack real; alterne por rodada, nunca repita sempre o mesmo.
- `pular_tipos` (em `aplicadas.json`): áreas que você nunca quer (ex.: DS/BI, UX, ERP)
  — o robô descarta ainda na listagem, sem abrir nem registrar bloqueio.

## 3. Nível, modelo e salário

- Regra 1 (remoto) e regra 3 (JR/trainee): ajuste se seu alvo for outro
  (ex.: aceitar híbrido na sua cidade) — mas seja explícito, o robô segue ao pé da letra.
- `pretensao_regra`: base `SEU_VALOR_BASE`; campo numérico **nunca** recebe "A combinar".

## 4. `bot/prompt_followup.md` e `bot/prompt_perfil_gupy.md`

- Follow-up: ajuste os portais à sua realidade (de onde vieram suas vagas).
  Sessão de **só leitura** — nunca adicione ação de candidatura aqui.
- Perfil Gupy: faça **1 item por execução**; se um item travar (captcha, autocomplete
  quebrado), documente em `NOTA TÉCNICA` e siga — não repita estratégia falha.

## Regras de edição

- Mantenha o sentinel `QUOTA_EXAUSTA` (última linha): é ele que diz ao `loop.sh`
  para cascatear de modelo.
- Mantenha o formato de registro (`data` local + `enviada_em`/`bloqueado_em` com fuso
  via `date` no shell): o monitor prioriza esses campos; UTC quebra o painel.
- Teste 1 rodada manual após cada mudança grande (`./bot/loop.sh` + Ctrl+C).
