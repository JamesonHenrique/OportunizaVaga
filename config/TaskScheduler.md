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

## 5. Follow-up semanal (roda todo dia, so executa de fato 1x/semana)

`followup.ps1` tem retentativa interna (`state/followup.ok`): pula sozinho se o
último sucesso tiver menos de 6 dias, então a tarefa pode rodar todo dia sem
duplicar o follow-up — uma falha não trava a semana inteira sem tentar de novo.

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\Followup' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\bot\followup.ps1`"" `
  /SC DAILY /ST 09:00 /F
```

Equivale a `0 9 * * * $BOT_DIR/bot/followup.sh`.

## 6. Backup rotativo dos JSONs de estado (2x/dia)

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\BackupJsons' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\scripts\backup-jsons.ps1`"" `
  /SC DAILY /ST 08:00 /RI 240 /DU 0008:00 /F
```

Equivale a `0 8,12 * * * $BOT_DIR/scripts/backup-jsons.sh` (duas execuções, 8h e 12h).

## 7. Resumo diário com alertas (21h)

`digest.ps1 -Send` exige `$env:TELEGRAM_BOT_TOKEN` e `$env:TELEGRAM_CHAT_ID` no
ambiente da tarefa (ex.: via `cron.env` carregado pelo próprio script, se você
adaptar; nunca hardcode no Task Scheduler).

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
schtasks /Create /TN 'OportunizaVaga\Digest' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\scripts\digest.ps1`" -Send" `
  /SC DAILY /ST 21:05 /F
```

Equivale a `5 21 * * * $BOT_DIR/scripts/digest.sh --send`.

## 8. Respostas do Gmail (08:40 e 18:40)

Lê as caixas de `email` e `email_contas` (as duas precisam estar logadas no Chrome do robô;
a que faltar vira só um aviso no log).

```powershell
$BOT_DIR = 'C:\Users\VOCE\opensource\oportunizavaga'
foreach ($h in '08:40','18:40') {
  schtasks /Create /TN "OportunizaVaga\GmailStatus-$($h -replace ':','')" `
    /TR "py `"$BOT_DIR\bot\gmail-status.py`"" /SC DAILY /ST $h /F
}
```

Equivale a `40 8,18 * * * python3 $BOT_DIR/bot/gmail-status.py`.

## 9. Garimpo do Telegram (opcional; 08:00, 13:00 e 18:00)

Rode uma vez à mão com `-Login` para criar a sessão; depois agende:

```powershell
foreach ($h in '08:00','13:00','18:00') {
  schtasks /Create /TN "OportunizaVaga\TgGarimpo-$($h -replace ':','')" `
    /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\bot\tg-garimpo.ps1`"" /SC DAILY /ST $h /F
}
```

## 10. Validação do estado (opcional; a cada 30 min)

```powershell
schtasks /Create /TN 'OportunizaVaga\ValidateRodada' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\scripts\validate-rodada.ps1`"" /SC MINUTE /MO 30 /F
```

## 11. Mascarar segredos nos logs (a cada 10 min)

O `loop.ps1` já limpa o log de cada rodada ao terminar (`--forcar`); esta tarefa varre o resto
(`loop.log`, `followup.log`, rotacionados, `.gz`) e ignora arquivos escritos há menos de 30 min.
Configuração opcional por variáveis: `OV_CREDENTIALS_FILE` (padrão `%USERPROFILE%\.config\oportunizavaga\credenciais.tsv`)
e `OV_REDACT_GLOBS` (globs separados por `;`).

```powershell
schtasks /Create /TN 'OportunizaVaga\RedactLogs' `
  /TR "py `"$BOT_DIR\bot\redact-logs.py`"" /SC MINUTE /MO 10 /F
```

Equivale a `*/10 * * * * python3 $BOT_DIR/bot/redact-logs.py`.

## 12. Poda das sessões do robô no opencode (opcional, opt-in; diária 04:30)

O banco do opencode guarda os argumentos de toda tool-call (senhas digitadas em formulários incluídas) e o
`redact-logs.py` não o alcança. A poda apaga só sessões cujo título começa com `candidaturas-`/`followup-` **e**
cuja pasta é a do robô, com mais de N dias (usa `created`). Teste antes: `py bot\podar-sessoes.py --dry 3`.

```powershell
schtasks /Create /TN 'OportunizaVaga\PodarSessoes' `
  /TR "py `"$BOT_DIR\bot\podar-sessoes.py`" 3" /SC DAILY /ST 04:30 /F
```

Relatório de tokens (manual): `py "$BOT_DIR\scripts\tokens-relatorio.py" 1`.

## 13. Vigia de vida / dead man's switch (a cada 15 min)

Avisa no Telegram (`scripts\notificar.ps1`) se o `loop.ps1` estiver parado em 2 checagens seguidas, se o heartbeat do
monitor tiver mais de `HB_MAX_MIN` minutos (só checa com `MONITOR_URL` definido; sem ele a checagem é pulada) ou se o
`aplicadas.json` estiver ausente/ilegível. Defina `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` (e, se usar o monitor,
`MONITOR_URL`) como variáveis de ambiente do usuário (`setx`), pois a tarefa herda o ambiente do usuário.

```powershell
schtasks /Create /TN 'OportunizaVaga\VigiaVida' `
  /TR "powershell -ExecutionPolicy Bypass -File `"$BOT_DIR\bot\vigia-vida.ps1`"" /SC MINUTE /MO 15 /F
```

Equivale a `*/15 * * * * $BOT_DIR/bot/vigia-vida.sh`. Limite: roda na própria máquina; PC desligado não avisa.

## 14. Canário dos parsers de portal (opcional; diário 07:30)

Roda a busca do LinkedIn/Gupy **ao vivo** (2-3 requisições) e avisa no Telegram (`scripts\notificar.ps1`) se algum parser
parou de devolver dados (o portal mudou o HTML/API). Só faz sentido com a descoberta ligada (`OV_DESCOBRIR=1`).

```powershell
schtasks /Create /TN 'OportunizaVaga\CanarioFontes' `
  /TR "py `"$BOT_DIR\bot\canario-fontes.py`"" /SC DAILY /ST 07:30 /F
```

Equivale a `30 7 * * * python3 $BOT_DIR/bot/canario-fontes.py`.

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
