# QUICKSTART — do zero à primeira rodada em ~20 min

> Você precisa de: Google Chrome, Node 20+, Python 3, [opencode](https://opencode.ai)
> com algum provider gratuito configurado, e uma conta Google (p/ Gupy/LinkedIn).
> **Linux** (testado) ou **Windows 10/11** — veja as abas abaixo.

## Linux | Windows

- **Linux (recomendado, caminho principal):** siga o guia como está (bash + cron).
- **Windows — opção A, WSL2 (recomendado):** instale o WSL2 + Ubuntu e siga o guia
  Linux dentro do WSL. O Chrome pode ficar no Windows (CDP em `:9222`) ou no WSL.
- **Windows — opção B, PowerShell nativo (alternativo):** use os espelhos `.ps1`
  (mesma lógica dos `.sh`) + Task Scheduler (`config/TaskScheduler.md`).
  Limitações conhecidas: watchdog simplificado (sem inspeção do log interno do
  opencode) e carimbos em hora local com offset -03:00 documentado (o Node no
  Windows ignora TZ IANA). Detalhes no cabeçalho de `bot/loop.ps1`.

## 1. Clone e setup

### Linux

```bash
git clone <sua-fork> oportunizavaga && cd oportunizavaga
./scripts/setup.sh
```

O setup copia os exemplos, valida dependências e imprime o crontab sugerido.

### Windows (PowerShell nativo)

```powershell
git clone <sua-fork> oportunizavaga; cd oportunizavaga
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

O setup copia os exemplos, valida dependências e imprime os comandos `schtasks`
(equivalentes ao crontab). Guia completo em `config/TaskScheduler.md`.

## 2. Preencha SEUS dados (nunca commite!)

```bash
cp examples/dados_candidato.example.json bot/dados_candidato.json
cp examples/aplicadas.example.json bot/aplicadas.json
```

Edite `bot/dados_candidato.json`: nome, e-mail, stack real (`experiencia.tecnologias`),
similares JR (`experiencia.stacks_similares_jr`), pretensão (`SEU_VALOR_BASE`),
respostas padrão de formulário. **Campo vazio = o robô registra "bloqueado" em vez
de inventar.** Veja `docs/PROMPTS.md` para adaptar `bot/prompt_loop.md` ao seu stack.

## 3. Chaves de API (fora do repo)

### Linux

```bash
touch ~/.config/opencode/cron.env && chmod 600 ~/.config/opencode/cron.env
# Ex.: OPENROUTER_API_KEY=... (só se USAR_OPENROUTER=1 em bot/loop.sh)
```

### Windows (PowerShell nativo)

```powershell
$null = New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\opencode"
notepad "$env:USERPROFILE\.config\opencode\cron.env"  # OPENROUTER_API_KEY=... (só se USAR_OPENROUTER=1)
```

## 4. Browser

### Linux

```bash
./browser/chrome-real.sh &   # CDP em :9222; faça login 1x nos sites (vale p/ tudo)
```

### Windows (PowerShell nativo)

```powershell
powershell -ExecutionPolicy Bypass -File browser\chrome-real.ps1
# CDP em :9222; faça login 1x nos sites (vale p/ tudo). Perfil em %LOCALAPPDATA%\oportunizavaga-chrome-real
```

Detalhes em `browser/README.md`. A allowlist de domínios está em
`config/sites_permitidos.json` e deve espelhar o `--allowed-origins` do seu
`~/.config/opencode/opencode.jsonc` (modelo em `config/opencode.jsonc.example`).

## 5. Teste manual (1 rodada)

### Linux

```bash
./bot/loop.sh   # Ctrl+C após a primeira rodada "ok" — confira bot/loop.log e aplicadas.json
```

### Windows (PowerShell nativo)

```powershell
powershell -ExecutionPolicy Bypass -File bot\loop.ps1  # Ctrl+C após a primeira rodada "ok"
```

## 6. Automação (cron | Task Scheduler)

### Linux (cron)

```bash
crontab -e   # cole o conteúdo de config/crontab.example, ajustando BOT_DIR
```

- `bot/guardiao.sh` (`*/5` + `@reboot`): mantém loop + Chrome de pé.
- `bot/followup.sh` (seg 09:00): atualiza o status das vagas aplicadas.
- `scripts/monitor-keepalive.sh` (opcional): heartbeat do painel `monitor/`.

### Windows (Task Scheduler)

```powershell
# comandos prontos em config/TaskScheduler.md (ajuste BOT_DIR):
# Guardião a cada 5min + no logon, follow-up seg 09:00, keepalive/pull opcionais
```

- `bot\guardiao.ps1` (5min + logon): mantém loop + Chrome de pé.
- `bot\followup.ps1` (seg 09:00): atualiza o status das vagas aplicadas.
- `scripts\monitor-keepalive.ps1` (opcional): heartbeat do painel `monitor/`.

## 7. Monitor (opcional)

```bash
cd monitor && npm install && npm run dev   # ou deploy na Vercel (veja monitor/README.md)
export MONITOR_URL=https://sua-url.vercel.app
```

Sem `MONITOR_URL`, o bot funciona normalmente — só não publica status.

## Teste sem risco (dry-run)

Antes de ligar o loop real, simule UMA rodada sem se candidatar (só lê
arquivos — não abre browser, não aplica em nada):

```bash
./bot/dry-run.sh           # resumo humano do que a rodada faria
./bot/dry-run.sh --json    # saída máquina (site, termos, limite 3, modelo)
```

Windows (PowerShell nativo):

```powershell
powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1
powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1 --json
```

## Diagnosticando (doctor)

Checklist de ambiente com dicas de correção por item (saída colável em issue):

```bash
./bot/doctor.sh
```

Windows (PowerShell nativo):

```powershell
powershell -ExecutionPolicy Bypass -File bot\doctor.ps1
```

Exit 0 = essencial ok (`[??]` são só avisos); exit 1 = falta algo essencial
(veja os itens `[FALHA]`). Validação fina dos JSONs contra os schemas em
`config/`: `bash scripts/validate.sh` (ou `scripts\validate.ps1`).
