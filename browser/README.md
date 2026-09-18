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
