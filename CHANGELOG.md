# Changelog — OportunizaVaga

All notable changes to this project will be documented in this file.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

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
