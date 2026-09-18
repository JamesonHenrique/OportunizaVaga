# Modelos — cascata grátis, provider-agnóstico e 100% local

O OportunizaVaga separa **o "cérebro" (o modelo)** do **"corpo" (o Chrome real via
CDP)**. Trocar de modelo nunca muda a forma de aplicar — só quem raciocina. Isso dá
três caminhos, do mais barato ao mais privado:

| Caminho | Custo | Privacidade | Config |
|---|---|---|---|
| Cascata free (padrão) | R$ 0 | dados vão a APIs free | [`config/opencode.jsonc.example`](../config/opencode.jsonc.example) |
| Provider pago único | pago | dados vão à API | mesma, trocando `model` |
| **100% local (Ollama)** | R$ 0 | **nada sai da máquina** | [`config/opencode.local.jsonc.example`](../config/opencode.local.jsonc.example) |

A escada de providers free e os backoffs estão documentados em
[`docs/CUSTO.md`](CUSTO.md). Aqui o foco é **como estender** e **como rodar local**.

## 100% local com Ollama (offline, privado)

Como o robô lê seu CV e seus dados pessoais, rodar o modelo na sua própria máquina
elimina o envio desses dados a terceiros — o argumento de privacidade mais forte do
projeto.

```bash
# 1. Instale o Ollama:  https://ollama.com/download
# 2. Baixe um modelo com bom tool-calling:
ollama pull qwen2.5:14b        # bom meio-termo; use :8b se faltar RAM/VRAM
# 3. Confirme o servidor OpenAI-compatível:
curl http://localhost:11434/v1/models
# 4. Use o exemplo local:
cp config/opencode.local.jsonc.example ~/.config/opencode/opencode.jsonc
```

Trade-off honesto: modelos locais pequenos erram mais tool-calls (abrir/clicar) que
os grandes da cascata free. Prefira ≥14B se o hardware permitir e valide com
`./bot/dry-run.sh` antes de uma rodada real.

## Adicionar um provider novo à cascata (`bot/loop.sh`)

A cascata é controlada por flags `USAR_*` (ver `docs/CUSTO.md`). Para plugar um
provider novo:

1. Garanta que o OpenCode conhece o provider (via `~/.config/opencode/opencode.jsonc`).
2. Adicione os IDs de modelo na lista de cascata do `bot/loop.sh`, na posição de
   preferência desejada.
3. Se o provider tiver **API de cota** (como o OpenRouter), dá para medir uso real no
   monitor — veja `monitor/quota-daemon.mjs`. Sem API de cota, o painel infere "bateu
   no teto" contando eventos de cascata no `loop.log`.
4. Rode `./bot/doctor.sh` e uma rodada de `dry-run` para validar.

## Qual modelo escolher

- **Rodadas de listagem/filtro** (a maior parte): qualquer modelo free decente serve.
- **Preencher formulário Gupy** (tool-calling pesado): prefira os modelos maiores da
  cascata ou um local ≥14B.
- **Nunca** confie no modelo para inventar dado ausente: campo vazio em
  `bot/dados_candidato.json` vira `bloqueado`, por design. Isso independe do modelo.
