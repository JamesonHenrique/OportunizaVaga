# OportunizaVaga 🤖🇧🇷

<p align="center">
  <img src="assets/logo.svg" alt="OportunizaVaga logo" width="480">
</p>

[![CI](https://img.shields.io/github/actions/workflow/status/JamesonHenrique/OportunizaVaga/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%7CWindows%7CWSL2-blue.svg)](docs/QUICKSTART.md)
[![Release](https://img.shields.io/github/v/release/JamesonHenrique/OportunizaVaga?label=release)](https://github.com/JamesonHenrique/OportunizaVaga/releases)

> 🌐 Traducciones / Translations: 🇬🇧 [English](README.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇪🇸 Español

Bot de código abierto que **aplica automáticamente a empleos remotos junior/trainee en Brasil**,
ejecutándose en tu propia PC a **costo cero** (modelos de IA gratuitos + portales de empleos brasileños).

> ⚠️ **Aviso legal:** automatizar solicitudes puede violar los Términos de Servicio de
> LinkedIn, Gupy, Indeed y otros portales. Este código se publica para estudio y
> automatización personal; **aceptas el riesgo de que tus cuentas sean bloqueadas o
> suspendidas** al usarlo. Los autores no son responsables de cuentas suspendidas,
> empleos perdidos o cualquier daño resultante de su uso.
> Lee [`docs/USO-ETICO.md`](docs/USO-ETICO.md) antes de aumentar el uso.

## Demo

<!-- TODO(demo): replace with a real recording.
     Record a ≤30s asciinema/GIF of one round + the live monitor, save it as
     assets/demo.gif, and swap the placeholder below. This is the single biggest
     lever for the project's reach — see ROADMAP.md. -->
<p align="center">
  <img src="assets/demo.gif" alt="OportunizaVaga em ação: uma rodada + o monitor ao vivo" width="820">
  <br><em>▶️ Demo (GIF próximamente). Mientras tanto: <code>./bot/dry-run.sh</code> muestra una ronda simulada sin aplicar a nada.</em>
</p>

<!-- TODO(live-demo): host the monitor with FAKE data on Vercel free-tier and link it here.
     Never point a public demo at real dados_candidato.json / aplicadas.json. -->
> 🔴 **Demo en vivo** (monitor con datos de ejemplo): _próximamente_ — ver [`monitor/README.md`](monitor/README.md).

## Cómo funciona

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

- **1 sitio por ronda**, rotación circular, 20 min de espera entre rondas (retroceso cuando está vacío).
- **Estado aislado por perfil:** el perfil activo guarda su historial en `bot/state/<perfil>/`.
- **Modo reconocimiento:** `OV_RECONHECIMENTO=1` puntúa vacantes sin postularse.
- **Solo junior/trainee + remoto + ≤14 días** (todo configurable en el prompt).
- **Nunca alucina datos:** todo proviene de `bot/dados_candidato.json`;
  los vacíos se convierten en entradas `bloqueado` con la razón exacta.
- **Sin ruido:** los listados descartados se convierten en contadores, nunca bloquean entradas.
- **Cascada de modelo gratuito** (Zen → OpenRouter → NVIDIA → Groq → Cerebras → HF,
  Copilot opcional): al llegar al límite de velocidad intenta el siguiente — la
  vuelta al modelo preferido es automática.
- **Seguimiento semanal** (lunes): verifica nuevamente el estado de empleos solicitados.
- **Monitor opcional** (`monitor/`): dashboard de nivel gratuito, sin base de datos,
  con telemetría agregada por defecto (detalles solo con opt-in).

## Inicio rápido (5 pasos)

### 1. Instalar

```bash
curl -fsSL https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.ps1 | iex
```

Alternativa manual: `git clone https://github.com/JamesonHenrique/OportunizaVaga oportunizavaga`
(`scripts/setup.sh` en Linux, `scripts\setup.ps1` en Windows; WSL2 recomendado).
Guía completa: [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

### 2. Completa TUS datos (¡nunca hagas commit!)

Camino más rápido — asistente interactivo (sin editar JSON):

```bash
./scripts/setup-wizard.sh          # Windows: scripts\setup-wizard.ps1
```

O copia `examples/` a `bot/dados_candidato.json` y edita manualmente.
**Campo vacío = el bot registra "bloqueado" en lugar de inventar.**
Adapta los filtros a tu stack: [`docs/PROMPTS.md`](docs/PROMPTS.md).

### 3. Navegador — inicia Chrome, inicia sesión una vez

```bash
./browser/chrome-real.sh &  # CDP on :9222; one login covers every site
```

Detalles: [`browser/README.md`](browser/README.md). Lista de dominios permitidos:
[`config/sites_permitidos.json`](config/sites_permitidos.json).

### 4. Prueba segura primero, luego una ronda real

```bash
./bot/dry-run.sh            # plan global: solo lee archivos, no aplica nada
./bot/dry-run.sh --json
./bot/dry-run.sh --json --site indeed
./bot/loop.sh      # real round — Ctrl+C after the first "ok"
./bot/doctor.sh    # environment checklist (exit 0 = essentials OK)
```

Espejos de Windows: `bot\dry-run.ps1`, `bot\loop.ps1`, `bot\doctor.ps1`.

### 5. Automatizar (cron | Task Scheduler)

```bash
crontab -e   # paste config/crontab.example, adjusting BOT_DIR
```

Windows: comandos listos en [`config/TaskScheduler.md`](config/TaskScheduler.md).

## Monitor (opcional)

```bash
cd monitor && npm install && npm run dev   # or free deploy — see monitor/README.md
```

Demo Docker con datos de ejemplo (nunca tus datos reales):

```bash
docker compose up monitor   # see monitor/README.md
```

Sin `MONITOR_URL`, el bot funciona normalmente — simplemente no publica nada.

## Seguridad — LEE ANTES DE HACER COMMIT

**Nunca** hagas commit: `bot/dados_candidato.json`, `bot/aplicadas.json`, `bot/state/`,
`bot/prompt_loop.runtime.md`, PDF de CVs, `cron.env`/`auth.json`, `*.log`, `logs/`,
el perfil de Chrome, copias de seguridad `*.bak-*`. `.gitignore` ya bloquea todo esto —
comprueba `git status` antes de cada push y ejecuta `./scripts/sanitize.sh`.
¿Filtraste un secreto? **Rótalo inmediatamente** en el proveedor (eliminarlo de git
no borra el historial). Detalles: [`docs/SEGURANCA.md`](docs/SEGURANCA.md).

## Documentación

| Guía | Qué |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | de cero a primera ronda en ~20 min |
| [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) | diagrama, componentes, decisiones clave |
| [`docs/CUSTO.md`](docs/CUSTO.md) | por qué cuesta R$ 0 + la escala de modelos |
| [`docs/MODELOS.md`](docs/MODELOS.md) | agnóstico de proveedor + 100% local (Ollama) |
| [`docs/ADAPTERS.md`](docs/ADAPTERS.md) | añade un portal de empleos (forma más fácil de contribuir) |
| [`docs/SEGURANCA.md`](docs/SEGURANCA.md) | secretos, gitignore, pre-commit, si se filtran |
| [`docs/USO-ETICO.md`](docs/USO-ETICO.md) | uso responsable, velocidad, privacidad |
| [`docs/FAQ.md`](docs/FAQ.md) | permiso del portal, cuota, bloqueos, sitios nuevos |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | adapta stack, términos y filtros a tu perfil |

## Licencia

MIT — ver [`LICENSE`](LICENSE). Contribuciones: [`CONTRIBUTING.md`](CONTRIBUTING.md).
