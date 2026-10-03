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
  Limitações conhecidas: carimbos em hora local com offset -03:00 documentado (o Node no
  Windows ignora TZ IANA). O watchdog de stall/early-abort é espelhado, mas a leitura do log
  interno do opencode é fail-open (sem log, só vale o critério de stall). Detalhes no cabeçalho
  de `bot/loop.ps1`.

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
cp examples/cv_base.example.md bot/cv_base.md
cp examples/aplicadas.example.json bot/aplicadas.json
```

Edite `bot/dados_candidato.json`: nome, e-mail, stack real (`experiencia.tecnologias`),
similares (`experiencia.stacks_similares`), pretensão (`SEU_VALOR_BASE`),
respostas padrão de formulário. **Campo vazio = o robô registra "bloqueado" em vez
de inventar.** Edite `bot/cv_base.md` com seu currículo mestre (é dele que sai o PDF
por vaga da regra `c1`; ver `docs/PROMPTS.md`). Veja `docs/PROMPTS.md` para adaptar
`bot/prompt_loop.md` ao seu stack.

## Múltiplos perfis

Exemplos em `config/perfis/` para níveis e áreas diferentes:

| Arquivo | Níveis | Área |
|---|---|---|
| `junior-backend.example.json` | trainee, júnior | tecnologia (backend) |
| `pleno-frontend.example.json` | pleno | tecnologia (frontend) |
| `pleno-dados.example.json` | pleno, sênior | tecnologia (dados e BI) |
| `senior-techlead.example.json` | sênior, especialista, líder | tecnologia (liderança técnica) |
| `estagio-qa.example.json` | estágio, trainee | tecnologia (QA) |
| `pleno-marketing.example.json` | pleno, sênior | marketing digital |
| `pleno-vendas.example.json` | pleno, especialista | vendas e comercial |
| `pleno-saude.example.json` | pleno, especialista | saúde (enfermagem, nutrição, fisioterapia) |
| `pleno-administrativo.example.json` | pleno | administrativo e financeiro |
| `estagio-direito.example.json` | estágio | jurídico |

Estrutura: `nome_perfil`, `niveis[]`, `area`, `termos[]`, `pular_tipos[]` e, opcionais,
`modelos[]` (`remoto`, `hibrido`, `presencial`; padrão só remoto), `cidades[]` (onde híbrido/presencial
vale), `experiencia_max_anos` e `sites_pular` (schema em `config/perfil.schema.json`).
O `./scripts/setup-wizard.sh` já gera esse arquivo por perguntas.

```bash
cp config/perfis/senior-techlead.example.json bot/perfil.json  # ou qualquer outro
# edite niveis/area/termos/pular_tipos: o loop injeta tudo no prompt ({{NIVEIS}}, {{AREA}}, {{TERMOS}}...)
python3 bot/perfil_render.py info bot/perfil.json  # confere o que o robô vai aceitar/recusar
```

Aponte o perfil no loop via `$BOT_PERFIL` (caminho do JSON do perfil ativo) ou
deixe `bot/perfil.json` no lugar. O loop resolve o perfil sozinho e cria um
estado isolado em `bot/state/<perfil>/aplicadas.json` — cada perfil mantém o
próprio rodízio, bloqueados e candidaturas, sem misturar histórico.

Para validar o plano sem se candidatar:

```bash
BOT_PERFIL=config/perfis/junior-backend.example.json ./bot/dry-run.sh --json
./bot/dry-run.sh --json --site indeed       # plano só do Indeed
OV_RECONHECIMENTO=1 ./bot/dry-run.sh --json # modo reconhecimento (não aplica)
```

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

Detalhes em `browser/README.md`. A blocklist de domínios está em
`config/sites_permitidos.json` (`bloqueados_no_browser`) e deve espelhar o
`--blocked-origins` do seu `~/.config/opencode/opencode.jsonc` (modelo em
`config/opencode.jsonc.example`).

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

Antes de ligar o loop real, simule o plano sem se candidatar (só lê arquivos —
não abre browser, não aplica em nada):

```bash
./bot/dry-run.sh            # plano humano: todos os sites, termos e URLs
./bot/dry-run.sh --json    # saída máquina (sites, perfil, limites, telemetria)
./bot/dry-run.sh --json --site indeed
./bot/dry-run.sh --json --reconhecimento
```

Windows (PowerShell nativo):

```powershell
powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1
powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1 -json
powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1 -json -Site indeed
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

## Acompanhando o resultado (funil)

Depois de algumas rodadas, veja em que etapa as candidaturas estão:

```bash
./scripts/funnel.sh                 # vistas → aplicadas → respondidas → convites → entrevistas
./scripts/funnel.sh --csv           # exporta CSV (planilha / relatório)
./scripts/funnel.sh --markdown      # exporta tabela Markdown
./scripts/funnel.sh --json          # saída máquina (contagens, taxas e diagnósticos)
```

As etapas são cumulativas (entrevista ⊆ convites ⊆ respondidas ⊆ aplicadas) e a taxa
de cada uma é contra a etapa imediatamente anterior. "Respondeu" = o status saiu de
`enviada`; `sem_resposta` é ausência de resposta e não entra. `encerrada` e
`sem_retorno_verificavel` ficam de fora (não dá para saber se houve retorno) e saem
como diagnóstico, junto com os status desconhecidos.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\funnel.ps1
powershell -ExecutionPolicy Bypass -File scripts\funnel.ps1 -Csv funil.csv
```

A regra de contagem vive em [`bot/funil.py`](../bot/funil.py) — os dois espelhos
`.sh`/`.ps1` só repassam flags, então não divergem.

Exit 0 = essencial ok (`[??]` são só avisos); exit 1 = falta algo essencial
(veja os itens `[FALHA]`). Validação fina dos JSONs contra os schemas em
`config/`: `bash scripts/validate.sh` (ou `scripts\validate.ps1`).
