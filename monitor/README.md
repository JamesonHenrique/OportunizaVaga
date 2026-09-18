# Monitor (opcional)

Painel na Vercel (plano gratuito, **sem banco**) para acompanhar o robô de longe:
estado do loop, candidaturas por portal, modelos no teto, quota, terminal ao vivo.

## Como funciona

- `snapshot.mjs` lê `CANDIDATURAS_ROOT` (= `bot/` do repo: `aplicadas.json` + logs)
  e monta o retrato. Fallback sem env: o `bot/` ao lado de `monitor/`.
- `publish-status.mjs` (daemon): heartbeat a cada 15s rodando / 60s dormindo.
- `publish-once.mjs`: envio único (o `loop.sh` chama a cada mudança de estado).
- `quota-daemon.mjs`: mede 1x/h a cota dos `:free` do OpenRouter (único provider
  com API de uso) → `bot/quota-cache.json`, que o snapshot mistura no painel.
- O endpoint `/api/status` na Vercel guarda **só o último snapshot em memória**
  (custo zero); após cold start, o próximo heartbeat repõe em segundos.

## Rodar

```bash
cd monitor && npm install && npm run dev
# deploy: vercel --prod  (regions: gru1 — veja vercel.json)
MONITOR_URL=https://sua-url.vercel.app node publish-status.mjs
```

Sem `MONITOR_URL`, o bot funciona normalmente — só não publica nada.

## Rodando com Docker (demo)

Demonstração com dados de exemplo — **nunca** monta seu `bot/` real:

```bash
docker compose up monitor   # http://localhost:3000
```

O serviço `monitor` (raiz: `docker-compose.yml`) usa a imagem do `Dockerfile`
da raiz, monta só `examples/` como **read-only** (`/demo:ro`), copia
`aplicadas.example.json` para o nome esperado (`aplicadas.json`) num diretório
efêmero (`/tmp/demo`, via `CANDIDATURAS_ROOT`) e sobe `npm run dev`.
Para dados reais, rode fora do Docker (`npm run dev` acima) apontando
`CANDIDATURAS_ROOT` para o seu `bot/` local.

## Segurança

O snapshot envia contadores, eventos e caudas de log — **nunca** documentos,
CPF ou segredos. Proteja o endpoint com `MONITOR_SECRET` (header `x-monitor-secret`)
se expor o painel.
