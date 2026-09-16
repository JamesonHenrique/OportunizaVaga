# AplicaBot 🤖🇧🇷

Robô open-source de **candidaturas automáticas para vagas JR/trainee remotas no Brasil**, rodando no seu próprio PC a **custo zero** (modelos de IA gratuitos + sites de vaga BR).

> ⚠️ **Aviso legal:** automatizar candidaturas pode violar os Termos de Uso de LinkedIn, Gupy, Indeed e outros portais. Este código é publicado para estudo e automação pessoal; **você assume o risco de bloqueio/suspensão das suas contas** ao usá-lo. Os autores não se responsabilizam por contas suspensas, vagas perdidas ou qualquer dano decorrente do uso.

## Como funciona

```
cron (5min) ──▶ guardiao.sh ──┬──▶ loop.sh ──▶ opencode run (modelo grátis) ──▶ Chrome real (CDP :9222)
                              │         │              │
                              │         │              └──▶ 1 site do rodízio por rodada (Indeed, LinkedIn,
                              │         │                   Gupy, Programathor, Trampardecasa, GeekHunter,
                              │         │                   Remotar, Infojobs, Vagas)
                              │         └──▶ estado em aplicadas.json (NUNCA na sessão do modelo)
                              │
                              ├──▶ Chrome com CDP (sobe sozinho se cair)
                              └──▶ publisher do monitor (opcional, repo separado)
```

- **1 site por rodada**, rodízio circular, dorme 20min entre rodadas.
- **Só JR/trainee + remoto + ≤14 dias** (janela configurável no prompt).
- **Nunca inventa dados:** tudo vem de `dados_candidato.json`; o que falta vira `bloqueado` com o motivo.
- **Anti-ruído:** descarte de listagem vira contador, não polui bloqueios.
- **Cascata de modelos gratuitos:** se um bater no rate limit, tenta o próximo.
- **Follow-up semanal** (segundas): recheca o status das vagas aplicadas.

## Estrutura

```
aplicabot/
├── bot/
│   ├── loop.sh                  # loop principal (uma rodada = uma sessão nova do modelo)
│   ├── guardiao.sh              # supervisor via cron: loop + Chrome (+ publisher se usar monitor)
│   ├── followup.sh              # rotina semanal de status das candidaturas
│   ├── monitor-keepalive.sh     # mantém o publisher do painel no ar (opcional)
│   ├── prompt_loop.md           # regras e passo a passo de cada rodada (o "cérebro")
│   ├── prompt_followup.md       # prompt da rotina semanal
│   ├── prompt_perfil_gupy.md    # manutenção avulsa do perfil Gupy
│   ├── sites_permitidos.json    # allowlist de domínios BR (espelha o bloqueio do browser)
│   ├── dados_candidato.example.json  # COPIE para dados_candidato.json e preencha
│   └── aplicadas.example.json        # COPIE para aplicadas.json (estado inicial vazio)
└── docs/
    └── (seus guias aqui)
```

## Setup (Linux)

1. Dependências: `bash`, `python3`, `node`, [opencode](https://opencode.ai) com provider gratuito, Google Chrome, `flock`, `fuser`.
2. `cp bot/dados_candidato.example.json bot/dados_candidato.json` e **preencha com seus dados reais**.
3. `cp bot/aplicadas.example.json bot/aplicadas.json`.
4. Ajuste `bot/prompt_loop.md` ao seu perfil (stack, nível, pretensão).
5. Configure o browser com a allowlist de `sites_permitidos.json` (o MCP Playwright aceita `--allowed-origins`).
6. Suba o Chrome com remote debugging: `chrome --remote-debugging-port=9222`.
7. Teste uma rodada manual: `./bot/loop.sh` (Ctrl+C após a primeira rodada ok).
8. Cron:
   ```
   @reboot /seu/caminho/bot/guardiao.sh
   */5 * * * * /seu/caminho/bot/guardiao.sh
   0 9 * * 1 /seu/caminho/bot/followup.sh >> /seu/caminho/bot/followup.log 2>&1
   ```

## Segurança — LEIA ANTES DE COMMITAR

**NUNCA** commite: `dados_candidato.json`, `aplicadas.json`, CVs em PDF, `cron.env`, `*.log`, `logs/`, perfil do Chrome, backups `*.bak-*`. O `.gitignore` já bloqueia tudo isso — confira com `git status` antes de cada push. Vazou secret? **Rode a rotação imediatamente** (troque a chave/senha no provedor) — remover do git não apaga o histórico.

## Custo

R$ 0 com modelos gratuitos (testado com a cadeia de modelos `:free` do opencode). Sem banco, sem servidor: o estado é um JSON no disco.

## Licença

MIT — veja `LICENSE`.
