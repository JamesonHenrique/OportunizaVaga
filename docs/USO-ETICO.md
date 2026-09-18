# Uso ético e responsável

Este projeto automatiza ações em portais de emprego reais, com **a sua conta** e os
**seus dados pessoais**. Poder automatizar não é o mesmo que dever automatizar sem
critério. Leia antes de escalar o uso.

## Você aceita o risco

Automatizar candidaturas pode violar os Termos de Uso de LinkedIn, Gupy, Indeed e
outros. O código é publicado para **estudo e automação pessoal**. Ao usar, **você
assume o risco** de bloqueio/suspensão de contas. Os autores não se responsabilizam
por contas suspensas, vagas perdidas ou qualquer dano. (Igual ao aviso do README.)

## Princípios

1. **Só a sua conta, só os seus dados.** Nunca use o robô em nome de terceiros nem
   com dados que não são seus.
2. **Nunca inventar.** O design não chuta: campo vazio em `dados_candidato.json` vira
   `bloqueado`. Não contorne isso para "passar" numa vaga — é o coração da confiança
   do projeto e da honestidade com o recrutador.
3. **Não faça spam.** Candidatar-se a tudo que se move prejudica você (recrutadores
   percebem) e o ecossistema. O projeto foca em vagas que **casam de verdade** com o
   perfil — mantenha os filtros apertados.
4. **Respeite o ritmo humano.** Rajadas de requisições são a forma mais rápida de ser
   bloqueado e de sobrecarregar o portal. Prefira ritmo conservador (abaixo).
5. **Respeite o filtro remoto/nível** que você declarou — não force candidatura em
   vaga que claramente não é para o seu momento de carreira.

## Ritmo conservador (pacing)

Os tempos de espera do loop são configuráveis por env (defaults = histórico). Para um
uso mais "humano", aumente-os — copie o que quiser de
[`config/pacing.example.env`](../config/pacing.example.env):

| Env | Default | O que faz |
|---|---|---|
| `OV_NORMAL_WAIT` | 1200 (20min) | pausa após rodada com vaga nova |
| `OV_VAZIA_BASE` | 3600 (1h) | pausa inicial após rodada vazia (dobra a cada vazia) |
| `OV_RETRY_BASE` / `OV_RETRY_MAX` | 300 / 1800 | backoff de falha (base/teto) |
| `OV_RUN_TIMEOUT` | 20m | timeout por rodada |

Por design o bot já processa **1 site por rodada** em rodízio e faz backoff crescente
quando não há vaga nova — ou seja, quanto menos há para fazer, mais devagar ele vai.
Isso é intencional: reduz pegada e cara de automação.

## Privacidade

Rodar o modelo **100% local com Ollama** faz seus dados e CV nunca saírem da máquina.
Ver [`docs/MODELOS.md`](MODELOS.md). Nunca commite dados reais — ver
[`docs/SEGURANCA.md`](SEGURANCA.md) e rode `./scripts/sanitize.sh` antes de todo push.

## Não use para

- Aplicar em massa/indiscriminadamente (spam de candidaturas).
- Burlar verificações anti-bot de forma que caracterize fraude.
- Preencher dados falsos (experiência, idioma, tempo de carreira) — o robô é
  desenhado para **se recusar** a isso; mantê-lo assim é sua responsabilidade.
- Operar contas de terceiros ou coletar dados de terceiros.

Reportes de segurança: `SECURITY.md`. Conduta da comunidade: `CODE_OF_CONDUCT.md`.
