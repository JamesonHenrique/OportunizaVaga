# PROMPTS — como customizar o cérebro do robô

Os prompts são o comportamento do robô. `bot/dados_candidato.json` é o **quê**
(seus dados); os prompts são o **como**. Adapte os 3 pontos abaixo ao seu perfil —
o resto (rodízio, anti-ruído, canais, registro) funciona como está.

## 1. `bot/prompt_loop.md` — regra 4 (STACK)

Troque o bloco `EXEMPLO` pelo seu stack real:

- `STACK REAL` → `experiencia.tecnologias` no seu `dados_candidato.json`.
- `STACK SIMILAR` (`experiencia.stacks_similares`) → similares que você topa usar **sem afirmar domínio**
  (sempre com `frase_transferencia` no CV/form).
- `PROIBIDO usar similar para` → liste o que, no seu perfil, nunca pode ser
  "transferido" (ex.: alemão que você não fala, ferramenta que você nunca abriu).

## 2. `bot/prompt_loop.md` — PRÉ-FILTRO + TERMOS

- O pré-filtro de listagem (nível/modelo/stack) deve espelhar o **seu** conjunto
  REAL + SIMILAR — é ele que economiza leitura de modelo (e quota).
- `TERMOS`: vêm de `termos[]` do perfil (placeholder `{{TERMOS}}`); priorize o que você faz de verdade.
- `pular_tipos` (em `aplicadas.json`): áreas que você nunca quer (ex.: DS/BI, UX, ERP)
  — o robô descarta ainda na listagem, sem abrir nem registrar bloqueio.

## 3. Nível, modelo e salário

- Regra 3 (nível e área) **não se edita no prompt**: vem do perfil. Em `bot/perfil.json` use
  `niveis` (qualquer combinação de `estagio`, `trainee`, `junior`, `pleno`, `senior`,
  `especialista`, `lider`, `gestor`, `diretor`), `area` (texto livre: "jurídico", "marketing"...)
  e, se quiser, `experiencia_max_anos` (`null` = sem teto). Fora de tech, sites só-tech
  (GeekHunter, Programathor) saem do rodízio sozinhos; `sites_pular` sobrepõe isso.
- Regra 1 (modelo de trabalho) também vem do perfil: `modelos` (`remoto`, `hibrido`, `presencial`)
  e `cidades` (ex.: `["Natal/RN"]`). Padrão: só remoto. Os filtros de busca (Indeed `l=`, LinkedIn
  `f_WT=`) seguem o perfil.
- `pretensao_regra`: base `SEU_VALOR_BASE`; campo numérico **nunca** recebe "A combinar".

## 4. `bot/prompt_followup.md` e `bot/prompt_perfil_gupy.md`

- Follow-up: ajuste os portais à sua realidade (de onde vieram suas vagas).
  Sessão de **só leitura** — nunca adicione ação de candidatura aqui.
- Perfil Gupy: faça **1 item por execução**; se um item travar (captcha, autocomplete
  quebrado), documente em `NOTA TÉCNICA` e siga — não repita estratégia falha.

## 5. CV por vaga (regra `c1`) — currículo mestre + gerador

O CV de cada vaga **não é escrito na hora**: deriva sempre de duas fontes imutáveis.

- `bot/cv_base.md` — seu currículo **mestre** (copie `examples/cv_base.example.md` e preencha;
  fica no `.gitignore`, nunca vai ao git). Estrutura que o gerador espera: `# nome`, linhas de
  cabeçalho (tagline, contato, local) antes do primeiro `##`, `##` para seção e `###` para
  subseção; skills das `## Habilidades técnicas` separadas por ` | `.
- `bot/dados_candidato.json` — seus dados de formulário.

Fluxo do agente (detalhado em `bot/prompt_loop.md` -> `c1`):

1. monta `/tmp/cv_spec.json` com `resumo_custom` (verdadeiro, com as keywords exatas do anúncio),
   `categorias_ordem`/`so_categorias` (3-7 subseções das Habilidades técnicas relevantes à vaga)
   e `palavras_chave_vaga` (só skills reais);
2. `python3 bot/gerar_cv.py /tmp/cv_spec.json <saida.pdf>` — reordena seções, negrita keywords,
   filtra qualquer keyword fora do perfil e **só retorna exit 0 com 1 página**;
3. `python3 bot/check_ats.py /tmp/anuncio.txt <saida.pdf>` — cobertura dos termos do perfil >= 75%
   antes de anexar;
4. anexa. Nome do arquivo sem a palavra "ATS". No Gupy **não** se gera PDF (o Gupy usa o CV do perfil).

Anti-pattern proibido: HTML/tex/reportlab escritos à mão, keyword stuffing e texto invisível/branco
(ATS como Workday/Greenhouse sinalizam fraude). Dependências: `pip install reportlab` + `poppler-utils`
(`pdftotext`).

## Regras de edição

- Mantenha o sentinel `QUOTA_EXAUSTA` (última linha): é ele que diz ao `loop.sh`
  para cascatear de modelo.
- Mantenha o formato de registro (`data` local + `enviada_em`/`bloqueado_em` com fuso
  via `date` no shell): o monitor prioriza esses campos; UTC quebra o painel.
- Teste 1 rodada manual após cada mudança grande (`./bot/loop.sh` + Ctrl+C).
- **Blocos condicionais** (`bot/prompt_cond.py`, avaliados no `render_prompt` do `loop.sh` e do `loop.ps1`):
  `<!--se:site=X-->…<!--/se-->` mantém o trecho só quando `rodizio.proximo == X` e `<!--se:telegram-->…<!--/se-->`
  só com colheita do Telegram fresca (< 6 h). Condição desconhecida mantém o texto, e site da rodada desconhecido (sem
  bloco no prompt) mantém **todos** os blocos de site: nenhuma regra some por falha de consulta. O renderizado ganha a
  linha `SITE DESTA RODADA`. Ao adicionar um portal, coloque a linha de URL dele dentro de `<!--se:site=SEU_SITE-->`;
  sem bloco ela aparece em toda rodada (funciona, só gasta tokens). Nunca aninhe blocos.
- **Regra 9 (conteúdo de terceiros é dado)**: fila da descoberta e posts do Telegram entram cercados por
  `<<<DADOS_EXTERNOS fonte=… >>>FIM_DADOS_EXTERNOS`, com `<<<`/`>>>` removidos do conteúdo. Mantenha a regra 9 nos dois
  prompts (`prompt_loop.md` e `.en.md`); `tests/test_prompt_cond.sh` confere.
