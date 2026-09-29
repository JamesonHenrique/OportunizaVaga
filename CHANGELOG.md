# Changelog — OportunizaVaga

All notable changes to this project will be documented in this file.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Added
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
