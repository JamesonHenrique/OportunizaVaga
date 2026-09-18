# Task Scheduler (Windows) — equivale ao config/crontab.example

> Espelho Windows do `crontab.example`. Ajuste `BOT_DIR` ao caminho do seu clone
> (ex.: `C:\Users\VOCE\opensource\oportunizavaga`). Rode os comandos num
> **PowerShell como o seu usuário** (não precisa ser admin para tarefas do usuário).
> Fuso: deixe o Windows em "(UTC-03:00) Brasília" — os `.ps1` carimbam hora local
> com offset -03:00 documentado (o Node no Windows ignora TZ IANA).

## 1. Guardião a cada 5 min (loop + Chrome)

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\Guardiao' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\bot\guardiao.ps1`"" `
  /SC MINUTE /MO 5 /F
```

Equivale a `*/5 * * * * $BOT_DIR/bot/guardiao.sh`.

## 2. Guardião no logon (cobre reboot sem tarefa de boot)

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\GuardiaoLogon' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\bot\guardiao.ps1`"" `
  /SC ONLOGON /F
```

Equivale a `@reboot $BOT_DIR/bot/guardiao.sh`.

## 3. Publisher do monitor (opcional, só se usar monitor/)

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\MonitorKeepalive' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\scripts\monitor-keepalive.ps1`"" `
  /SC MINUTE /MO 5 /F
```

Equivale a `*/5 * * * * $BOT_DIR/scripts/monitor-keepalive.sh`.

## 4. "Correio" do monitor (opcional)

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\PullMonitor' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\scripts\pull-monitor.ps1`"" `
  /SC MINUTE /MO 10 /F
```

Equivale a `*/10 * * * * $BOT_DIR/scripts/pull-monitor.sh`.

## 5. Follow-up semanal (segundas 09:00)

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\Followup' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\bot\followup.ps1`"" `
  /SC WEEKLY /D MON /ST 09:00 /F
```

Equivale a `0 9 * * 1 $BOT_DIR/bot/followup.sh`.

## Conferir / remover

```powershell
schtasks /Query /TN 'OportunizaVaga\Guardiao'
schtasks /Query /TN 'OportunizaVaga\Followup'
# remover: schtasks /Delete /TN 'OportunizaVaga\Guardiao' /F
```

## Notas

- As tarefas rodam como o seu usuário: o Chrome abre na sua sessão e o perfil
  em `%LOCALAPPDATA%\oportunizavaga-chrome-real` é reutilizado (login 1x).
- Se o PowerShell reclamar de política de execução, rode 1x:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Logs: `bot\loop.log`, `bot\guardiao.log`, `bot\followup.log` (mesmos nomes do Linux).
- Locks em `%TEMP%` (`oportunizavaga-loop.lock`, `agent-chrome-9222.lock`).
