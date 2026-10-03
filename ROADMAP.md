# Roadmap

Direção pública do OportunizaVaga. Não é promessa de data — é onde ajuda é bem-vinda.
Discussão e sugestões: abra uma issue com o template de _feature request_, ou use as
Discussions do repositório.

## Princípios que não mudam

- **R$ 0** para rodar (modelos free ou locais). Ver [`docs/CUSTO.md`](docs/CUSTO.md).
- **Nunca inventar dado.** Campo vazio vira `bloqueado` (ou `quase_la`, se for só UM dado faltando),
  nunca um chute.
- **Estado durável só em `aplicadas.json`** — nunca na sessão do modelo.
- **Sem servidor**: seu PC + cron. Monitor é opcional e free-tier.

## Agora (v0.x)

- [x] Cascata de modelos free com backoff e rodízio de 1 site/rodada.
- [x] Monitor opcional (dashboard sem banco).
- [x] Scaffold OSS: CI, testes, docs, templates, segurança.
- [x] Contrato de adaptadores de site + template ([`docs/ADAPTERS.md`](docs/ADAPTERS.md)).
- [x] Adaptadores descobertos automaticamente via [`bot/sites/lib.sh`](bot/sites/lib.sh).
- [x] Estado isolado por perfil (`bot/state/<perfil>/aplicadas.json`).
- [x] Dry-run global com `--site`, `--profile` e `--reconhecimento`.
- [x] Modo reconhecimento (`OV_RECONHECIMENTO=1`) sem alterar `aplicadas.json`.
- [x] Telemetria agregada e anônima por padrão no monitor.
- [x] Modo 100% local com Ollama ([`docs/MODELOS.md`](docs/MODELOS.md)).
- [x] Wizard de setup (`scripts/setup-wizard.sh`).
- [x] Pacing configurável + guia de uso ético ([`docs/USO-ETICO.md`](docs/USO-ETICO.md)).
- [x] Blocklist de domínios no browser (`--blocked-origins`) em vez de allowlist fechada — candidatura
      liberada para qualquer ATS/site de carreira BR.
- [x] `bot/estado.py`: CLI atômica de leitura/escrita sobre `aplicadas.json` (economia de tokens).
- [x] `bot/rodizio-saude.py`: pausa automática (48h) de site sem retorno após 4 rodadas vazias.
- [x] Cooldown por modelo, sessão improdutiva e watchdog de stall no `loop.sh`; cascata de modelos e
      retentativa semanal no `followup.sh`.
- [x] `scripts/notificar.sh`, alertas de anomalia no `digest.sh` e `scripts/backup-jsons.sh`.
- [x] Regras de elegibilidade generalizadas: tempo de experiência até 3 anos, regra de formação, fluxo
      `c-Externo` para ATS sem padrão.
- [x] **Qualquer nível e área**: `niveis`, `area`, `experiencia_max_anos` e `sites_pular` no perfil,
      injetados nos prompts por [`bot/perfil_render.py`](bot/perfil_render.py).
- [x] **Modelo de trabalho configurável**: `modelos` (remoto/híbrido/presencial) e `cidades` no perfil.
- [x] Wizard gera também o `bot/perfil.json` (nível, área, modelo, termos).

## Próximo

- [ ] **Mais adaptadores de portal**, com prioridade para os generalistas que atendem perfis fora de tech —
      `good first issue`, ver [`docs/ADAPTERS.md`](docs/ADAPTERS.md). **Feitos: Catho, InfoJobs, Sólides e
      Trampos** (o `trampos.com.br` antigo saiu do ar; a plataforma é `trampos.co`). Faltam Trabalhabrasil,
      99jobs, Netvagas, Jooble, Empregos.com.br e Revelo.
- [x] **Demo animada** no topo do README (GIF/asciinema de 1 rodada + monitor).
- [x] **Demo ao vivo** do monitor com dados fake, linkada no README.
- [ ] **Mais perfis prontos** em `config/perfis/`. Já há: backend, QA, tech lead, marketing, direito,
      frontend, dados, saúde, administrativo e vendas. Faltam: suporte, financeiro/contábil,
      logística, educação, industrial e comercial.
- [x] **Relatório de funil** exportável (vistas → aplicadas → respondidas → convites → entrevistas),
      em CSV e Markdown: [`bot/funil.py`](bot/funil.py), casca em `scripts/funnel.{sh,ps1}`.
- [x] Cobertura de testes dos adaptadores (URL montada por `site_url_busca`).
- [x] Testes Pester para `Expand-PerfilPlaceholders` (`loop.ps1`) e o filtro de sites do `dry-run.ps1`
      ([`tests/loop.Tests.ps1`](tests/loop.Tests.ps1) e [`tests/sites.Tests.ps1`](tests/sites.Tests.ps1),
      31 testes; o segundo roda o bash de verdade e compara a URL dos dois espelhos).
- [x] **`bot/loop.ps1`**: watchdog de stall/early-abort mid-rodada portado do `loop.sh`
      (`Get-ProviderError` + poll do log da rodada em `Invoke-ModelRound`); a leitura do log
      interno do opencode é fail-open (sem log, só age o critério de stall).

## Depois / ideias

- [ ] Suporte a espanhol (LatAm) no prompt e nos filtros.
- [ ] Painel de métricas históricas (opt-in, ainda sem banco).
- [ ] Detecção de vaga duplicada entre portais.
- [x] Modo "somente triagem" (lista e pontua, não aplica) — é o modo reconhecimento (`OV_RECONHECIMENTO=1`).

## Como ajudar

Veja [`CONTRIBUTING.md`](CONTRIBUTING.md). O PR de maior impacto e mais fácil é um
**adaptador de portal novo**. Itens marcados como `good first issue` nas Issues são
pensados para a primeira contribuição.
