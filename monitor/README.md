# Monitor (opcional)

Painel Next.js (Vercel plano gratuito, **sem banco**) para acompanhar o robô de longe.
De cima para baixo, ele responde três perguntas antes de mostrar qualquer detalhe:

1. **O robô está vivo?** Faixa de status fixa, com um selo por loop (rodando, em pausa,
   trocando de modelo, parado) e o último heartbeat.
2. **Enviou hoje?** Candidaturas do dia em destaque e gráfico dos últimos 14 dias.
3. **Precisa de você?** Só o que exige ação humana: cadastro quebrado, dado faltando
   (ex.: CPF), vaga para retentar, dias sem envio, PC sem sinal.

Embaixo ficam os KPIs e o detalhe em abas: **Candidaturas · Bloqueios · Robô** (terminal,
linha do tempo, diagnóstico, modelos, rendimento e saúde do rodízio). Tema claro e escuro.

## Como funciona

- `snapshot.mjs` lê `CANDIDATURAS_ROOT` (= `bot/` do repo: `aplicadas.json` + logs)
  e monta o retrato. Fallback sem env: o `bot/` ao lado de `monitor/`.
- `publish-status.mjs` (daemon): heartbeat a cada 15s rodando / 60s dormindo.
- `publish-once.mjs`: envio único (o `loop.sh` chama a cada mudança de estado).
- `quota-daemon.mjs`: mede 1x/h a cota dos `:free` do OpenRouter (único provider
  com API de uso) → `bot/quota-cache.json`, que o snapshot mistura no painel.
- `app/api/status/route.js` guarda **só o último snapshot em memória** (custo zero);
  após cold start, o próximo heartbeat repõe em segundos. Sem nenhum POST ainda, ela
  usa, nesta ordem: a **demo** (`MONITOR_DEMO=1`) ou, fora da Vercel, a **leitura
  direta do disco** (`snapshot.mjs`), então `npm run dev` funciona sem o publisher.
- `demo.mjs`: dados **fictícios** (empresas inventadas, datas relativas a agora).

## Rodar

```bash
cd monitor && npm install
npm run demo       # http://localhost:3000 com dados fictícios
npm run dev        # lê o seu bot/ direto do disco (CANDIDATURAS_ROOT opcional)
```

Deploy na Vercel (Root Directory = `monitor`, região `gru1` em `vercel.json`):

```bash
vercel --prod
MONITOR_URL=https://sua-url.vercel.app MONITOR_SECRET=... node publish-status.mjs
```

Sem `MONITOR_URL`, o bot funciona normalmente — só não publica nada.

### Variáveis

| Variável | Onde | Para quê |
| --- | --- | --- |
| `MONITOR_URL` | PC | URL do painel que recebe o heartbeat |
| `MONITOR_SECRET` | PC + Vercel | exige `x-monitor-secret` no POST; no GET, sem ele o painel mostra a visão redigida (terminal oculto). Abra `?secret=...` uma vez: a API troca por um cookie `httpOnly` (hash do secret, 30 dias) e o secret some da URL, sem ficar salvo no navegador |
| `MONITOR_INCLUDE_DETAILS=1` | PC | publica listas brutas (candidaturas, bloqueios, eventos, terminal). Padrão: só agregados |
| `MONITOR_DEMO=1` | Vercel/local | serve a demo fictícia e recusa POST (demo pública segura) |
| `MONITOR_LOCAL=0` | local | desliga a leitura direta do disco |
| `BOT_TZ` / `NEXT_PUBLIC_BOT_TZ` | PC / painel | fuso (padrão `America/Sao_Paulo`) |
| `MONITOR_CORS_ORIGIN` | Vercel | libera CORS para outra origem (padrão: mesma origem) |

### Arquivos de estado opcionais

Além de `aplicadas.json`, o snapshot lê (se existirem; ausência não quebra nada):

- `state/vagas_fila.json` — fila da busca por script (painel "Busca por script"; títulos e links só com `MONITOR_INCLUDE_DETAILS=1`);
- `state/gmail_status.json` — resumo do leitor de respostas do Gmail (`atualizado`, `linhas_lidas`, `achados`);
- `aguardando_login` / `login_checagens` dentro de `aplicadas.json` — fila "Esperando login" (só no modo detalhado);
- `status` (`etapa_teste`, `proxima_etapa`, `entrevista`...) e `historico_status[].email_data` (data do e-mail) em cada candidatura.

E-mails, CPFs e telefones em texto livre são trocados por `[e-mail]`, `[cpf]`, `[telefone]` antes de publicar.

## Rodando com Docker (demo)

Demonstração com dados de exemplo — **nunca** monta seu `bot/` real:

```bash
docker compose up monitor   # http://localhost:3000
```

O serviço `monitor` (raiz: `docker-compose.yml`) usa a imagem do `Dockerfile`
da raiz, monta só `examples/` como **read-only** (`/demo:ro`) e sobe `npm run dev`
com `MONITOR_DEMO=1`, então o painel mostra a demo fictícia de `demo.mjs`.
Para dados reais, rode fora do Docker (`npm run dev` acima) apontando
`CANDIDATURAS_ROOT` para o seu `bot/` local.

## Segurança

O snapshot publica agregados por padrão (contadores, estados, perfis e totais).
Detalhes brutos (aplicadas, bloqueadas, eventos, caudas de log) só saem quando
`MONITOR_INCLUDE_DETAILS=1` for definido explicitamente — nada de CPF, documentos,
segredos, host/pid ou caminho local. Proteja o endpoint com `MONITOR_SECRET`
(header `x-monitor-secret`) se expor o painel.
