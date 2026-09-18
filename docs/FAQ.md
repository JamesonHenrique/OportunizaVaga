# FAQ

**Automatizar candidatura é permitido?**
Depende do portal. LinkedIn, Gupy, Indeed e outros **podem proibir automação** nos
Termos de Uso — sua conta pode ser suspensa. Este projeto é para estudo e automação
**pessoal**; o risco é seu. Use com moderação (1 site/rodada, pausas de 20 min+).

**Quanto custa rodar?**
R$ 0 (docs/CUSTO.md): modelos gratuitos + Vercel free + seu PC.

**Preciso do monitor?**
Não. Sem `MONITOR_URL`, o bot funciona igual — só não publica status. O monitor é
um painel de acompanhamento opcional.

**O robô inventa dados no meu nome?**
Não — essa é a regra nº 4 do prompt. Tudo vem de `bot/dados_candidato.json`;
o que falta vira `bloqueado` com o dado exato que faltou. Preencha bem o arquivo.

**Nível/idioma/stack: posso mudar?**
Sim — o repo vem com EXEMPLO Java/Spring + Angular. Adapte `dados_candidato.json`,
os TERMOS e o PRÉ-FILTRO em `bot/prompt_loop.md` ao seu perfil (docs/PROMPTS.md).

**Por que só 1 site por rodada?**
Anti-timeout (rodada cabe em ~8 min), anti-bloqueio (menos requisições/portal) e
economia de quota de modelo (pré-filtro na listagem evita abrir vaga inútil).

**Rodada diz "QUOTA_EXAUSTA"?**
Normal: todos os modelos free bateram no teto. O loop dorme (15→30→60 min) e tenta
de novo. Não mexa em nada — a volta ao preferido é automática.

**Chrome perdeu o login?**
Abra `http://127.0.0.1:9222/json/version` — se não responder, rode
`./browser/chrome-real.sh &` e logue de novo 1x. O `guardiao.sh` tenta subir sozinho.

**Lock "preso" / loop não sai do lugar?**
O guardião checa o **processo**, não só o lock, e limpa órfãos (`bot/guardiao.log`).
Se persistir: `fuser -k /tmp/oportunizavaga-loop.lock` e deixe o cron subir de novo.

**Como adiciono um site novo?**
1. Adicione em `config/sites_permitidos.json` (nas **duas** formas: `https://x` e `https://*.x`).
2. Adicione as origens no `--allowed-origins` do seu `opencode.jsonc`.
3. Inclua no rodízio (`rodizio.ordem` em `aplicadas.json`) e no prompt (URLs + termos).

**Funciona no Windows/macOS?**
Os scripts são bash (Linux testado). No macOS, adapte `stat -c %s`, `fuser` e o
caminho do Chrome. No Windows, use WSL2 (recomendado, guia Linux funciona dentro
do WSL) ou os espelhos PowerShell nativos (`bot/*.ps1`, `scripts/*.ps1`,
`browser/chrome-real.ps1` + `config/TaskScheduler.md`).

**Windows: "não é possível carregar o script porque a execução de scripts foi desabilitada" (execution policy)?**
O Windows bloqueia `.ps1` por padrão. Rode 1x como o seu usuário (não precisa de admin):
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, e execute com
`powershell -ExecutionPolicy Bypass -File bot\loop.ps1`. Nunca use `Unrestricted`
global — `RemoteSigned` no escopo do usuário basta.

**Windows: como agendo o robô sem cron (schtasks)?**
O equivalente ao `crontab.example` está em `config/TaskScheduler.md`, com comandos
prontos: guardião a cada 5 min (`/SC MINUTE /MO 5`) + no logon (`/SC ONLOGON`),
follow-up seg 09:00 (`/SC WEEKLY /D MON /ST 09:00`). Confira com
`schtasks /Query /TN 'OportunizaVaga\Guardiao'` e remova com
`schtasks /Delete /TN 'OportunizaVaga\Guardiao' /F`.

**Windows: Chrome CDP não responde em 127.0.0.1:9222?**
Suba com `powershell -ExecutionPolicy Bypass -File browser\chrome-real.ps1` e teste
com `(New-Object Net.Sockets.TcpClient).BeginConnect('127.0.0.1', 9222, $null, $null).AsyncWaitHandle.WaitOne(5000)`.
O perfil fica em `%LOCALAPPDATA%\oportunizavaga-chrome-real`. Agende as tarefas como
o **seu usuário** (não SYSTEM): o Chrome precisa abrir na sua sessão para reaproveitar
o login 1x. Se cair, `bot\guardiao.ps1` tenta subir sozinho (veja `bot\guardiao.log`).
