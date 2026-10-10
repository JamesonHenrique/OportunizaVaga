# OPERAÇÃO — triagem, cascata de modelos, vigia e canário

Componentes determinísticos (sem LLM) que gastam menos tokens e avisam quando algo quebra.
Tudo é portável (Python + `.sh`/`.ps1`) e **fail-open**: se um deles falhar, a rodada segue como antes.

## Triagem pela descrição (`bot/vaga_check.py`)

Decide o óbvio **antes** do modelo abrir a vaga: nível, anos exigidos, modelo de trabalho e stack, a partir do texto do
anúncio e do "Nível de experiência" oficial do LinkedIn. É **conservador**: só rejeita com evidência clara; na dúvida
diz `COMPATIVEL` e o modelo decide.

```bash
python3 bot/vaga_check.py checar /tmp/anuncio.txt "Título da vaga" "Júnior"   # COMPATIVEL | INCOMPATIVEL: motivo
```

Tudo vem do **perfil** (`perfil.json`) e do `descoberta.json` opcional (exemplo em `config/descoberta.example.json`):

| Regra | De onde vem |
|---|---|
| níveis aceitos/recusados (palavras do papel: "desenvolvedor sênior", "vaga pleno") | `niveis` do perfil |
| nível oficial do LinkedIn vence o título; título sem palavra de nível só reprova em perfis de entrada (estágio/trainee/júnior) | `niveis` |
| anos exigidos (`4+ years of full-stack experience`, `experiência mínima de 3 anos`); número ≥ 10 é idade da empresa e é ignorado | `experiencia_max_anos` (`null` = sem teto) |
| presencial/híbrido explícitos, salvo se a descrição também disser "remoto" | `modelos` |
| 2+ tecnologias de fora e nenhuma do perfil | `stack_evitar` / `stack_preferida` (vazias = regra desligada) |

Uso na descoberta (`OV_DESCOBRIR=1`): cada vaga da fila passa pela triagem. LinkedIn: página pública
`jobs-guest/jobs/api/jobPosting/<id>` (descrição + nível oficial), no máximo `max_descricoes` (padrão 12, `0` desliga)
por coleta, com pausa entre requisições; Gupy: a descrição já vem na lista. Falha de rede/parse **nunca filtra**. A vaga
aprovada aparece no prompt com a marca `[descrição ok]`, e o passo **c0** do prompt manda o modelo rodar o mesmo
`vaga_check.py` nas demais vagas, antes de gerar CV. Rejeitadas entram na fila como `filtrada` com motivo `desc:...`.
Teste: `tests/test_vaga_check.sh` (os 10 casos de referência, perfil, CLI, descoberta offline).

## Cascata adaptativa de modelos (`bot/modelos-saude.py`)

A ordem da cascata em `loop.sh`/`loop.ps1` é escrita à mão, mas modelos gratuitos variam muito: na operação privada do
mantenedor (8 dias), um modelo teve 1 sucesso em 54 sessões improdutivas enquanto outro teve 57 sucessos e 0 falhas.
O script lê os `loop.log*` dos últimos 7 dias e conta, por modelo, `rodada usou o modelo X` (sucesso) contra
`no limite` / `encerrou sem navegar` / `quebrou o formato de tool-call` / `morreu apos erro` (falha):

- ordena por nota suavizada `(sucessos + 1) / (tentativas + 2)` (modelo novo começa em 0,5; empate mantém a ordem original);
- **quarentena de 7 dias** para modelo com 0 sucessos em ≥ 10 tentativas, nunca deixando menos de `MIN_ATIVOS` (2) modelos;
- recalcula no máximo a cada 6 h; **fail-open**: qualquer erro devolve a ordem original.

```bash
python3 bot/modelos-saude.py relatorio              # tabela por modelo (usou / limite / improdutiva / erro / nota)
python3 bot/modelos-saude.py ordenar M1 M2 M3      # cascata resultante, um modelo por linha
```

Estado em `<STATE_DIR>/modelos_saude.json` (`MODELOS_SAUDE_FILE` sobrescreve; `MODELOS_SAUDE_LOGS` troca o glob dos logs,
útil em testes). Desligue com `OV_MODELOS_SAUDE=0`. O modelo pago opcional (`OV_MODELO_PAGO`) continua na frente e fora
da ordenação. Teste: `tests/test_modelos_saude.sh`.

## Config enxuta do opencode (`bot/opencode-enxuto.py`)

Cada chamada do opencode envia o schema de **todas** as ferramentas de MCP e as nativas. O robô usa um MCP de browser e
poucas nativas; o resto é custo puro em toda chamada (~9 por sessão). O script monta um `OPENCODE_CONFIG_CONTENT` que o
opencode mescla sobre a sua config:

- os **outros** MCPs da sua config são desligados (`{"enabled": false}`; nenhuma URL/header é copiado);
- o MCP de browser (`OV_BROWSER_MCP`, padrão `playwright-chrome-real`) fica com o `command` **lido da sua config**, sem a
  capacidade `vision` (`--caps vision`: as ferramentas por coordenada nunca foram chamadas nas rodadas do mantenedor);
- ferramentas nativas que o robô não usa ficam negadas: `edit`, `glob`, `grep`, `websearch`, `task`, `todowrite` e o
  `browser_close` do MCP (`OV_ENXUTO_NEGAR="a,b"` troca a lista). `write` e `webfetch` continuam. O agente ainda pode
  usar grep/edição via bash; sai só o schema das ferramentas dedicadas.

**Medição privada:** no ambiente do mantenedor (conjunto de MCPs dele, mesmo modelo, prompt de uma linha) o contexto da
primeira chamada caiu de 15.346 para 11.051 tokens (**-28% por chamada**). É uma medição privada, não uma garantia:
o ganho no seu ambiente depende de quais MCPs você tem configurados.

Precedência em `loop.sh`/`loop.ps1`: `OV_OPENCODE_CONFIG_CONTENT` explícito > este script > nada. O `followup.sh`/`.ps1`
usa a mesma ordem (o `.sh` cai na config fixa antiga se o script não gerar nada). **Fail-open**: config não encontrada,
MCP de browser ausente ou JSONC inválido = saída vazia e o robô segue com a config do opencode intacta.
`OV_OPENCODE_ENXUTO=1` liga (desligado por padrão: nega ferramentas embutidas). Arquivo lido: `OV_OPENCODE_USER_CONFIG`, `OPENCODE_CONFIG` ou
`~/.config/opencode/opencode.jsonc|json`. Teste: `tests/test_opencode_enxuto.sh`.

## Bloco do Telegram só enquanto há vaga nova

A colheita do Telegram roda algumas vezes por dia, mas quase nenhuma vaga colhida vira candidatura; um bloco fixo no
prompt custa tokens em toda rodada. `<!--se:telegram-->` (em `bot/prompt_cond.py`, usado por `loop.sh` e `loop.ps1`)
agora só é mantido enquanto a colheita está fresca (< 6 h) **e** alguma vaga colhida foi oferecida menos de 2 vezes.
O contador vive em `<estado>/telegram_oferecidas.json` (chave `id` ou `post`, últimas 500), incrementa uma vez por prompt
renderizado com o bloco e `telegram_fresco()` não tem efeito colateral. Erro de leitura = sem bloco. O texto das vagas
que `tg-garimpo.py prompt` acrescenta continua com o próprio limite por vaga (`max_ofertas`). Teste:
`tests/test_prompt_cond.sh`.

## Cobertura ATS gravada automaticamente

Antes, o campo `ats` de uma candidatura só existia se o modelo lembrasse de anotá-lo (na operação privada, 1 de 42),
então ninguém sabia se o CV por vaga compensa. Agora `estado.py add-aplicada` mede sozinho: se o registro traz `cv` com um
`CV_*.pdf` existente e o anúncio salvo no passo c1 (`ANUNCIO_FILE`, padrão `<tmp>/anuncio.txt`) foi escrito há menos de
20 minutos (para nunca usar o texto de outra vaga), roda `bot/check_ats.py` e grava
`"ats": {"geral": <%>, "perfil": <%|null>}`. Best effort: qualquer falha deixa o registro como veio. `OV_CHECK_ATS`
troca o script (testes). Teste: `tests/test_estado.sh`.

## Vigia de vida / dead man's switch (`bot/vigia-vida.sh`, `bot/vigia-vida.ps1`)

Cron (ou Task Scheduler) a cada 15 min. Manda um alerta por `scripts/notificar.sh`/`.ps1` (Telegram, com dedupe de 6 h) quando:

1. o loop **não** está rodando em 2 checagens seguidas (uma falta é normal: o `guardiao` religa);
2. o heartbeat do monitor (`$MONITOR_URL/api/status?ping=1`, campo `updatedAt`) tem mais de `HB_MAX_MIN` (padrão 20) minutos,
   está ausente ou o servidor não responde. **`MONITOR_URL` é opcional e não tem padrão**: vazio (ou um placeholder
   `sua-url`/`example.invalid`) pula esta checagem, então quem não usa o painel não recebe alarme falso;
3. o `aplicadas.json` do perfil ativo (ou o mais recente de `bot/state/*/`) está ausente ou não é JSON válido.

Por que não olhar só o log: o loop dorme de 1 h a 4 h legitimamente quando não há vaga nova, então "log parado" gera
alarme falso o tempo todo; o vigia olha o **processo**. Limite: roda na própria máquina, então PC desligado não avisa
(para isso é preciso um pinger externo no `/api/status`). Variáveis: `HB_MAX_MIN`, `VIGIA_INTERVALO_MIN` (só a mensagem),
`NOTIFY`/`VIGIA_NOTIFY` (notificador), `VIGIA_STATE`, `VIGIA_LOOP_PATTERN` (testes). Sai com 2 quando alertou.
Teste: `tests/test_vigia_vida.sh`. O `.ps1` não tem teste automatizado (ver `docs/TESTES.md`).

## Canário dos parsers de portal (`bot/canario-fontes.py`)

`descobrir.py` lê páginas públicas cujo markup os portais mudam sem aviso; sem alarme, um parser quebrado vira "0 vagas
novas" para sempre. O canário roda 1x/dia, **ao vivo**, o primeiro termo do perfil em cada fonte habilitada em
`descoberta.json` (`fontes`) e checa o contrato: busca do LinkedIn com `id`/`titulo`/`url`; página da vaga com descrição
**e** nível de experiência oficial; API da Gupy com vagas e descrição. Falhou = mensagem `[CANARIO] ...` no Telegram
(`scripts/notificar.sh`; no Windows `notificar.ps1`) e exit 2.

As fixtures de `tests/fixtures/` (`linkedin_search.html`, `linkedin_vaga.html`, `gupy_busca_desc.html`) são **sintéticas**:
fixam o markup que o projeto *assume*, então testes verdes offline não provam que o portal ainda o serve; só o canário
detecta a mudança. Ao atualizar um parser, atualize a fixture junto. Teste: `tests/test_canario_fontes.sh`.

**Aviso imediato (`bot/descobrir.py`, `avisar_fontes`):** a cada coleta, se todas as buscas de uma fonte
derem erro ou 0 vagas, o notificador avisa na hora (sem esperar o canário); quando a fonte volta, avisa uma
vez. Fontes caídas ficam em `fontes_quebradas` na fila. Teste: `tests/test_descobrir.sh` (caso 8).


## Kit de entrevista e funil por fonte (`bot/kit-entrevista.py`, `bot/funil-fontes.py`)

`kit-entrevista.py` (sugestão de cron: `*/30 7-22 * * *`): para cada candidatura em teste/entrevista/próxima
etapa ainda não marcada como feita (`acao_feita_em`/`teste_feito_em`), manda pelo notificador um kit por mudança
de status (vaga, link, como foi enviada, CV, data do convite quando o assunto do Gmail traz) e um lembrete no dia
do evento. Marca `kit_status`, `evento_em` e `lembrete_em` via `estado.py set-campo`, então nada repete.
Caminhos por env: `APLICADAS_FILE`, `OV_GMAIL_STATUS`, `NOTIFY`, `OV_ESTADO_PY`; texto do "feito": `OV_KIT_FEITO`.

`funil-fontes.py [APLICADAS] [--curto]`: envio → retorno → avanço por fonte e por `caminho` (fila × rodízio),
mais "sem resposta há >21 dias" calculado na hora (o status nunca é rebaixado). Teste: `tests/test_kit_funil.sh`.

## Backups e restauração (`scripts/backup-jsons.sh`, `scripts/restore-json.py`)

`backup-jsons.sh` (ou `.ps1`) copia `aplicadas.json` e `dados_candidato.json` — da raiz e de cada
`bot/state/<perfil>/` — para `bot/backups/<prefixo>.AAAAMMDD-HHMM.json`, mantendo as 14 cópias mais
recentes **por prefixo**. Uma origem que não é JSON válido é pulada (exit 1) e não gira a rotação,
para que um arquivo corrompido não empurre as cópias boas para fora.

```bash
python3 scripts/restore-json.py --listar        # backups, validade e destino de cada um
python3 scripts/restore-json.py --verificar     # exit 1 se algum backup estiver inválido
python3 scripts/restore-json.py bot/backups/aplicadas.AAAAMMDD-HHMM.json            # simulação
python3 scripts/restore-json.py bot/backups/aplicadas.AAAAMMDD-HHMM.json --aplicar  # restaura
```

- Sem `--aplicar` nada é alterado: o comando mostra destino, contagens e quantas aplicadas do
  arquivo atual **não** existem no backup (seriam esquecidas e poderiam ser reenviadas).
- Backup com JSON inválido ou sem a lista `aplicadas` é recusado.
- Antes de substituir, o arquivo atual vai para `bot/backups/<prefixo>.pre-restore.<carimbo>.json`
  (fora da rotação). A escrita usa a mesma trava + troca atômica do `bot/estado.py`.
- Pare o loop (e o guardião/cron que o religa) antes: uma rodada em andamento pode regravar o estado antigo.
- Os backups ficam no mesmo disco e contêm `dados_candidato.json` (dados pessoais); `bot/backups/`
  já está no `.gitignore`. Cópia fora da máquina fica a cargo do usuário.

## Envio com resultado desconhecido (`estado.py intencao`)

Uma candidatura passa por três estados no `aplicadas.json`:

| Estado | Onde fica | Quem grava |
|---|---|---|
| intenção (resultado desconhecido) | `envios_pendentes[CHAVE]` | `estado.py intencao`, logo antes do clique final |
| enviada (confirmada) | `aplicadas[]` | `estado.py add-aplicada` (remove a intenção) |
| não enviada (comprovado) | `envios_cancelados[]` (últimas 100) | `estado.py cancelar-intencao CHAVE MOTIVO` |

Se o processo morre entre o clique e o `add-aplicada` (timeout, watchdog, queda do Chrome ou da
máquina), a intenção sobra. Resultado desconhecido **não** é tratado como falha: a próxima
tentativa — outro modelo da cascata na mesma rodada (`OV_TENTATIVA`) ou a rodada seguinte — recebe
exit 1 de `intencao` para essa chave e a vê no topo do `resumo` e do `ja-visto`. O modelo deve
verificar no portal ou no e-mail e só então registrar `add-aplicada` ou `cancelar-intencao`.
`scripts/validate-rodada.py` imprime `[aviso]` enquanto houver pendentes, e o monitor recebe só a
contagem (`telemetry.totals.enviosPendentes`).

Limitações: a proteção depende de o modelo chamar `intencao` antes do clique (está no passo d0 do
prompt). Uma rodada que pula esse passo volta ao comportamento antigo. No `loop.ps1` não há
`OV_RODADA`/`OV_TENTATIVA`, então toda intenção já existente é tratada como de outra tentativa:
a trava continua segura, só perde a idempotência dentro da mesma tentativa.
