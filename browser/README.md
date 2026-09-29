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
- `bot/loop.sh`, `bot/followup.sh` e `bot/gmail-status.py` disputam o Chrome pelo protocolo único de
  `bot/chrome-lock.sh NOME alta|normal ESPERA_S -- CMD` (`flock` em `/tmp/agent-chrome-9222.lock`):
  nunca rode dois agentes ao mesmo tempo sem o lock. Jobs curtos (`alta`: follow-up, Gmail) marcam a vez com
  uma flag `/tmp/agent-chrome-9222.prio.NOME`; o loop (`normal`) **cede** a rodada (rc 76; o loop mapeia p/ 75 =
  "Chrome ocupado") em vez de fazê-los esperar 15 min. Códigos: 75 = timeout do lock, 76 = cedeu, 2 = uso.
  Log em `bot/logs/chrome-lock.log`.
- Display: em desktop use `DISPLAY=:0`; em servidor, adapte (Xvfb ou máquina com X).

## Windows (PowerShell nativo)

```powershell
powershell -ExecutionPolicy Bypass -File browser\chrome-real.ps1
# confere: (New-Object Net.Sockets.TcpClient).BeginConnect('127.0.0.1', 9222, $null, $null).AsyncWaitHandle.WaitOne(5000)
```

- Perfil em `%LOCALAPPDATA%\oportunizavaga-chrome-real`
  (**fora do git**: contém sessões logadas — nunca commite).
- `bot/guardiao.ps1` sobe o Chrome sozinho se o CDP cair.
- `bot/loop.ps1` e `bot/followup.ps1` disputam o Chrome via `bot\chrome-lock.ps1` (lock de arquivo
  `%TEMP%\agent-chrome-9222.lock` + flags de prioridade, mesmo protocolo do `.sh`):
  nunca rode dois agentes ao mesmo tempo sem o lock. Uso avulso:
  `powershell -File bot\chrome-lock.ps1 meujob alta 900 -- node meu-script.mjs`.
- No Windows o Chrome abre na sua sessão de usuário: agende as tarefas do
  `config/TaskScheduler.md` como o seu usuário (não SYSTEM) para reaproveitar o login.
