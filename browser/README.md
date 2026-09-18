# Chrome real persistente (CDP :9222)

O robô navega num **Chrome de verdade**, não headless: login feito 1x no perfil
persiste para todas as rodadas (Gupy via Google, LinkedIn, Indeed…).

```bash
./browser/chrome-real.sh &   # abre com --remote-debugging-port=9222
curl -s http://127.0.0.1:9222/json/version   # confere se subiu
```

- Perfil em `${XDG_CONFIG_HOME:-$HOME/.config}/oportunizavaga-chrome-real`
  (**fora do git**: contém sessões logadas — nunca commite).
- `bot/guardiao.sh` sobe o Chrome sozinho se o CDP cair.
- `bot/loop.sh` e `bot/followup.sh` disputam o Chrome via `flock`
  (`/tmp/agent-chrome-9222.lock`): nunca rode dois agentes ao mesmo tempo sem o lock.
- Display: em desktop use `DISPLAY=:0`; em servidor, adapte (Xvfb ou máquina com X).

## Windows (PowerShell nativo)

```powershell
powershell -ExecutionPolicy Bypass -File browser\chrome-real.ps1
# confere: (New-Object Net.Sockets.TcpClient).BeginConnect('127.0.0.1', 9222, $null, $null).AsyncWaitHandle.WaitOne(5000)
```

- Perfil em `%LOCALAPPDATA%\oportunizavaga-chrome-real`
  (**fora do git**: contém sessões logadas — nunca commite).
- `bot/guardiao.ps1` sobe o Chrome sozinho se o CDP cair.
- `bot/loop.ps1` e `bot/followup.ps1` disputam o Chrome via lock de arquivo
  (`%TEMP%\agent-chrome-9222.lock`): nunca rode dois agentes ao mesmo tempo sem o lock.
- No Windows o Chrome abre na sua sessão de usuário: agende as tarefas do
  `config/TaskScheduler.md` como o seu usuário (não SYSTEM) para reaproveitar o login.
