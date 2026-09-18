# Roadmap

Direção pública do OportunizaVaga. Não é promessa de data — é onde ajuda é bem-vinda.
Discussão e sugestões: abra uma issue com o template de _feature request_, ou use as
Discussions do repositório.

## Princípios que não mudam

- **R$ 0** para rodar (modelos free ou locais). Ver [`docs/CUSTO.md`](docs/CUSTO.md).
- **Nunca inventar dado.** Campo vazio vira `bloqueado`, sempre.
- **Estado durável só em `aplicadas.json`** — nunca na sessão do modelo.
- **Sem servidor**: seu PC + cron. Monitor é opcional e free-tier.

## Agora (v0.x)

- [x] Cascata de modelos free com backoff e rodízio de 1 site/rodada.
- [x] Monitor opcional (dashboard sem banco).
- [x] Scaffold OSS: CI, testes, docs, templates, segurança.
- [x] Contrato de adaptadores de site + template ([`docs/ADAPTERS.md`](docs/ADAPTERS.md)).
- [x] Modo 100% local com Ollama ([`docs/MODELOS.md`](docs/MODELOS.md)).
- [x] Wizard de setup (`scripts/setup-wizard.sh`).
- [x] Pacing configurável + guia de uso ético ([`docs/USO-ETICO.md`](docs/USO-ETICO.md)).

## Próximo

- [ ] **Mais adaptadores de portal** (Catho, Trampos, Revelo, InfoJobs, Solides…) —
      `good first issue`, ver [`docs/ADAPTERS.md`](docs/ADAPTERS.md).
- [ ] **Demo animada** no topo do README (GIF/asciinema de 1 rodada + monitor).
- [ ] **Demo ao vivo** do monitor com dados fake, linkada no README.
- [ ] **Perfis prontos** por área (backend, frontend, dados, QA) em `config/perfis/`.
- [ ] **Relatório de funil** exportável (aplicadas → convites → entrevistas).
- [ ] Cobertura de testes dos adaptadores (URL montada por `site_url_busca`).

## Depois / ideias

- [ ] Suporte a espanhol (LatAm) no prompt e nos filtros.
- [ ] Painel de métricas históricas (opt-in, ainda sem banco).
- [ ] Detecção de vaga duplicada entre portais.
- [ ] Modo "somente triagem" (lista e pontua, não aplica).

## Como ajudar

Veja [`CONTRIBUTING.md`](CONTRIBUTING.md). O PR de maior impacto e mais fácil é um
**adaptador de portal novo**. Itens marcados como `good first issue` nas Issues são
pensados para a primeira contribuição.
