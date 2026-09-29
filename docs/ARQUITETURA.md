# ARQUITETURA

```
                         ┌─────────────────────────────────────────────┐
 cron */5 ──────────────▶│ bot/guardiao.sh (supervisor idempotente)    │
 @reboot ───────────────▶│  ├─ loop.sh vivo? senão sobe                │
                         │  └─ Chrome CDP :9222 vivo? senão sobe       │
                         └──────────────┬──────────────────────────────┘
                                        │ flock (instância única)
                         ┌──────────────▼──────────────────────────────┐
                         │ bot/loop.sh (loop infinito)                 │
                         │  1. resolve perfil (BOT_PERFIL/perfil.json) │
                         │  2. render_prompt com estado isolado        │
                         │  3. escolhe 1 site do rodízio              │
                         │  4. opencode run (cascata de modelos free)  │
                         │     com prompt_loop.runtime.md ─▶ Chrome    │
                         │  5. watchdog de quota (mata rodada travada) │
                         │  6. fingerprint depois: mudou? achou vaga   │
                         │     nova → dorme 20min; senão backoff 1h→2h…│
                         │  7. publica snapshot agregado (monitor)    │
                         └──────────────┬──────────────────────────────┘
                                        │ estado durável
                         ┌──────────────▼──────────────────────────────┐
                         │ bot/aplicadas.json (perfil default)         │
                         │ bot/state/<perfil>/aplicadas.json           │
                         │  aplicadas, bloqueados, rodizio, descartes, │
                         │  pular_empresas/tipos, contas_criadas       │
                         │ O modelo NÃO tem memória entre rodadas:     │
                         │ cada rodada é sessão nova que lê/escreve    │
                         │ este arquivo.                               │
                         └──────────────┬──────────────────────────────┘
                                        │ descoberta automática
                         ┌──────────────▼──────────────────────────────┐
                         │ bot/sites/*.sh (contrato + lib.sh)         │
                         │  indeed, gupy, linkedin, programathor,      │
                         │  geekhunter, vagas                          │
                         └─────────────────────────────────────────────┘
```

## Componentes

| Arquivo | Papel |
|---|---|
| `bot/loop.sh` | Loop principal: perfil ativo, 1 site/rodada, cascata de modelos, backoffs, watchdog, rotação de log |
| `bot/dry-run.sh` | Plano global sem risco: valida JSONs, lista sites/terms/URLs e mostra limites |
| `bot/guardiao.sh` | Supervisor via cron (sem systemd): loop + Chrome; limpa lock órfão |
| `bot/followup.sh` | Rotina semanal (só leitura de status, nunca se candidata) |
| `bot/prompt_*.md` | O "cérebro": regras, rodízio, pré-filtros, canais, formato de registro |
| `bot/estado.py` | CLI compacta e atômica p/ ler/escrever `aplicadas.json` sem o agente ler o arquivo inteiro; `resumo` enxuto + `ja-visto EMPRESA [TITULO]` sob demanda |
| `bot/jsonlock.py` | Trava exclusiva (fcntl/msvcrt) + gravação atômica (tmp único, fsync, `os.replace`) dos JSONs de estado |
| `bot/prompt_cond.py` | Blocos condicionais do prompt (`<!--se:site=X-->…<!--/se-->`, `<!--se:telegram-->`; fail-open) e cerca `<<<DADOS_EXTERNOS>>>` para texto de terceiros; usado por `loop.sh`/`loop.ps1` |
| `bot/redact-logs.py` | Varredor que mascara segredos nos logs (chamado com `--forcar` ao fim de cada rodada + cron/Task Scheduler) |
| `bot/podar-sessoes.py` | (opt-in) Poda sessões antigas do robô no opencode, com filtro título+pasta; DB em 600 |
| `bot/gerar_cv.py` | Gera o PDF por vaga (regra `c1`) só a partir de `bot/cv_base.md` + `dados_candidato.json`; 1 página ou exit 2 |
| `bot/check_ats.py` | Mede a cobertura dos termos do anúncio no CV (meta >= 75%) antes de anexar |
| `bot/rodizio-saude.py` | Pausa (48h) site com 4 rodadas seguidas sem candidatura nova; reordena o rodízio 1x/dia pelo rendimento; hooks `pre`/`pos` no `loop.sh` |
| `bot/vaga_check.py` | Triagem determinística pela descrição + nível oficial do LinkedIn (conservadora, dirigida pelo perfil); usada por `descobrir.py` e pelo passo c0 do prompt. Ver `docs/OPERACAO.md` |
| `bot/modelos-saude.py` | Ordena a cascata de modelos pela taxa de sucesso real (logs de 7 dias), quarentena de modelo inútil, fail-open; chamado por `loop.sh`/`loop.ps1` antes de cada rodada |
| `bot/opencode-enxuto.py` | Gera o `OPENCODE_CONFIG_CONTENT` enxuto (MCPs/ferramentas não usadas fora) a partir da config do opencode do usuário; fail-open; usado por `loop` e `followup` |
| `bot/vigia-vida.sh` (+ `.ps1`) | Dead man's switch (cron/Task Scheduler a cada 15 min): avisa no Telegram se o loop parar em 2 checagens, o heartbeat do monitor envelhecer (`MONITOR_URL` opcional) ou o estado ficar ilegível |
| `bot/canario-fontes.py` | Canário diário AO VIVO dos parsers do LinkedIn/Gupy: avisa no Telegram quando o portal muda o markup (o contrato offline fica em `tests/test_canario_fontes.sh`) |
| `bot/sites/lib.sh` | Descoberta automática de adaptadores e contrato comum (`site_adapter_*`) |
| `bot/sites/*.sh` | Adaptadores de portal: URL de busca, dica de remoto e termos por site |
| `bot/chrome-lock.sh` (+ `.ps1`) | Protocolo único do Chrome compartilhado: lock + flags de prioridade (`alta` marca a vez, `normal` cede) |
| `browser/chrome-real.sh` | Chrome persistente com CDP :9222 (login 1x vale p/ tudo) |
| `config/sites_permitidos.json` | Blocklist de agregadores gringos/spam em 2 camadas: `--blocked-origins` + regra 7 do prompt |
| `monitor/*.mjs` | `snapshot` (agregado + perfis) → `publish-status` / `publish-once` → Vercel |
| `monitor/quota-daemon.mjs` | Mede cota diária OpenRouter `:free` (único provider com API de uso) |
| `scripts/monitor-keepalive.sh` | Dono único do publisher (sobe se cair) |
| `scripts/pull-monitor.sh` | Fast-forward do painel + restart do publisher se o código mudou |
| `scripts/digest.sh` | Resumo diário (aplicadas/bloqueadas + alertas de anomalia no `loop.log`) |
| `scripts/notificar.sh` | Push genérico ao Telegram (dedupe de 6h); usado por `digest`/`followup`/`rodizio-saude` |
| `scripts/ctl.sh` (+ `.ps1`) | Inspeção só-leitura: `status` / `rodada` / `chrome` em respostas curtas (comece por `status` antes de abrir qualquer log) |
| `scripts/backup-jsons.sh` | Cópia rotativa (14x) de `aplicadas.json`/`dados_candidato.json`, raiz + cada perfil |

## Decisões-chave

- **Sessão nova por rodada** (`opencode run`, sem `session --continue`): o histórico
  não carrega nada que `aplicadas.json` não tenha; rodada travada não contamina a próxima.
- **Fingerprint em vez de mtime**: o rodízio sempre regrava o arquivo, então "mudou"
  = soma de aplicadas + bloqueados + descartes. Mtime mentia.
- **Quota só conta em linha de erro**: varrer o corpo da rodada gerava falso positivo
  (anúncio de vaga com "trial"/"credit" mandava o loop dormir).
- **Watchdog via log interno**: o opencode entra em retry silencioso sem imprimir nada
  no stdout; o erro só existe no log interno — sem o watchdog, cada rodada bloqueada
  queimava 20 min de timeout.
- **Descarte de listagem ≠ bloqueado**: título/card filtrado vira contador
  (`descartes_listagem`), não entrada — bloqueados é só p/ vaga real com motivo concreto.
- **Estado por perfil**: `bot/perfil.json`/`BOT_PERFIL` ativa um estado isolado em
  `bot/state/<perfil>/aplicadas.json`; sem perfil, o histórico fica em `bot/aplicadas.json`.
- **Adaptadores descobertos automaticamente**: `bot/sites/*.sh` que cumpre o contrato
  entra no rodízio e no dry-run sem precisar de registro manual.
- **Modo reconhecimento**: `OV_RECONHECIMENTO=1` transforma a rodada em leitura e
  pontuação — nenhuma candidatura é enviada e `aplicadas.json` não muda.
- **Telemetria agregada**: o monitor publica contadores e estados por padrão;
  detalhes brutos só saem com `MONITOR_INCLUDE_DETAILS=1` (opt-in explícito).
- **Monitor sem banco**: a Vercel guarda só o último snapshot em memória (custo zero);
  o heartbeat repõe tudo em segundos após cold start.
