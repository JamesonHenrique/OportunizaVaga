# OportunizaVaga 🤖🇧🇷

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Shell](https://img.shields.io/badge/shell-bash-blue.svg)](bot/)
[![Custo](https://img.shields.io/badge/custo-R%240%2Fm%C3%AAs-brightgreen.svg)](docs/CUSTO.md)
[![Node](https://img.shields.io/badge/monitor-node%20%2B%20vercel-black.svg)](monitor/)

Robô open-source de **candidaturas automáticas para vagas JR/trainee remotas no Brasil**,
rodando no seu próprio PC a **custo zero** (modelos de IA gratuitos + sites de vaga BR).

> ⚠️ **Aviso legal:** automatizar candidaturas pode violar os Termos de Uso de LinkedIn,
> Gupy, Indeed e outros portais. Este código é publicado para estudo e automação pessoal;
> **você assume o risco de bloqueio/suspensão das suas contas** ao usá-lo. Os autores não
> se responsabilizam por contas suspensas, vagas perdidas ou qualquer dano decorrente do uso.

## Como funciona

```
cron (*/5) ──▶ bot/guardiao.sh ──┬──▶ bot/loop.sh ──▶ opencode run (modelo grátis)
                                 │        │              │
                                 │        │              └──▶ Chrome real (CDP :9222)
                                 │        │                   1 site do rodízio por rodada
                                 │        │                   (Indeed, LinkedIn, Gupy,
                                 │        │                    Programathor, GeekHunter…)
                                 │        └──▶ estado em bot/aplicadas.json
                                 │             (NUNCA na sessão do modelo)
                                 └──▶ Chrome com CDP (sobe sozinho se cair)
```

- **1 site por rodada**, rodízio circular, dorme 20 min entre rodadas (backoff se vazio).
- **Só JR/trainee + remoto + ≤14 dias** (tudo configurável no prompt).
- **Nunca inventa dados:** tudo vem de `bot/dados_candidato.json`; o que falta vira
  `bloqueado` com o motivo exato.
- **Anti-ruído:** descarte de listagem vira contador, não polui bloqueios.
- **Cascata de modelos gratuitos** (Zen → OpenRouter → NVIDIA → Groq → Cerebras → HF,
  Copilot opcional): se um bater no rate limit, tenta o próximo — a volta ao preferido
  é automática.
- **Follow-up semanal** (segundas): recheca o status das vagas aplicadas.
- **Monitor opcional** (`monitor/`): painel na Vercel free, sem banco.

## Estrutura

```
oportunizavaga/
├── bot/
│   ├── loop.sh                  # loop principal (1 rodada = 1 sessão nova do modelo)
│   ├── guardiao.sh              # supervisor via cron: loop + Chrome
│   ├── followup.sh              # rotina semanal de status (só lê, nunca candidata)
│   ├── prompt_loop.md           # regras e passo a passo de cada rodada (o "cérebro")
│   ├── prompt_followup.md       # prompt da rotina semanal
│   └── prompt_perfil_gupy.md    # manutenção avulsa do perfil Gupy
├── browser/
│   ├── chrome-real.sh           # Chrome persistente com CDP :9222
│   └── README.md
├── config/
│   ├── sites_permitidos.json    # allowlist de domínios BR (espelha o bloqueio do browser)
│   ├── opencode.jsonc.example   # modelo do config do opencode (com a cascata de modelos)
│   └── crontab.example          # cron sugerido (guardiao, keepalive, follow-up)
├── monitor/                     # painel opcional (Vercel free, sem banco)
│   ├── snapshot.mjs             # retrato a partir de bot/aplicadas.json + logs
│   ├── publish-status.mjs       # heartbeat (daemon)
│   ├── publish-once.mjs         # envio único por evento
│   ├── quota-daemon.mjs         # cota diária OpenRouter :free
│   ├── package.json / vercel.json / README.md
├── scripts/
│   ├── setup.sh                 # instalador interativo (copia exemplos, valida deps)
│   ├── sanitize.sh              # varredura pré-commit de segredos/dados pessoais
│   ├── monitor-keepalive.sh     # mantém o publisher do painel no ar
│   └── pull-monitor.sh          # atualiza o painel via git pull
├── examples/
│   ├── dados_candidato.example.json  # COPIE p/ bot/dados_candidato.json e preencha
│   └── aplicadas.example.json        # COPIE p/ bot/aplicadas.json (estado inicial)
├── docs/                        # QUICKSTART, ARQUITETURA, CUSTO, SEGURANCA, FAQ, PROMPTS
├── CONTRIBUTING.md / LICENSE (MIT)
└── README.md
```

## Setup resumido

```bash
git clone <sua-fork> oportunizavaga && cd oportunizavaga
./scripts/setup.sh          # copia exemplos, valida deps, imprime crontab
# preencha bot/dados_candidato.json com SEUS dados (nunca commite!)
./browser/chrome-real.sh &  # login 1x nos sites
./bot/loop.sh               # teste 1 rodada (Ctrl+C após o primeiro "ok")
crontab -e                  # cole config/crontab.example
```

Guia completo: [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Segurança — LEIA ANTES DE COMMITAR

**Nunca** commite: `bot/dados_candidato.json`, `bot/aplicadas.json`, CVs em PDF,
`cron.env`/`auth.json`, `*.log`, `logs/`, perfil do Chrome, backups `*.bak-*`.
O `.gitignore` já bloqueia tudo isso — confira com `git status` antes de cada push e
rode `./scripts/sanitize.sh`. Vazou secret? **Rotacione imediatamente** no provedor
(remover do git não apaga o histórico). Detalhes em [`docs/SEGURANCA.md`](docs/SEGURANCA.md).

## Docs

| Guia | O quê |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | do zero à primeira rodada em ~20 min |
| [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) | diagrama, componentes, decisões-chave |
| [`docs/CUSTO.md`](docs/CUSTO.md) | por que custa R$ 0 + a escada de modelos |
| [`docs/SEGURANCA.md`](docs/SEGURANCA.md) | segredos, gitignore, pre-commit, se vazar |
| [`docs/FAQ.md`](docs/FAQ.md) | permissão dos portais, quota, locks, novos sites |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | como adaptar stack, termos e filtros ao seu perfil |

## Licença

MIT — veja [`LICENSE`](LICENSE). Contribuições: [`CONTRIBUTING.md`](CONTRIBUTING.md).
