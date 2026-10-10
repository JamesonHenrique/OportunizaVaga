# Changelog — OportunizaVaga

All notable changes to this project will be documented in this file.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Added
- **Adesão ao passo d0 mensurável**: `add-aplicada` do robô sem intenção grava `sem_intencao` (e avisa o modelo);
  com intenção grava `intencao_em`; `doctor` seção 7 conta as duas. `tests/test_estado.sh` (30).
- **`doctor` seção 7 (`scripts/doctor-estado.py`, usado por `doctor.sh` e `doctor.ps1`)**: perfil legível, cada estado
  (raiz e `bot/state/*`), envios com resultado desconhecido, inconsistências do `validate-rodada`, idade e validade dos
  backups, última rodada e contagem de ERRO/ALERTA no `loop.log` — só nomes de perfil, contagens e idades (sem dado
  pessoal). Exit 1 só para perfil/estado ilegível. `tests/test_doctor_estado.sh` (6).
- **`eventos.jsonl`**: cada escrita do `estado.py` vira uma linha (`em`, `rodada`, `tentativa`, `cmd`, `chave`,
  `de`/`para`), sem texto livre; recusas e leituras não contam; gira em 2 MB. `docs/OPERACAO.md`.
- **Intenção de envio (`bot/estado.py intencao` / `cancelar-intencao`)**: gravada logo antes do clique final (passo d0
  do prompt) em `envios_pendentes`. Se o processo morre entre o clique e o `add-aplicada`, o próximo modelo da cascata
  (`OV_TENTATIVA`) ou a próxima rodada recebe exit 1 e vê o envio no topo do `resumo`/`ja-visto` como resultado
  desconhecido — verificar antes de reenviar. `validate-rodada.py` avisa; o monitor recebe só a contagem
  (`telemetry.totals.enviosPendentes`). `tests/test_estado.sh` (28). Ver `docs/OPERACAO.md`.
- **`scripts/restore-json.py`**: `--listar`, `--verificar` e restauração com simulação por padrão; recusa backup
  inválido, avisa aplicadas que seriam esquecidas e guarda o atual como `pre-restore` antes de trocar
  (trava + escrita atômica). `tests/test_backup.sh` (10).

### Fixed
- **`bot/guardiao.sh` matava às cegas quem segurava o lock (`fuser -k`)**: agora só `sleep` órfão ou processo além de
  `OV_GUARDIAO_ORFAO_S` (1500 s); órfão ainda trabalhando adia a subida do loop. `tests/test_guardiao.sh` (3).
- **Alertas (`scripts/notificar.sh`/`.ps1`)**: a deduplicação usava o hash exato, então o mesmo alerta com outra hora ou
  contagem saía a cada rodada; agora números são ignorados na chave (janela `OV_NOTIFY_JANELA_S`, padrão 6h) e envio
  recusado pela API (`curl -f`) não é marcado como enviado. `tests/test_notificar.sh` (4).
- **Telegram (`bot/tg-garimpo.py`)**: deduplicava pelo link cru (mesma vaga com outro `?utm=` voltava) e conferia
  "já registrada" por substring do arquivo (`/vaga/1` casava `/vaga/12`). `url_canon` foi para `vagas_filtros.py`
  (uma regra para `descobrir` e `tg-garimpo`) e o Telegram compara URL canônica / e-mail exato.
- **Monitor publicava dados congelados (`monitor/snapshot.mjs`)**: estado, log e "hoje" eram lidos ao importar o
  módulo; o daemon `publish-status.mjs` reenviava esses dados com `updatedAt` novo e o vigia nunca via o monitor
  parado. Agora tudo é lido dentro de `buildSnapshot()` (teste de regressão no mesmo processo).
- **Backup (`scripts/backup-jsons.sh`/`.ps1`)**: origem com JSON inválido é pulada (exit 1) em vez de entrar na
  rotação e empurrar as cópias boas; a rotação da raiz (`aplicadas.*`) apagava os backups dos perfis
  (`aplicadas.perfil-*`) — agora o glob exige o carimbo numérico.
- **Deduplicação (`bot/descobrir.py`)**: `url_canon` descartava parâmetros fora de 5 nomes, então
  `detalhe?codigo=55` e `?codigo=56` viravam a mesma chave e a segunda vaga sumia; agora só parâmetros de
  rastreio (`utm_*`, `ref`, `trk`...) saem. `ja_registrada` comparava só a 1ª palavra da empresa como substring
  ("SAP" casava "sapiens", todo "Banco ..." colidia) e ignorava o nível; agora exige todas as palavras da empresa e
  nível explícito diferente = vaga diferente. `tests/test_descobrir.sh`.
- **Perfil corrompido virava júnior/remoto em silêncio**: `perfil_render.carregar` e `vagas_filtros` caíam nos padrões;
  no `loop.sh`, o nome vazio levava a um estado novo e vazio (histórico sumia, vagas já enviadas voltavam). Agora o
  loop para com `ERRO: perfil invalido` e os scripts saem com mensagem clara. Estado novo criado quando já existe
  histórico de outro perfil deixa `AVISO` no `loop.log`.
- **Filtro de anos (`bot/vaga_check.py`)**: "Mínimo 5 anos em Java", "pelo menos 4 anos com", "at least 3 years" e
  "N anos atuando com" passavam pelo teto de experiência.
- **`bot/check_ats.py`**: "java" era coberto por "javascript" (substring) — agora palavra inteira; perfil ausente ou
  corrompido dava "OK" (agora exit 2, não verificável); anúncio sem nenhum termo do perfil dava "OK" (agora
  reprovado como desalinhado). `tests/test_check_ats.py`.
- **`tests/test_estado.sh`**: um `if` fora do lugar deixava os testes 21–23 dentro da condição final.

- **CV levava nota interna ao recrutador (`bot/gerar_cv.py`)**: a frase de transferência (feita para formulário) e a
  linha "Termos do anúncio correspondidos", com os rótulos internos das stacks similares ("sem afirmar domínio"), eram
  impressas logo após o resumo. Saíram; `resumo_custom` com nota interna é recusado (exit 2) e a autochecagem
  reprova o PDF que contiver uma. O resumo ganhou título de seção (o ATS acha a seção pelo heading), o headline
  aceita `titulo_alvo` (cargo da vaga, só dev/analista e nunca pleno/sênior) e o PDF leva assunto e palavras-chave
  nos metadados. `prompt_cv.md`/`.en.md`: `frase_key` → `titulo_alvo` e regra do resumo.
- **Híbrida de qualquer cidade entrava como remota (`bot/descobrir.py`)**: com `hibrido` em `modelos`, a busca do Gupy
  deixa de filtrar `workplaceType=remote`, mas `parse_gupy` gravava `local="remoto"` em toda vaga. Agora o local vem de
  `workplaceType`/`city`/`state`; híbrida/presencial fora de `cidades` do perfil vira `modelo`, e os filtros de card
  com cidade (LinkedIn, boards) valem fora das cidades do perfil. `tests/test_descobrir.sh` (19).
- **Gupy sem filtro com perfil remoto + híbrido (`bot/descobrir.py gupy_buscas`)**: a busca baixava o país inteiro
  (maioria presencial) e estourava o tempo (`gupy:prazo`). Agora: uma busca `workplaceType=remote` + uma
  `workplaceType=hybrid` por lugar de `cidades` (`state=` para nome de estado, `city=` para o resto), sem duplicar vaga.
- **Coleta intercala LinkedIn e Gupy (`coletar`)**: com o LinkedIn em 8 termos × 8 páginas, o prazo `tempo_max_s` cortava
  as buscas do Gupy, que vinham todas no fim. Agora o prazo corta as duas fontes por igual.
- **Fila do descobridor perdia vaga nova (`bot/vagas_filtros.py salvar_fila`)**: `descobrir.py` lia a fila, trabalhava
  minutos e gravava por cima — vaga que o `tg-garimpo` ou outra coleta anexou nesse meio-tempo sumia. Agora grava com
  mescla de 3 vias (`mesclar(base, meu, atual)`) sob `jsonlock`. Teste em `tests/test_descobrir.sh`.
- **Clique em aba oculta (`bot/cdp.py`)**: `Chrome.clicar` traz a aba para frente (`Page.bringToFront`) antes do
  clique sintético; com a aba em segundo plano o botão "Entrar com Google" do Gupy ignorava o clique. `tests/test_cdp.py`.
- **`bot/gmail-status.py`** avisa quando a busca enche a 1ª página (50 conversas): e-mails mais antigos não são lidos.
- **`bot/gupy-status.py`** grava pelo `estado.py` dono do `aplicadas.json` (`OV_ESTADO_PY`, padrão `bot/estado.py`) e usa
  o `ORDEM` dele (antes faltavam `respondida`/`followup`); `OV_GUPY_STATUS_FILE` escolhe onde fica o resumo.
- **`is_quota` voltou a `bot/lib/opencode-erros.sh`**: o `loop.sh` chamava uma função que não existia (rc 127 lido como
  "não é cota"). O teste confere que toda função da lib chamada pelo `loop.sh` existe.
- **`bot/modelos-saude.py`**: quarentena possível com cascata de 2 modelos (`MODELOS_SAUDE_MIN_ATIVOS`, padrão 1) e
  todos os padrões de falha da lib de erros contam. Teste em `tests/test_modelos_saude.sh`.
- **Contagem de site's `bot/rodizio-saude.py`**: `pos` creditava ao site da rodada **toda** candidatura
  anexada durante ela, inclusive as que saíram pela fila em outro canal (Gupy/Inhire/Telegram). Um site de
  exploração chegou a `4 aplicadas` sem nenhuma candidatura registrada nele, e esse número falso entrava na
  promoção D1 e na reordenação por rendimento. Agora a atribuição usa a regra `de_site()` — o `como` da
  candidatura precisa nomear o site —, a mesma que `nota_site()` já usava, para contador e nota nunca
  divergirem. Teste 11 em `tests/test_rodizio_saude.sh`.
- **Promoção D1 morta (`bot/rodizio-saude.py pos-so-fila`)**: `ultima_aplicada` só era carimbada no caminho
  `pos`, mas a maioria das candidaturas chega pela fila (caminho `pos-so-fila`), então um site de exploração
  dificilmente era promovido. `pos-so-fila` agora carimba `ultima_aplicada` no site que o `como` nomeia, sem
  tocar em streak (`rodadas`) nem avançar o rodízio — a rodada não varreu site nenhum. Teste 11.
- **Fila do descobridor (`bot/descobrir.py marcar LOG`)**: a oferta só conta quando o id da vaga aparece no log da
  rodada (vaga que o modelo nem abriu não perde a chance; teto `max_mostrada`=6); vaga que o modelo descartou só no
  texto (`DESCARTADA`) vira `bloqueados` e não volta toda rodada; mesma empresa + título entra como `duplicada`.
  `loop.sh`/`loop.ps1` passam o log. Teste 7 em `tests/test_descobrir.sh`.
- **`estado.py descartes`** aceita rótulos (`nivel 1 modelo 2 stack 3`) e recusa o placeholder copiado sem traceback;
  `add-aplicada` sem status grava `enviada`. Testes 21–22 em `tests/test_estado.sh`.
- **`.playwright-mcp/`** (snapshots de página, alguns com formulário preenchido) é podado a 2 dias pelo `loop.sh`
  (ainda não no `loop.ps1`).
- **Cota x erro transitório do provedor (`bot/lib/opencode-erros.sh`)**: qualquer `AI_APICallError` contava como
  cota, então um 503 "Service Unavailable" ou timeout de cabeçalho punha o melhor modelo em resfriamento e a rodada
  caía para modelos piores. Agora só 429/rate limit/quota é cota; 5xx/timeout/sobrecarga é transitório. O vigia da
  rodada aborta em qualquer erro do provedor com saída parada. Teste: `tests/test_opencode_erros.sh`.

- **Registro retroativo** (candidatura feita fora do robô, sem data de envio conhecida) não quebra mais o
  `scripts/validate-rodada.py` nem conta como envio recente no `rodizio-saude.py`.
- **Follow-up** pula candidaturas `encerrada` e pula o Gupy enquanto `gupy_status.json` tiver < 36h; sessão
  improdutiva conta como falha do modelo na cascata.

### Added
- **De onde veio cada envio (`descoberta`)**: `descobrir.py marcar` carimba `descoberta=<fonte>:<termo>` (termo do
  LinkedIn/Gupy, canal do Telegram, board) ou `rodizio:<site>` em cada candidatura da rodada; `funil-fontes.py` mostra o
  funil por termo/canal/site — base para podar termos e canais com dado, não no escuro. Testes `test_descobrir.sh`,
  `test_kit_funil.sh`.
- **`embargo_dias` (`config/descoberta.json`)**: `{fonte: N}` segura na fila, ainda `nova`, a vaga de fonte com paywall
  nos primeiros N dias após `publicada` (ex.: eu.dev.br esconde empresa e link por 48 h). Vaga sem data não espera.
- **Portão da rodada (`bot/rodada-portao.py`, opt-in `OV_PORTAO=1`)**: decide sem LLM se a rodada vale uma sessão de
  modelo — `completa` (site do rodízio vencido por `rodizio_intervalo_h`), `so_fila` (só fila/rechecagens, sem varrer
  site) ou `pular`. Site bloqueado (403/Cloudflare) é sondado por `bot/sonda-sites.py` e sai do rodízio por 12h.
  Teste: `tests/test_portao.sh`.
- **Status do Gupy por script (`bot/gupy-status.py`)**: lê "Minhas candidaturas" via CDP (`bot/cdp.py`, precisa de
  `websocket-client`) e atualiza os status sem LLM; candidatura feita à mão vira `registro_retroativo`. Casamento 1-1
  (id da vaga vence, empate fica ambíguo). Exemplo em `config/crontab.example`. Teste: `tests/test_gupy_status.sh`.
- **Relógio da rodada (`bot/tempo-rodada.py`)**: o modelo pergunta antes de abrir vaga nova; evita candidatura pela
  metade quando o timeout mata a rodada.
- **`estado.py`**: `resumo-candidato` e `dado CAMPO` (o prompt recebe um resumo em vez de ler o JSON inteiro),
  `del-aplicada` (move para `aplicadas_removidas`), validação de `status`, uso do comando impresso no erro.

- **Canário dos parsers de portal (`bot/canario-fontes.py`)**: 1x/dia roda a busca do LinkedIn/Gupy ao vivo (só as `fontes`
  habilitadas) e avisa no Telegram, com exit 2, se algum parser não devolver dados usáveis (busca vazia, página de vaga sem
  descrição ou sem nível oficial, Gupy sem descrição). Contrato offline com fixtures **sintéticas** em
  `tests/test_canario_fontes.sh` (`tests/fixtures/linkedin_vaga.html`, `gupy_busca_desc.json`). Exemplos em
  `config/crontab.example` e `config/TaskScheduler.md`.
- **Dead man's switch (`bot/vigia-vida.sh` / `bot/vigia-vida.ps1`)**: a cada 15 min avisa no Telegram se o loop não estiver
  rodando em 2 checagens seguidas, se o heartbeat do monitor (`MONITOR_URL/api/status?ping=1`) tiver mais de `HB_MAX_MIN`
  minutos (`MONITOR_URL` opcional e sem padrão: sem ele a checagem é pulada) ou se o `aplicadas.json` estiver ausente/ilegível.
  Exemplos em `config/crontab.example` e `config/TaskScheduler.md`. Teste: `tests/test_vigia_vida.sh`.
- **Cobertura ATS gravada sozinha** em `estado.py add-aplicada`: com `cv` = `CV_*.pdf` existente e anúncio (`ANUNCIO_FILE`)
  salvo há < 20 min, roda `check_ats.py` e grava `ats: {geral, perfil}` (campo novo no `aplicadas.schema.json`).
- **Bloco do Telegram só enquanto há vaga colhida ainda não oferecida** (`bot/prompt_cond.py`): `<!--se:telegram-->` exige
  colheita fresca **e** ao menos uma vaga oferecida < 2 vezes (`<estado>/telegram_oferecidas.json`, contado uma vez por prompt
  renderizado em `loop.sh`/`loop.ps1`). Testes em `tests/test_prompt_cond.sh`.
- **Config enxuta do opencode (`bot/opencode-enxuto.py`)**: monta o `OPENCODE_CONFIG_CONTENT` a partir da sua própria config
  (desliga os outros MCPs, tira `--caps vision` do MCP de browser, nega `edit/glob/grep/websearch/task/todowrite`, mantém
  `write`/`webfetch`), usada por `loop` e `followup` (`.sh` e `.ps1`); fail-open, `OV_OPENCODE_ENXUTO=1` liga (desligado por padrão: nega ferramentas embutidas) e
  `OV_OPENCODE_CONFIG_CONTENT` continua mandando. Medição privada do mantenedor: -28% de contexto por chamada
  (15.346 -> 11.051 tokens). Teste: `tests/test_opencode_enxuto.sh`.
- **Cascata de modelos adaptativa (`bot/modelos-saude.py`)**: ordena a cascata pela taxa de sucesso real dos últimos 7 dias de
  `loop.log*`, põe em quarentena (7 dias) modelo com 0 sucessos em ≥ 10 tentativas (nunca abaixo de 2 ativos), recalcula a
  cada 6 h e é fail-open. Ligado em `loop.sh` e `loop.ps1` (`OV_MODELOS_SAUDE=0` desliga; `MODELOS_SAUDE_FILE` sobrescreve o
  estado). Teste: `tests/test_modelos_saude.sh`.
- **Triagem pela descrição (`bot/vaga_check.py`)**: decide nível, anos exigidos (pt/en, hifenizado, idade da empresa ≥ 10
  ignorada), modelo e stack a partir do texto e do "Nível de experiência" oficial do LinkedIn, dirigida pelo perfil e por
  `descoberta.json` (`stack_evitar`/`stack_preferida`, nada de stack fixa no código). `bot/descobrir.py` a usa em cada vaga da
  fila (`linkedin_detalhe`, descrição da lista da Gupy, `max_descricoes` por coleta, fail-open, marca `[descrição ok]`) e os
  prompts (pt/en) ganham o passo **c0**. Teste: `tests/test_vaga_check.sh`. Ver `docs/OPERACAO.md`.
- **`scripts/ctl.sh` / `scripts/ctl.ps1`**: `status` (motor, prompt, estado, Chrome, logs em ~20 linhas), `rodada` (final da
  última rodada) e `chrome` (quem usou o Chrome), só leitura e baratos em tokens. Teste: `tests/test_ctl.sh`.
- **Rodízio reordenado 1x/dia pelo rendimento** (`bot/rodizio-saude.py`): mesma quantidade de vagas de rodada, ≥ 1 por site,
  o resto proporcional a uma nota suavizada (candidaturas por rodada + respostas positivas), intercalado por round-robin
  ponderado suave (sem repetir site em sequência quando dá); guarda `rodizio.ordem_calculada_em`. Desliga com
  `OV_RODIZIO_REORDENAR=0`. Testes determinísticos em `tests/test_rodizio_saude.sh`.
- **`bot/podar-sessoes.py`** (opt-in): apaga as sessões antigas do robô no opencode (banco com argumentos de tool-calls) via
  `opencode session list --format json` / `session delete`; filtra por prefixo de título **e** pasta, idade por `created`,
  `--dry`, banco em `chmod 600`. Documentado em `docs/SEGURANCA.md`, cron e Task Scheduler. Teste: `tests/test_podar_sessoes.sh`.
- **`bot/redact-logs.py`**: mascara segredos nos logs (senhas do `credenciais.tsv`, campos de senha de tool-calls,
  `printf … >> credenciais`, tokens de API/bot, CPF, códigos de 6 dígitos; `.gz`), portável, globs e arquivo de
  credenciais configuráveis (`OV_REDACT_GLOBS`, `OV_CREDENTIALS_FILE`). Pula arquivo escrito há < 30 min salvo `--forcar`;
  `loop.sh`/`loop.ps1` limpam o log de cada rodada ao fim dela. Exemplos de cron/Task Scheduler. Teste: `tests/test_redact_logs.sh`.
- **`bot/chrome-lock.sh` / `bot/chrome-lock.ps1`**: protocolo único do Chrome compartilhado (`NOME alta|normal ESPERA -- CMD`):
  jobs curtos (follow-up, Gmail) marcam prioridade por flag e o loop cede a rodada (`CHROME_LOCK_YIELD_RC`); flag do job pai
  não é removida; log em `bot/logs/chrome-lock.log`. Usado por `loop.sh/.ps1`, `followup.sh/.ps1` e `gmail-status.py`.
  Teste: `tests/test_chrome_lock.sh` (rodar/ceder/timeout).
- **Prompt modular e defesa contra injeção indireta** (`bot/prompt_cond.py`, usado por `loop.sh` e `loop.ps1`):
  blocos `<!--se:site=X-->…<!--/se-->` (só a URL do site da rodada) e `<!--se:telegram-->` (só com colheita fresca),
  fail-open para condição/site desconhecido; linha `SITE DESTA RODADA`; fila da descoberta e posts do Telegram entram
  cercados por `<<<DADOS_EXTERNOS …>>>` (delimitadores removidos do conteúdo) e a regra 9 dos prompts (pt/en) manda
  tratar texto de terceiros como dado, nunca instrução. Teste: `tests/test_prompt_cond.sh`.
- **`estado.py ja-visto EMPRESA [TITULO]`** e **`resumo` compacto**: aplicadas como `empresa | vaga`; bloqueadas e
  arquivadas só como nomes de empresa com contagem (o detalhe vem sob demanda). Corta milhares de tokens por prompt;
  regra 2 e recheagem de bloqueados dos prompts (pt/en) usam o `ja-visto`.
- **`bot/jsonlock.py`** (trava exclusiva + tmp único + fsync + `os.replace`, portável fcntl/msvcrt) usada por
  `estado.py` (escritas travadas, leituras não), `rodizio-saude.py` e `arquivar-logs-rodada.py`: gravações
  concorrentes não se perdem mais. Teste de corrida em `tests/test_jsonlock.sh` (30 escritas paralelas = 30).
- **Leitor de respostas no Gmail** (`bot/gmail-status.py` + `bot/gmail-extrair.mjs`): CDP puro, sem dependências,
  aba própria; lê as caixas de `email` e `email_contas` (escolhidas por endereço, `authuser`) e só falha se
  nenhuma abrir. Classifica em encerrada → **etapa de testes / fit cultural** → entrevista → **próxima etapa** →
  em análise, só avança o status, grava a **data do e-mail** (`historico_status[].email_data`) e avisa no Telegram.
  Lock do Chrome portável (Linux/Windows).
- **E-mail de contato × e-mail de contas** (`email_contas`, `regra_emails` em `dados_candidato`): cadastros, OAuth,
  códigos e links de verificação usam a caixa de `email_contas`; o CV e os campos de contato usam `email`.
- **`bot/nova-senha.mjs`**: gera a senha de cadastro, grava em `credenciais.tsv` (`OV_CREDENTIALS_FILE`) e preenche os
  campos via CDP — a senha nunca passa pelo modelo nem pelo log (regra 3 do prompt).
- **Descoberta determinística** (`bot/descobrir.py`, opt-in `OV_DESCOBRIR=1`): fila LinkedIn/Gupy sem LLM,
  filtrada pelo perfil e injetada no prompt; config em `config/descoberta.example.json`.
- **Garimpo do Telegram** (`bot/tg-garimpo.py` + `.sh`/`.ps1`, opcional): canais em `bot/telegram_canais.json`.
- **`scripts/validate-rodada`** (+ `.sh`/`.ps1`) após cada rodada, notificando falha; `scripts/tokens-relatorio.py`.
- **Monitor**: fila "Esperando login" por canal; bloqueios triados por causa (você / robô retenta / descartada)
  com CSV; nome da vaga vira link; painel "Busca por script" e resumo do Gmail (arquivos de estado opcionais);
  rótulos "TESTE / FIT CULTURAL" e "PRÓXIMA ETAPA" separados de "ENTREVISTA", com a data do e-mail; e-mail, CPF e
  telefone mascarados antes de publicar; redesenho de todas as abas; demo com os novos status.
- Testes: `test_gmail_status.sh`, `test_descobrir.sh`, `test_tg_garimpo.sh`, casos novos em `test_estado.sh` e
  `monitor/snapshot.test.mjs`.

### Changed
- **Dieta do prompt** (pt/en): resumo do candidato injetado no render, c1 (CV por vaga) e c-Externo movidos para
  `prompt_cv(.en).md`/`prompt_externo(.en).md` lidos só quando necessários (~24 KB → ~20 KB por chamada); regras 7d
  (relógio), 7e (rascunhos em /tmp) e 7f (site bloqueado). `opencode-enxuto.py` nega 11 tools do Playwright pouco usadas.
- **Cascata** (`loop.sh`/`followup.sh`): começa por `opencode/space-bunny-free`; erro transitório ou rodada travada
  repete o mesmo modelo 1x antes de descer; vigia de travamento (`WATCHDOG_HANG`, 6 min sem saída); timeout que
  registrou progresso conta como ok. Paridade no Windows (`loop.ps1`) só para o resumo do candidato — portão,
  vigia e relógio ainda são só Linux.
- **Loop** (`loop.sh`/`loop.ps1`): teto do backoff de rodada vazia (`OV_VAZIA_MAX`), impressão digital do estado por
  chaves, descarte de modelos que o opencode não lista mais, cascata quando a sessão morre após erro de ferramenta,
  rotação persistente de termos, modelo pago opt-in para rodadas com envio pronto, quota do log do opencode
  filtrada por diretório (Linux).

### Security
- Senhas de cadastro não aparecem mais em comandos de shell nem em `fill_form` (ambos vão para o log da rodada).
- `credenciais.tsv`, `gmail_status.json`, sessões e config do Telegram no `.gitignore`.

- **CV por vaga com gerador e checagem ATS (regra `c1`)**: currículo mestre `bot/cv_base.md`
  (exemplo em `examples/cv_base.example.md`, gitignored) alimenta `bot/gerar_cv.py`, que gera o PDF
  de 1 página com as subseções de `Habilidades técnicas` reordenadas por vaga (`so_categorias` é
  obrigatório), keywords reais em negrito e filtro de keyword fora do perfil (avisa em `kw
  DESCARTADAS`). `bot/check_ats.py` mede a cobertura dos termos do anúncio no CV (meta >= 75%)
  antes do anexo. Auto-checagem no gerador: exit 0 só com 1 página e nome/seções extraíveis.
  Prompts `c1` PT/EN agora exigem o fluxo spec → gerador → checagem; nunca mais HTML/reportlab à mão.
- `scripts/setup.sh`/`setup.ps1` copiam o exemplo do `cv_base` e checam `reportlab`/`pdftotext`.
- **Modelo de trabalho configurável**: `modelos` (`remoto`, `hibrido`, `presencial`) e `cidades` no perfil.
  Placeholders `{{REGRA_MODELO}}`, `{{FILTRO_MODELO}}`, `{{LOCAL_BUSCA}}` e `{{LINKEDIN_WT}}` na regra 1 e nas
  URLs de busca. Padrão continua só remoto. Sites só-remoto (`restrito_a_modelo`) saem do rodízio de quem não aceita remoto.
- Wizard (`setup-wizard.sh`/`.ps1`) gera também o `bot/perfil.json`; `validate` passa a checar esse arquivo.

### Changed
- `bot/perfil.json` entra no `.gitignore` (é a preferência pessoal de cada usuário).
- ROADMAP atualizado (nível/área/modelo feitos; modo triagem = reconhecimento).

### Changed
- README principal agora é em português (`README.md`); inglês foi para `README.en.md`.

### Added
- **Qualquer nível e qualquer área.** O perfil (`bot/perfil.json`) ganha `niveis` (estágio → diretor,
  em qualquer combinação), `area` (texto livre), `experiencia_max_anos` e `sites_pular`.
  `bot/perfil_render.py` preenche os placeholders `{{NIVEIS}}`, `{{NIVEIS_RECUSADOS}}`, `{{AREA}}`,
  `{{TERMOS}}`, `{{PULAR_TIPOS}}`, `{{REGRA_EXPERIENCIA}}` e `{{SITES_PULAR}}` dos prompts
  (`loop.sh`, `loop.ps1`, triagem).
- Perfis de exemplo `senior-techlead`, `pleno-marketing` e `estagio-direito`.
- `config/sites_permitidos.json` -> `restrito_a_area`: perfis fora de tech pulam GeekHunter/Programathor
  no rodízio (`rodizio-saude.py pre --perfil`); o dry-run marca esses sites como pulados.
- `dados_candidato`: `experiencia.stacks_similares`, `aceita_senior`, `aceita_lideranca`.

### Changed
- Regra 3 dos prompts (PT/EN) e da triagem deixa de fixar "só JR/trainee" e a stack Java/Angular:
  nível, área, termos e teto de experiência vêm do perfil ativo. URLs de busca usam os termos do perfil.
- "X anos de experiência" só pode ser afirmado se `experiencia.anos` estiver preenchido.

### Deprecated
- `nivel` (string) no perfil — use `niveis`. `experiencia.stacks_similares_jr` — use `stacks_similares`.
  Os dois seguem funcionando; perfil só com `nivel: "junior"` aceita também trainee, como antes.

## [0.2.0] - 2026-09-26

### Added
- **Painel do monitor** (`monitor/app`, `monitor/components`): faixa de status, destaque do dia com
  gráfico de 14 dias, "Precisa de você", KPIs e abas (Candidaturas, Bloqueios, Robô). Antes a pasta
  só tinha os scripts de coleta e `npm run dev` abria um Next.js vazio.
- `/api/status` com `MONITOR_SECRET` opcional, redação para GET sem segredo, `?ping=1` e limite de 1,5 MB.
  O `?secret=` do navegador vira um cookie `httpOnly` (hash, nunca o secret) e sai da URL.
- **Demo com dados fictícios** (`monitor/demo.mjs`, `MONITOR_DEMO=1`), usada na demo ao vivo
  (https://oportunizavaga-demo.vercel.app), no Docker e no GIF do README (`assets/demo.gif`).
- Leitura local do disco quando nada foi publicado ainda (fora da Vercel), e `porDia` agregado no snapshot.
- CI: job `monitor` com `next build` e checagem da demo.
- Contrato comum de adaptadores (`bot/sites/lib.sh`) com descoberta automática de portais.
- Dry-run global por perfil (`--json`, `--site`, `--profile`, `--reconhecimento`).
- Estado isolado por perfil em `bot/state/<perfil>/aplicadas.json`.
- Modo reconhecimento (`OV_RECONHECIMENTO=1`): pontua vagas sem se candidatar.
- Telemetria agregada e anônima por padrão no monitor (`MONITOR_INCLUDE_DETAILS=0`).
- Schemas `config/perfil.schema.json` e `config/reconhecimento.schema.json`.
- Testes: `monitor/snapshot.test.mjs`, `tests/test_dry_run.sh` e Pester ampliado.
- Espelhos Windows (`loop.ps1`, `dry-run.ps1`, `validate.ps1`) atualizados para perfil e reconhecimento.
- `bot/estado.py`: CLI compacta e atômica sobre `aplicadas.json` (resumo, get, add-aplicada,
  add-bloqueado, set-quase-la, descartes, status, conta, rodizio-avancar) — o agente deixa de
  ler/editar o JSON inteiro na mão; novo campo de estado `quase_la` (vaga só não enviada por falta
  de UM dado, retomada quando o dado passar a existir em `dados_candidato.json`).
- `bot/rodizio-saude.py`: pausa automática (48h) de site sem nenhuma candidatura em 4 rodadas
  seguidas, com hooks `pre`/`pos` no `loop.sh` (e no `loop.ps1`, via python se disponível).
- `bot/arquivar-logs-rodada.py`: arquiva chaves `log_rodada_*` de `aplicadas.json` para
  `logs/rodadas.jsonl` ao fim de cada rodada (idempotente, atômico).
- `bot/loop.sh`: cooldown por modelo (`state/model_cooldown`), detecção de sessão improdutiva
  (modelo que encerra sem navegar / quebra o formato de tool-call) e watchdog de stall mid-rodada.
- `bot/followup.sh`: cascata de modelos gratuitos, watchdog de stall e retentativa semanal
  (`state/followup.ok` — o cron pode rodar todo dia sem duplicar o follow-up).
- `scripts/notificar.sh` (+ `.ps1`): push genérico ao Telegram (`TELEGRAM_BOT_TOKEN`/
  `TELEGRAM_CHAT_ID`) com dedupe de 6h por mensagem.
- `scripts/digest.sh` (+ `.ps1`): alertas de anomalia (nenhuma rodada ok, rodadas vazias seguidas,
  timeouts, sinais de quota) a partir das linhas de hoje do `loop.log`.
- `scripts/backup-jsons.sh` (+ `.ps1`): cópia rotativa (14x) de `aplicadas.json`/`dados_candidato.json`,
  na raiz e em cada perfil (`bot/state/*/`).
- Regras de elegibilidade generalizadas no prompt: tempo de experiência aceito até 3 anos (antes 2),
  regra de formação (vaga que exige graduação completa deixa de ser descarte automático), nova seção
  `c-Externo` (fluxo para ATS sem padrão — redirects normais, senha gerada fora do repo/estado
  publicado) e retentativa de bloqueios cujo motivo referencia regra que já mudou.
- Novos campos de exemplo em `dados_candidato.example.json`: `regra_formacao` e
  `regra_tempo_experiencia` atualizado.
- Testes: `tests/test_estado.sh`, `tests/test_rodizio_saude.sh`.

### Changed
- Monitor em Next 16 / React 19; GitHub Actions `checkout`/`setup-node` v7.
- Modelo preferido da cascata movido para `openrouter/nex-agi/nex-n2.5-pro:free`
  enquanto `muse-spark-1.3` estiver no limite.
- Browser: `--allowed-origins` (allowlist fechada de sites de vaga) trocado por `--blocked-origins`
  (blocklist de agregadores estrangeiros/spam) — candidatura liberada para qualquer ATS/site de
  carreira, desde que a vaga seja BR/PT/remota. `config/sites_permitidos.json` e a regra 7 do
  prompt (+ `.en.md`) atualizados para o novo modelo.
- `bot/followup.sh`/`bot/prompt_followup.md`: passam a usar `bot/estado.py` para gravar status
  (`estado.py status CHAVE ST`) em vez de editar `aplicadas.json` na mão; nova regra de rascunho de
  follow-up de 7 dias (nunca enviado automaticamente).

## [0.1.0] - 2026-09-18
### Added
- (A) Saúde comunitária: SECURITY, CODE_OF_CONDUCT, CONTRIBUTING, templates de issue/PR, FUNDING, CITATION.
- (B) Validação por JSON Schema + dry-run/doctor (sh/ps1) integrados ao setup e ao CI.
- (C) Onboarding global em inglês, instalador one-command, Dockerfile/devcontainer/compose demo.
- (D) Adaptadores de sites, triagem two-tier, digest/funil, perfis de exemplo, prompts EN.
- (E) Qualidade: suites TAP/Pester/node:test, CI com testes nos 2 OS, Dependabot mensal, docs/TESTES.md.
- Renomeação open-source genérica (AplicaBot → OportunizaVaga) + espelhos PowerShell/Task Scheduler.
- Painel monitor opcional (Vercel free, sem banco) + daemons de quota/keepalive.
- Docs: QUICKSTART, ARQUITETURA, CUSTO, SEGURANCA, FAQ, PROMPTS + sanitize.sh.
### Notes / Notas
- Pronto para tag v0.1.0: loop/guardião/follow-up funcionais; tag/release ainda não criadas.
