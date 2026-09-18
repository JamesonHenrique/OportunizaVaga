# CUSTO — R$ 0/mês no plano gratuito

| Camada | Custo | Como |
|---|---|---|
| Modelos de IA | R$ 0 | Cascata de modelos **gratuitos** em `bot/loop.sh` (flags `USAR_*`) |
| Sites de vaga | R$ 0 | Acesso normal via browser (sua conta) |
| Monitor/painel | R$ 0 | Vercel free: sem banco, só último snapshot em memória |
| Infra local | R$ 0 | Seu PC + cron (sem servidor, sem systemd) |

## A escada de modelos (`bot/loop.sh`)

Toda rodada começa pelo primeiro modelo e cascateia ao bater no rate limit; a volta
ao preferido é automática (sem detectar recuperação nem guardar estado). O limite é
**por modelo** e transitório — o que faz cascatear valer a pena.

| Nível | Flag | Provedor / modelos |
|---|---|---|
| 1 (preferido) | — | Zen: 6 modelos free (muse-spark, nemotron, mimo, ling…) |
| 2 | `USAR_OPENROUTER=1` | OpenRouter 9 modelos `:free` (medido: `cost=0`, não consome crédito; limite é req/dia) |
| 3 | `USAR_NVIDIA=1` | NVIDIA direto (1 modelo) |
| 4 | `USAR_GROQ=1` | Groq (4 modelos, sem cartão) |
| 5 | `USAR_CEREBRAS=1` | Cerebras (2 modelos) |
| 6 | `USAR_HF=1` | Hugging Face serverless (3 modelos) |
| 7 (último) | `USAR_COPILOT=0` | GitHub Copilot (consome premium requests — **desligado por padrão**, ligue se o resto secar) |

Todos rodam por API: **RAM local = zero**.

## Backoffs (economia de rodada = economia de quota)

- Rodada OK com vaga nova → dorme 20 min.
- Rodada OK sem vaga nova → backoff 1h → 2h → 4h… (sem teto, reseta ao achar vaga).
- Todos os modelos no teto → 15 min → 30 min → 1h.
- Falhas → exponencial 5/10/20 min (teto 30 min).

## Quota medida vs. inferida

- **OpenRouter**: único com API de cota (`quota-daemon.mjs` mede 1x/h → `quota-cache.json`).
- **Demais providers**: sem endpoint de uso — o painel infere "bateu no teto hoje"
  contando eventos de cascata no `loop.log`.
