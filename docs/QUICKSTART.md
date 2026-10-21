# QUICKSTART — do zero à primeira rodada

Este guia leva você de máquina recem-formatada até o robô rodando a primeira
candidatura. Antes de tudo, identifique **o seu perfil** — o caminho muda pouco,
mas a ordem e o nível de explicação mudam bastante:

| Você é... | Tem terminal? | O que pular | Sua seção |
|---|---|---|---|
| **Leigo** (nunca abriu um terminal de propósito) | Não | Nada — este guia explica cada comando | **Seções 1, 2... 8, na ordem** |
| **Usuário básico** (roda `cd`, `sudo apt`, copia/cola sem medo) | Sim | As explicações "o que é isso"; atenção só nos avisos | **Seção "Caminho rápido" + seção 5 (config do opencode)** |
| **Dev** (vive no terminal) | Sim | Quase tudo | **Caminho rápido + minutos 5 e 6 (MCP e plugin da V2)** |

> ⚠️ **Antes de começar, leia:** automatizar candidaturas pode violar os Termos
> de Uso dos portais (LinkedIn, Gupy, Indeed...) e você assume o risco de
> bloqueio/suspensão das suas contas. Veja [`USO-ETICO.md`](USO-ETICO.md).
> O robô nunca inventa dados, nunca envia nada além das candidaturas que você
> configurou e guarda tudo no seu PC — sem nuvem além do monitor opcional.

**Pré-requisitos de verdade** (o que o código exige, não o que "seria bom ter"):

| Ferramenta | Versão mínima | Por quê | Como instalar (Linux/WSL) |
|---|---|---|---|
| Bash + utilitários core | bash 4+ | loop, guardião, adaptadores (`flock`, `timeout`) | já vem no Linux/WSL |
| Python | **3.10+** | `bot/*.py` usam `match/case` (sintaxe 3.10+): CV por vaga, validação, estado | Ubuntu 22.04+ já traz; `apt install python3` |
| Node.js | 20+ | o loop usa o publisher do monitor (`publish-once.mjs`) em cada rodada — **é obrigatório pro robô**, não só pro painel | Veja seção 1 |
| Google Chrome / Chromium | atual | navegador real controlado via CDP `:9222` | Veja seção 1 |
| [opencode](https://opencode.ai) | 2.x | o cérebro das rodadas (roda os modelos grátis) | Veja seção 1 |
| jq | qualquer | só o `setup-wizard.sh` usa (venientemente ignorável se você editar JSON à mão) | `sudo apt install jq` |
| poppler-utils (`pdftotext`) | qualquer | opcional: medir a cobertura ATS do CV | `sudo apt install poppler-utils` |
<!-- Caminhos Windows: Chrome = instalador normal; veja espelhos .ps1 (seção 4 e 6). -->

## Caso 1 — Leigo: o guia com tudo explicado 🐣

> Siga **na ordem**. Cada passo termina com uma verificação — cole o comando e
> compare com a saída esperada. Se travou, vá para **Primeiros socorros** no fim.

### Seção 1 — instale as ferramentas

Abra o terminal (Linux: busque "Terminal"; WSL2 no Windows: menu Iniciar → Ubuntu).

Cole bloco por bloco, esperando terminar antes do próximo:

```bash
# Chrome (navegador real que o robô controla)
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# Python 3.10+ (checagens e geradores do robô) + poppler (opcional, ATS)
sudo apt update && sudo apt install -y python3 python3-pip poppler-utils jq
python3 -m pip install --user reportlab websocket-client

# Node 20+ (o robô publica o status da rodada — obrigatório, não é só p/ painel)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# opencode (o cérebro que roda os modelos grátis)
curl -fsSL https://opencode.ai/install | bash
```

**Verificação** (cole; o que deve aparecer está ao lado):

```bash
google-chrome-stable --version   # qualquer número >= 115 ok
python3 --version                # Python 3.10.x ou maior
node --version                   # v20 ou maior
ls ~/.opencode/bin/opencode      # caminho do binário do opencode
```

> Se `python3 --version` mostrou 3.9 ou menos (Ubuntu 20.04), atualize o sistema
> ou use outra máquina — os scripts usam sintaxe que **exige** 3.10+.
> Se `node` não for achado, feche e reabra o terminal (o PATH só é relido assim).

### Seção 2 — pergunte ao robô o que está faltando

```bash
git clone https://github.com/JamesonHenrique/OportunizaVaga ~/oportunizavaga
cd ~/oportunizavaga
./scripts/setup.sh     # copia exemplos, valida dependências, imprime o cron sugerido
./bot/doctor.sh        # checklist de ambiente com dicas por item
```

No `doctor.sh`, você quer o final `doctor: essencial OK`. Imprimiu `[FALHA]`?
Cada linha já traz a correção. Se você vê `command not found` em qualquer
comando acima, veja **Primeiros socorros** (fim desta página).

### Seção 3 — seus dados (30 min, a parte mais importante)

O robô não sabe nada sobre você ainda: preencha por **perguntas** (recomendado)
ou editando o arquivo:

```bash
sudo apt install -y jq      # o wizard usa jq
./scripts/setup-wizard.sh   # pergunta nome, e-mail, stack, pretensão, portais...
```

Ou, na mão:

```bash
cp examples/dados_candidato.example.json bot/dados_candidato.json
cp examples/cv_base.example.md bot/cv_base.md
cp examples/aplicadas.example.json bot/aplicadas.json
# edite os 3 arquivos (gedit bot/dados_candidato.json)
```

Regras de ouro:

- **Campo vazio no JSON = o robô registra "bloqueado" em vez de inventar.** É
  de propósito: prefira deixar em branco a mentir.
- **Nunca** commite nada disso: `bot/dados_candidato.json`, `bot/cv_base.md`,
  `bot/aplicadas.json` estão no `.gitignore` — não desative.
- Em `experiencia.tecnologias` vá de dado real (ex.: `Python, SQL, Excel`),
  candidatos a `experiencia.stacks_similares` são o que você domina por
  vizinhança (ex.: você conhece Laravel, entra Django), não chutes.

### Seção 4 — chave de modelos grátis (5 min)

O robô começa num modelo gratuito sem chave (Zen). Para ganhar uma segunda
opção diária de rate limit, crie uma conta em [openrouter.ai](https://openrouter.ai)
e guarde a chave **fora do repo**:

```bash
mkdir -p ~/.config/opencode && touch ~/.config/opencode/cron.env
chmod 600 ~/.config/opencode/cron.env
echo 'OPENROUTER_API_KEY=sua-chave-aqui' >> ~/.config/opencode/cron.env
```

Sem isso o robô funciona igual: ele só perde a 2ª opção da cascata.

### Seção 5 — ensine o opencode a falar com o navegador (o passo que mais trava!)

O robô usa **duas camadas**: o opencode (modelos) controla um Chrome de verdade
pelo protocolo CDP. Essas duas camadas precisam de um arquivo de configuração
copiado para `~/.config/opencode/opencode.jsonc`. Copia e termina:

```bash
mkdir -p ~/.config/opencode
cp config/opencode.jsonc.example ~/.config/opencode/opencode.jsonc
```

E o plugin da versão 2 do opencode (explicação na seção [Caso 3](#caso-3--dev--cada-detahle))
— **este é o passo mais esquecido de todos e o erro nº 1 de primeira rodada**:

```bash
mkdir -p ~/.config/opencode/plugins
cp config/opencode-plugins/espera-mcp.ts ~/.config/opencode/plugins/
```

Alternativa sem config manual (não recomendado p/ iniciante): `OV_OPENCODE_ENXUTO=1`
faz o próprio robô gerar um config nativo da V2 em cada rodada.

### Seção 6 — o navegador (login 1x, vale para todos os sites)

```bash
./browser/chrome-real.sh &    # & = roda em segundo plano
```

- Abre um Chrome dedicado, com nota do filtro: um perfil **só do robô**
  (`~/.config/oportunizavaga-chrome-real`), fora do seu Chrome pessoal.
- **Logue 1x** em cada portal que quer usar (LinkedIn, Gupy...): abra abas
  normais e finalise o login à mão. O perfil guarda as sessões — depois o robô
  reusa tudo sem digitar senha.
- Alterou algo? A blocklist de agregadores gringos fica em `config/sites_permitidos.json`.

> **Aviso ético:** o robô respeita limite e cadência de pedidos, mas automação
> ainda pode resultar em bloqueio de conta pelo portal. Leia
> [`USO-ETICO.md`](USO-ETICO.md). Assuma o risco dos termos de uso.

### Seção 7 — ensaio geral: doctor + dry-run (nada é enviado)

```bash
./bot/doctor.sh        # precisa terminar em "essencial OK"
./bot/dry-run.sh       # imprime o plano da rodada; lê arquivos, não se candidata, não abre browser
```

Leia a saída do dry-run: são os sites e URLs exatos que a rodada real vai
visitar. Corrigiu algo? Rode de novo. Satisfeito? Siga.

### Checklist antes da 1ª rodada real ✅

Marque todos:

- [ ] `doctor.sh` termina em `essencial OK` (exit 0)
- [ ] `dry-run.sh` mostra sites/URLs que fazem sentido p/ seu perfil
- [ ] Chrome do robô aberto com CDP `:9222` e login feito nos portais
- [ ] `~/.config/opencode/opencode.jsonc` existe (cópia do example)
- [ ] Plugin `espera-mcp.ts` em `~/.config/opencode/plugins/` (opencode 2.x)
- [ ] `bot/dados_candidato.json` e `bot/cv_base.md` preenchidos
- [ ] Perfil `bot/perfil.json` no nível/área certa (ou o default histórico)

### Seção 8 — a primeira rodada real (e como parar dela)

```bash
./bot/loop.sh
```

O que acontece: uma rodada abre uma sessão nova do opencode no perfil ativo,
visita **1 site por rodada** (rodízio circular, 20 min entre rodadas), aplica
nas vagas compatíveis e preenche `bot/aplicadas.json` + `bot/loop.log`.

Para **parar**: `Ctrl+C` no terminal encerra o loop; nenhuma candidatura fica
pela metade (o robô marca "desconhecida" só se o navegador caiu no meio do envio —
veja o follow-up semanal). Depois da 1ª rodada "ok", você já pode automatizar.

### Seção 9 — deixe o robô rodando sozinho

```bash
crontab -e          # abra o editor; cole o conteúdo de config/crontab.example
                    # ajustando BOT_DIR para /home/VOCE/oportunizavaga
```

O cron sobe o guardião a cada 5 min (`bot/guardiao.sh`): se o loop ou o Chrome
caírem, ele sobe de novo. O follow-up semanal atualiza status às segundas 09:00.

*(Windows? Use os `schtasks` prontos de `config/TaskScheduler.md` — seção
Windows do Caso 2 abaixo.)*

### Caso 1: checklist de tudo que instalou

Chrome + Python 3.10+ + Node 20+ (via nodesource) + opencode + jq +
`reportlab`/`websocket-client` (pip) + poppler + o clone do repo + config +
plugin. Só isso. Tempo típico se nada der errado: **~20–35 min**.

## Caso 2 — Usuário básico: o caminho rápido 🚶

```bash
# 0. Ferramentas (WSL2/Ubuntu 22.04+)
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb python3 python3-pip poppler-utils jq
python3 -m pip install --user reportlab websocket-client
node --version || { curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -; sudo apt install -y nodejs; }
curl -fsSL https://opencode.ai/install | bash
ls ~/.opencode/bin/opencode   # tem que existir

# 1. Clonar + setup (não precisa fork: você está só rodando, não contribuindo)
git clone https://github.com/JamesonHenrique/OportunizaVaga ~/oportunizavaga
cd ~/oportunizavaga && ./scripts/setup.sh

# 2. Seus dados (wizard interativo; ou copie os .example e edite)
./scripts/setup-wizard.sh

# 3. Chave grátis opcional (OpenRouter) — fora do repo, chmod 600
mkdir -p ~/.config/opencode && touch ~/.config/opencode/cron.env && chmod 600 ~/.config/opencode/cron.env
echo 'OPENROUTER_API_KEY=sua-chave' >> ~/.config/opencode/cron.env

# 4. Config + plugin do opencode (o passo mais esquecido!)
cp config/opencode.jsonc.example ~/.config/opencode/opencode.jsonc
mkdir -p ~/.config/opencode/plugins
cp config/opencode-plugins/espera-mcp.ts ~/.config/opencode/plugins/

# 5. Navegador + login manual nos portais
./browser/chrome-real.sh &

# 6. Ensaio geral, depois rodada real
./bot/doctor.sh          # essencial OK?
./bot/dry-run.sh         # plano sem risco
./bot/loop.sh            # Ctrl+C após a primeira rodada "ok"

# 7. Automatizar
crontab -e               # cole config/crontab.example, ajustando BOT_DIR
```

**Windows — saiba qual caminho:**

- **WSL2 (recomendado):** siga o bloco acima dentro do Ubuntu. Chrome pode ficar
  no Windows (CDP `:9222` funciona igual); use `chromium` do WSL só se preferir.
- **PowerShell nativo (alternativo):** espelhos `.ps1` com a mesma lógica —
  `scripts\setup.ps1`, `scripts\setup-wizard.ps1`, `browser\chrome-real.ps1`,
  `bot\doctor.ps1`, `bot\loop.ps1`. Setup pip: `python -m pip install reportlab websocket-client`. Limitações: TZ IANA ignorada pelo Node no Windows (carimbos
  em hora local), leitura de log interno do opencode fail-open. Detalhes no
  cabeçalho de `bot/loop.ps1`; agendamento em `config/TaskScheduler.md`.

## Caso 3 — Dev: cada detalhe 🔧

```bash
# 1 linha (Linux/macOS/WSL2): clone em $HOME/oportunizavaga + setup.sh
curl -fsSL https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.sh | bash

# ou com destino próprio / modo manual
curl -fsSL https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.sh -o install.sh && bash install.sh ~/meu-bot
# equivalente Windows (PowerShell):
irm https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.ps1 | iex
```

O que o instalador faz (e não faz): clona o repo, roda `scripts/setup.sh`
(copia JSONs de exemplo para os arquivos de estado em `bot/`, valida
dependências, `bash -n` nos scripts críticos). **Nunca** sobrescreve JSON
existente (sai `[pq] mantido`), nunca faz commit, nunca agenda nada por conta
própria — cron/Task Scheduler ficam por sua conta após o dry-run.

Detalhes valentes se você mexe:

- **Config opencode:** `config/opencode.jsonc.example` → `~/.config/opencode/opencode.jsonc`
  define model padrão (Zen), `small_model` e os MCPs. O **MCP `playwright-chrome-real`**
  conecta ao Chrome do robô: `npx -y @playwright/mcp --cdp-endpoint http://127.0.0.1:9222`
  + `--blocked-origins` espelhado na blocklist de `config/sites_permitidos.json`.
- **OpenCode 2 dispara a 1ª requisição ao modelo antes do MCP conectar** → a
  rodada começaria sem `browser_*` e falharia com `tool not found`. O plugin
  `config/opencode-plugins/espera-mcp.ts` copiado para `~/.config/opencode/plugins/`
  segura o 1º prompt até o MCP emergir (45 s de desistência). Copie e pronto.
- **Escada de modelos é do robô, não do opencode:** dentro de `bot/loop.sh`,
  com o modelo corrente disponível, o loop faz **cascata automática** —
  Zen → USAR_OPENROUTER=1 → NVIDIA → Groq → Cerebras → HF — ao bater rate
  limit, e **volta ao preferido sozinho** quando a cota zera. Você **não**
  precisa trocar à mão com `omodel`. A comparação dos modelos vive em
  `docs/MODELOS.md` (`eval-modelos` testa as opções). `USAR_OPENROUTER=1`
  é o switch principal (com `OPENROUTER_API_KEY=` em ~/.config/opencode/cron.env).
- **Perfil personalizado:** `bot/perfil.json` ← copie de `config/perfis/*.json`
  (junior-backend, pleno-dados, senior-techlead, estagio-qa, pleno-marketing,
  pleno-saude, pleno-administrativo, estagio-direito...). O loop injeta
  `{{NIVEIS}}`, `{{AREA}}`, `{{TERMOS}}`... no prompt e cria estado isolado em
  `bot/state/<perfil>/`. Confirme com `python3 bot/perfil_render.py info bot/perfil.json`.
- **Dry-run com perfil específico:** `BOT_PERFIL=config/perfis/junior-backend.example.json ./bot/dry-run.sh --json`
  · `--site indeed` isola 1 adaptador · `--reconhecimento` pontua mas não candidata.
- **TZ/fuso:** o loop fixa `TZ=America/Fortaleza` por legado — sobrescreva por
  rodada com `OV_TZ=America/Sao_Paulo ./bot/loop.sh` (ou fixe no `cron.env`).
- **Validação de schema:** `bash scripts/validate.sh`; **estado:** `python3 bot/estado.py resumo`;
  **funil:** `./scripts/funnel.sh --csv`.
- **Contribuição:** `CONTRIBUTING.md`, [`ADAPTERS.md`](ADAPTERS.md) e os
  testes (`tests/test_*.sh`, Pester nos espelhos `.ps1`). O CI roda `shellcheck`,
  `bash -n`, Pester e testes Python de tudo que está no `git ls-files`.

## Seção 10 — Monitor (opcional, todo perfil)

Painel Next.js que publica o status das rodadas em tempo real (Vercel free,
sem banco, telemetria agregada por padrão):

```bash
cd monitor && npm install && npm run dev   # http://localhost:3000
# ou: npm run demo (dados fictícios) / deploy na Vercel (monitor/README.md)
export MONITOR_URL=https://sua-url.vercel.app   # aponte o bot pra ele
```

Sem `MONITOR_URL`, o robô funciona normalmente — só não publica status.
O `monitor/` é a **única** peça que exige Node moderno além do básico (a
instalação padrão do monitor já pede Node 20+ para o Next).

## Seção 11 — Funil

Depois de algumas rodadas, meça o retorno: `./scripts/funnel.sh` (com
`--csv`/`--markdown`/`--json`). Vista → aplicada → respondida → convite →
entrevista, com taxas contra a etapa anterior. Detalhes: [`README.md`](../README.md).

## Primeiros socorros 🩹

Erros mais comuns de primeira instalação, em ordem de frequência:

| Erro que você vê | Causa | Correção |
|---|---|---|
| `command not found: node` / `: python3` / `: git` | ferramenta não instalada **ou** terminal reaberto sem recarregar o PATH | instale (tabela de pré-requisitos) e feche/reabra o terminal |
| `opencode nao encontrado em $HOME/.opencode/bin/opencode` | instalador do opencode não rodou ou `~/.opencode/bin` não está no PATH | rode o instalador de novo; no cron, o loop cuida do PATH sozinho |
| `ERRO: node nao encontrado (fnm ausente e 'node' nao esta no PATH)` | Node veio do fnm mas o alias `default` não existe | recrie o alias do fnm ou instale via nodesource/apt (seção 1) |
| `tool not found: browser_*` na 1ª rodada (opencode 2.x) | plugin `espera-mcp.ts` ausente em `~/.config/opencode/plugins/` | `mkdir -p ~/.config/opencode/plugins && cp config/opencode-plugins/espera-mcp.ts ~/.config/opencode/plugins/` |
| Chrome abre e CDP falha / doctor avisa "CDP 9222 inacessível" | seu Chrome particular está aberto com o mesmo perfil, sem CDP | feche o Chrome particular e rode `./browser/chrome-real.sh &` de novo; o guardião sobe sozinho se cair |
| `wizard` trava/"jq não encontrado" | jq ausente | `sudo apt install jq` |
| `Failed to parse JSON` / candidaturas todas "bloqueado" | `bot/dados_candidato.json` ou `bot/perfil.json` inválido | `bash scripts/validate.sh` aponta o arquivo e a linha; campo vazio é normal (vira "bloqueado", não erro) |
| Logs e datas com fuso errado | TZ fixa em America/Fortaleza por padrão | `OV_TZ=America/Sao_Paulo ./bot/loop.sh` (ou fixe no `cron.env` / no cron) |

O `./bot/doctor.sh` valida **tudo** o que esta página pede (versões, CDP,
JSONs, config do opencode, plugin, segredos fora do git, libs Python, disco,
estado). Dúvida que não seja erro de instalação: [`FAQ.md`](FAQ.md).
Saída do doctor colável em issue: copie do título para o fim e confirme que
não há dados pessoais no trecho.
