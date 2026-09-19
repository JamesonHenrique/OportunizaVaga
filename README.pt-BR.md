> 🌐 Idiomas: 🇬🇧 [English](README.md) · 🇧🇷 Português · 🇪🇸 [Español](README.es.md)

# OportunizaVaga 🤖🇧🇷

<p align="center">
  <img src="assets/logo.svg" alt="Logo OportunizaVaga" width="480">
</p>

[![CI](https://img.shields.io/github/actions/workflow/status/JamesonHenrique/OportunizaVaga/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%7CWindows%7CWSL2-blue.svg)](docs/QUICKSTART.md)
[![Release](https://img.shields.io/github/v/release/JamesonHenrique/OportunizaVaga?label=release)](https://github.com/JamesonHenrique/OportunizaVaga/releases)
[![Shell](https://img.shields.io/badge/shell-bash-blue.svg)](bot/)
[![Custo](https://img.shields.io/badge/custo-R%240%2Fm%C3%AAs-brightgreen.svg)](docs/CUSTO.md)
[![Node](https://img.shields.io/badge/monitor-node%20%2B%20vercel-black.svg)](monitor/)

Robô open-source de **candidaturas automáticas para vagas JR/trainee remotas no Brasil**,
rodando no seu próprio PC a **custo zero** (modelos de IA gratuitos + sites de vaga BR).

> ⚠️ **Aviso legal:** automatizar candidaturas pode violar os Termos de Uso de LinkedIn,
> Gupy, Indeed e outros portais. Este código é publicado para estudo e automação pessoal;
> **você assume o risco de bloqueio/suspensão das suas contas** ao usá-lo. Os autores não
> se responsabilizam por contas suspensas, vagas perdidas ou qualquer dano decorrente do uso.
> Leia [`docs/USO-ETICO.md`](docs/USO-ETICO.md) antes de escalar o uso.

## Demo

<!-- TODO(demo): trocar pelo GIF real. Grave ≤30s (asciinema/GIF) de uma rodada +
     o monitor ao vivo, salve em assets/demo.gif e troque o placeholder abaixo.
     É a maior alavanca de alcance do projeto — ver ROADMAP.md. -->
<p align="center">
  <img src="assets/demo.gif" alt="OportunizaVaga em ação: uma rodada + o monitor ao vivo" width="820">
  <br><em>▶️ Demo (GIF em breve). Por ora: <code>./bot/dry-run.sh</code> mostra uma rodada simulada sem aplicar em nada.</em>
</p>

> 🔴 **Demo ao vivo** (monitor com dados fake): _em breve_ — ver [`monitor/README.md`](monitor/README.md).

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
- **Estado isolado por perfil:** o perfil ativo guarda o próprio histórico em `bot/state/<perfil>/`.
- **Modo reconhecimento:** `OV_RECONHECIMENTO=1` pontua vagas sem se candidatar.
- **Só JR/trainee + remoto + ≤14 dias** (tudo configurável no prompt).
- **Nunca inventa dados:** tudo vem de `bot/dados_candidato.json`; o que falta vira
  `bloqueado` com o motivo exato.
- **Anti-ruído:** descarte de listagem vira contador, não polui bloqueios.
- **Cascata de modelos gratuitos** (Zen → OpenRouter → NVIDIA → Groq → Cerebras → HF,
  Copilot opcional): se um bater no rate limit, tenta o próximo — a volta ao preferido
  é automática.
- **Follow-up semanal** (segundas): recheca o status das vagas aplicadas.
- **Monitor opcional** (`monitor/`): painel na Vercel free, sem banco, com telemetria
  agregada por padrão (detalhes brutos só com opt-in).

## Estrutura

```
oportunizavaga/
├── bot/
│   ├── loop.sh                  # loop principal (1 rodada = 1 sessão nova do modelo)
│   ├── dry-run.sh               # plano global sem risco (perfil, sites, limites)
│   ├── loop.ps1                 # espelho Windows (PowerShell 5.1+, mesma lógica)
│   ├── dry-run.ps1              # espelho Windows do plano sem risco
│   ├── guardiao.sh              # supervisor via cron: loop + Chrome
│   ├── guardiao.ps1             # espelho Windows (Task Scheduler)
│   ├── followup.sh              # rotina semanal de status (só lê, nunca candidata)
│   ├── followup.ps1             # espelho Windows
│   ├── prompt_loop.md           # regras e passo a passo de cada rodada (o "cérebro")
│   ├── prompt_followup.md       # prompt da rotina semanal
│   ├── prompt_perfil_gupy.md    # manutenção avulsa do perfil Gupy
│   └── sites/                   # adaptadores descobertos automaticamente
│       ├── lib.sh               # contrato comum (site_adapter_*)
│       └── *.sh                 # indeed, gupy, linkedin, programathor, geekhunter, vagas
├── browser/
│   ├── chrome-real.sh           # Chrome persistente com CDP :9222
│   ├── chrome-real.ps1          # espelho Windows (perfil em %LOCALAPPDATA%)
│   └── README.md
├── config/
│   ├── sites_permitidos.json    # allowlist de domínios BR (espelha o bloqueio do browser)
│   ├── opencode.jsonc.example   # modelo do config do opencode (com a cascata de modelos)
│   ├── crontab.example          # cron sugerido (guardiao, keepalive, follow-up)
│   └── TaskScheduler.md         # equivalente Windows (schtasks prontos)
├── monitor/                     # painel opcional (Vercel free, sem banco)
│   ├── snapshot.mjs             # retrato a partir de bot/aplicadas.json + logs
│   ├── publish-status.mjs       # heartbeat (daemon)
│   ├── publish-once.mjs         # envio único por evento
│   ├── quota-daemon.mjs         # cota diária OpenRouter :free
│   ├── package.json / vercel.json / README.md
├── scripts/
│   ├── setup.sh / setup.ps1    # instalador interativo (Linux / Windows)
│   ├── sanitize.sh              # varredura pré-commit de segredos/dados pessoais
│   ├── monitor-keepalive.sh / .ps1  # mantém o publisher do painel no ar
│   └── pull-monitor.sh / .ps1       # atualiza o painel via git pull
├── examples/
│   ├── dados_candidato.example.json  # COPIE p/ bot/dados_candidato.json e preencha
│   └── aplicadas.example.json        # COPIE p/ bot/aplicadas.json (estado inicial)
├── docs/                        # QUICKSTART, ARQUITETURA, CUSTO, SEGURANCA, FAQ, PROMPTS
├── CONTRIBUTING.md / LICENSE (MIT)
└── README.md
```

## Setup resumido

### Linux

```bash
git clone <sua-fork> oportunizavaga && cd oportunizavaga
./scripts/setup.sh          # copia exemplos, valida deps, imprime crontab
./scripts/setup-wizard.sh   # preenche bot/dados_candidato.json por perguntas (nunca commite!)
./browser/chrome-real.sh &  # login 1x nos sites
./bot/loop.sh               # teste 1 rodada (Ctrl+C após o primeiro "ok")
crontab -e                  # cole config/crontab.example
```

### Windows (PowerShell nativo — alternativo; WSL2 recomendado)

```powershell
git clone <sua-fork> oportunizavaga; cd oportunizavaga
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File scripts\setup-wizard.ps1  # preenche dados por perguntas (nunca commite!)
powershell -ExecutionPolicy Bypass -File browser\chrome-real.ps1  # login 1x nos sites
powershell -ExecutionPolicy Bypass -File bot\loop.ps1             # teste 1 rodada (Ctrl+C após o primeiro "ok")
# agende com os comandos em config\TaskScheduler.md (equivale ao crontab.example)
```

> **Windows:** WSL2 com o guia Linux é o caminho recomendado. O PowerShell nativo
> funciona via espelhos `.ps1` (mesma lógica), com watchdog simplificado e carimbos
> em hora local (-03:00 documentado) — veja `bot/loop.ps1` e `config/TaskScheduler.md`.

Guia completo: [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Segurança — LEIA ANTES DE COMMITAR

**Nunca** commite: `bot/dados_candidato.json`, `bot/aplicadas.json`, `bot/state/`,
`bot/prompt_loop.runtime.md`, CVs em PDF, `cron.env`/`auth.json`, `*.log`, `logs/`,
perfil do Chrome, backups `*.bak-*`. O `.gitignore` já bloqueia tudo isso — confira
com `git status` antes de cada push e rode `./scripts/sanitize.sh`. Vazou secret?
**Rotacione imediatamente** no provedor (remover do git não apaga o histórico).
Detalhes em [`docs/SEGURANCA.md`](docs/SEGURANCA.md).

## Docs

| Guia | O quê |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | do zero à primeira rodada em ~20 min |
| [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) | diagrama, componentes, decisões-chave |
| [`docs/CUSTO.md`](docs/CUSTO.md) | por que custa R$ 0 + a escada de modelos |
| [`docs/MODELOS.md`](docs/MODELOS.md) | provider-agnóstico + 100% local (Ollama) |
| [`docs/ADAPTERS.md`](docs/ADAPTERS.md) | adicionar um portal de vagas (jeito mais fácil de contribuir) |
| [`docs/SEGURANCA.md`](docs/SEGURANCA.md) | segredos, gitignore, pre-commit, se vazar |
| [`docs/USO-ETICO.md`](docs/USO-ETICO.md) | uso responsável, pacing, privacidade |
| [`docs/FAQ.md`](docs/FAQ.md) | permissão dos portais, quota, locks, novos sites |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | como adaptar stack, termos e filtros ao seu perfil |

## Licença

MIT — veja [`LICENSE`](LICENSE). Contribuições: [`CONTRIBUTING.md`](CONTRIBUTING.md).
