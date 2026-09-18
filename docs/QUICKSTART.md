# QUICKSTART — do zero à primeira rodada em ~20 min

> Você precisa de: Linux, Google Chrome, Node 20+, Python 3, [opencode](https://opencode.ai)
> com algum provider gratuito configurado, e uma conta Google (p/ Gupy/LinkedIn).

## 1. Clone e setup

```bash
git clone <sua-fork> oportunizavaga && cd oportunizavaga
./scripts/setup.sh
```

O setup copia os exemplos, valida dependências e imprime o crontab sugerido.

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

```bash
touch ~/.config/opencode/cron.env && chmod 600 ~/.config/opencode/cron.env
# Ex.: OPENROUTER_API_KEY=... (só se USAR_OPENROUTER=1 em bot/loop.sh)
```

## 4. Browser

```bash
./browser/chrome-real.sh &   # CDP em :9222; faça login 1x nos sites (vale p/ tudo)
```

Detalhes em `browser/README.md`. A allowlist de domínios está em
`config/sites_permitidos.json` e deve espelhar o `--allowed-origins` do seu
`~/.config/opencode/opencode.jsonc` (modelo em `config/opencode.jsonc.example`).

## 5. Teste manual (1 rodada)

```bash
./bot/loop.sh   # Ctrl+C após a primeira rodada "ok" — confira bot/loop.log e aplicadas.json
```

## 6. Automação (cron)

```bash
crontab -e   # cole o conteúdo de config/crontab.example, ajustando BOT_DIR
```

- `bot/guardiao.sh` (`*/5` + `@reboot`): mantém loop + Chrome de pé.
- `bot/followup.sh` (seg 09:00): atualiza o status das vagas aplicadas.
- `scripts/monitor-keepalive.sh` (opcional): heartbeat do painel `monitor/`.

## 7. Monitor (opcional)

```bash
cd monitor && npm install && npm run dev   # ou deploy na Vercel (veja monitor/README.md)
export MONITOR_URL=https://sua-url.vercel.app
```

Sem `MONITOR_URL`, o bot funciona normalmente — só não publica status.
