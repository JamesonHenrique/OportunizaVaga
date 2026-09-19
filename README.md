# OportunizaVaga 🤖🇧🇷

<p align="center">
  <img src="assets/logo.svg" alt="OportunizaVaga logo" width="480">
</p>

[![CI](https://img.shields.io/github/actions/workflow/status/JamesonHenrique/OportunizaVaga/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%7CWindows%7CWSL2-blue.svg)](docs/QUICKSTART.md)
[![Release](https://img.shields.io/github/v/release/JamesonHenrique/OportunizaVaga?label=release)](https://github.com/JamesonHenrique/OportunizaVaga/releases)

> 🌐 Translations: 🇧🇷 [Português](README.pt-BR.md) · 🇪🇸 [Español](README.es.md)

Open-source bot that **auto-applies to junior/trainee remote jobs in Brazil**,
running on your own PC at **zero cost** (free AI models + Brazilian job boards).

> ⚠️ **Legal warning:** automating applications may violate the Terms of Use of
> LinkedIn, Gupy, Indeed and other portals. This code is published for study and
> personal automation; **you accept the risk of your accounts being blocked or
> suspended** by using it. The authors are not liable for suspended accounts,
> missed jobs, or any damage resulting from its use.
> Read [`docs/USO-ETICO.md`](docs/USO-ETICO.md) before scaling usage.

## Demo

<!-- TODO(demo): replace with a real recording.
     Record a ≤30s asciinema/GIF of one round + the live monitor, save it as
     assets/demo.gif, and swap the placeholder below. This is the single biggest
     lever for the project's reach — see ROADMAP.md. -->
<p align="center">
  <img src="assets/demo.gif" alt="OportunizaVaga em ação: uma rodada + o monitor ao vivo" width="820">
  <br><em>▶️ Demo (GIF em breve). Enquanto isso: <code>./bot/dry-run.sh</code> mostra uma rodada simulada sem aplicar em nada.</em>
</p>

<!-- TODO(live-demo): host the monitor with FAKE data on Vercel free-tier and link it here.
     Never point a public demo at real dados_candidato.json / aplicadas.json. -->
> 🔴 **Live demo** (monitor with sample data): _coming soon_ — see [`monitor/README.md`](monitor/README.md).

## How it works

```
cron (*/5) ──▶ bot/guardiao.sh ──┬──▶ bot/loop.sh ──▶ opencode run (free model)
                                 │        │              │
                                 │        │              └──▶ Real Chrome (CDP :9222)
                                 │        │                   1 site in rotation per round
                                 │        │                   (Indeed, LinkedIn, Gupy,
                                 │        │                    Programathor, GeekHunter…)
                                 │        └──▶ state in bot/aplicadas.json
                                 │             (NEVER in the model session)
                                 └──▶ Chrome over CDP (restarts on its own if it drops)
```

- **1 site per round**, circular rotation, 20 min sleep between rounds (backoff when empty).
- **Profile isolation:** active profile keeps its own state in `bot/state/<perfil>/`.
- **Recognition mode:** `OV_RECONHECIMENTO=1` scores jobs without applying.
- **Junior/trainee + remote + ≤14 days only** (all configurable in the prompt).
- **Never hallucinates data:** everything comes from `bot/dados_candidato.json`;
  gaps become `bloqueado` entries with the exact reason.
- **Noise-free:** listing discards become counters, never block entries.
- **Free-model cascade** (Zen → OpenRouter → NVIDIA → Groq → Cerebras → HF,
  optional Copilot): on rate limit it tries the next one — return to the
  preferred model is automatic.
- **Weekly follow-up** (Mondays): rechecks applied-job status.
- **Optional monitor** (`monitor/`): free-tier dashboard, no database, aggregate
  telemetry by default (raw details are explicit opt-in).

## Quickstart (5 steps)

### 1. Install

```bash
curl -fsSL https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.ps1 | iex
```

Manual alternative: `git clone https://github.com/JamesonHenrique/OportunizaVaga oportunizavaga`
(`scripts/setup.sh` on Linux, `scripts\setup.ps1` on Windows; WSL2 recommended).
Full guide: [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

### 2. Fill in YOUR data (never commit!)

Fastest path — interactive wizard (no JSON editing):

```bash
./scripts/setup-wizard.sh          # Windows: scripts\setup-wizard.ps1
```

Or copy `examples/` to `bot/dados_candidato.json` and edit by hand.
**Empty field = the bot records "bloqueado" instead of inventing.**
Adapt filters to your stack: [`docs/PROMPTS.md`](docs/PROMPTS.md).

### 3. Browser — start Chrome, log in once

```bash
./browser/chrome-real.sh &  # CDP on :9222; one login covers every site
```

Details: [`browser/README.md`](browser/README.md). Domain allowlist:
[`config/sites_permitidos.json`](config/sites_permitidos.json).

### 4. Safe test first, then one real round

```bash
./bot/dry-run.sh   # simulation: reads files only, applies to nothing
./bot/loop.sh      # real round — Ctrl+C after the first "ok"
./bot/doctor.sh    # environment checklist (exit 0 = essentials OK)
```

Windows mirrors: `bot\dry-run.ps1`, `bot\loop.ps1`, `bot\doctor.ps1`.

### 5. Automate (cron | Task Scheduler)

```bash
crontab -e   # paste config/crontab.example, adjusting BOT_DIR
```

Windows: ready-made commands in [`config/TaskScheduler.md`](config/TaskScheduler.md).

## Monitor (optional)

```bash
cd monitor && npm install && npm run dev   # or free deploy — see monitor/README.md
```

Docker demo with sample data (never your real data):

```bash
docker compose up monitor   # see monitor/README.md
```

Without `MONITOR_URL`, the bot works normally — it just publishes nothing.

## Security — READ BEFORE COMMITTING

**Never** commit: `bot/dados_candidato.json`, `bot/aplicadas.json`, `bot/state/`,
`bot/prompt_loop.runtime.md`, PDF CVs, `cron.env`/`auth.json`, `*.log`, `logs/`,
the Chrome profile, `*.bak-*` backups. `.gitignore` already blocks all of this —
check `git status` before every push and run `./scripts/sanitize.sh`. Leaked a
secret? **Rotate it immediately** at the provider (removing it from git does not
erase history).
Details: [`docs/SEGURANCA.md`](docs/SEGURANCA.md).

## Docs

| Guide | What |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | zero to first round in ~20 min |
| [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) | diagram, components, key decisions |
| [`docs/CUSTO.md`](docs/CUSTO.md) | why it costs R$ 0 + the model ladder |
| [`docs/MODELOS.md`](docs/MODELOS.md) | provider-agnostic + 100% local (Ollama) |
| [`docs/ADAPTERS.md`](docs/ADAPTERS.md) | add a job portal (easiest way to contribute) |
| [`docs/SEGURANCA.md`](docs/SEGURANCA.md) | secrets, gitignore, pre-commit, if leaked |
| [`docs/USO-ETICO.md`](docs/USO-ETICO.md) | responsible use, pacing, privacy |
| [`docs/FAQ.md`](docs/FAQ.md) | portal permission, quota, locks, new sites |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | adapt stack, terms and filters to your profile |

## License

MIT — see [`LICENSE`](LICENSE). Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md).
