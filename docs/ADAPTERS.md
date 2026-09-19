# Adaptadores de site (como adicionar um portal)

Um **adaptador** é um descritor de um portal de vagas. Ele **não** abre o browser
nem aplica sozinho — quem faz isso é o modelo, dirigindo o Chrome real conforme
[`bot/prompt_loop.md`](../bot/prompt_loop.md). O adaptador só padroniza três coisas:

1. **Como montar a URL de busca** (com filtro remoto quando o portal permite);
2. **Onde/como o portal marca "remoto"** (dica para o modelo confirmar na página);
3. **Quais termos** daquela rodada valem para o site (lidos do `prompt_loop.md`).

Adaptadores são **descobertos automaticamente**: todo `bot/sites/*.sh` que segue o
contrato entra no plano do `dry-run` e no rodízio, sem registro manual. A
descoberta e o contrato comum vivem em [`bot/sites/lib.sh`](../bot/sites/lib.sh).

Adicionar um portal é a forma mais fácil de contribuir — e a que mais ajuda o
projeto. Cada portal novo é um PR pequeno e autocontido.

## Contrato

Base para copiar: [`bot/sites/_template.sh`](../bot/sites/_template.sh).

| Símbolo | Obrigatório | O que é |
|---|---|---|
| `SITE_ID` | ✅ | slug curto, sem espaço (`programathor`, `vagas`, `geekhunter`) |
| `SEARCH_URL_TEMPLATE` | ✅ | URL de busca contendo o marcador literal `SEU_TERMO` |
| `SITE_LABEL` | — | nome amigável para logs/monitor |
| `SITE_HOME` | — | home do portal (só documentação, nunca aberta sozinha) |
| `SITE_REMOTE_HINT` | — | como o portal expõe "remoto"/"home office" |
| `site_url_busca TERMO` | ✅ | imprime a URL de busca com o termo aplicado |
| `site_buscar_termos [PROMPT]` | ✅ | imprime, um por linha, os termos do site no `prompt_loop.md` |

O `lib.sh` injeta uma implementação padrão de `site_buscar_termos`: cada
adaptador só precisa declarar as variáveis do contrato; se quiser um parser
próprio, pode sobrescrever a função depois do `source`.

### Regras (o CI cobra)

- **Sem dado pessoal, sem segredo, sem caminho absoluto** (`/home/...`). Resolva a
  raiz por `$BOT_ROOT` com fallback para o próprio caminho do arquivo.
- Comentários em **português**; código e nomes em **inglês**.
- `bash -n` limpo e `shellcheck` **sem erro** (o CI roda os dois em toda a árvore).
- Nada de abrir browser ou navegar dentro do adaptador — ele é só descritor.

## Passo a passo

```bash
cp bot/sites/_template.sh bot/sites/meuportal.sh
$EDITOR bot/sites/meuportal.sh          # ajuste SITE_ID, SEARCH_URL_TEMPLATE, dicas
```

1. **`SITE_ID`**: o mesmo slug que você vai usar no rodízio e no `prompt_loop.md`.
2. **`SEARCH_URL_TEMPLATE`**: abra o portal, faça uma busca com filtro **remoto** e
   ordenação por **mais recentes**, e copie a URL trocando seu termo por `SEU_TERMO`.
3. **`site_url_busca`**: já vem pronto no template (troca espaços por `%20`); se o
   portal usa hífen no path (como Vagas.com.br), troque por `-` — veja
   [`bot/sites/vagas.sh`](../bot/sites/vagas.sh).
4. **Termos no prompt**: em `bot/prompt_loop.md`, adicione um bloco `- meuportal:`
   com os termos que fazem sentido nesse site.
5. **Rodízio**: inclua o `SITE_ID` na lista de rodízio (campo `rodizio` do
   `aplicadas.json` / seção de rodízio do prompt).

## Teste local (sem aplicar em nada)

```bash
bash -n bot/sites/meuportal.sh                       # sintaxe
shellcheck -S error bot/sites/meuportal.sh           # lint
source bot/sites/lib.sh
site_adapter_source meuportal "$(pwd)"              # carrega e valida o contrato
site_url_busca "desenvolvedor java junior"           # confere a URL montada
site_buscar_termos                                   # confere os termos lidos do prompt
./bot/dry-run.sh                                      # plano global: não aplica em nada
./bot/dry-run.sh --site meuportal --json             # plano só do portal novo
```

## Adaptadores que já existem

| Arquivo | Portal | Observação |
|---|---|---|
| [`indeed.sh`](../bot/sites/indeed.sh) | Indeed | filtro remoto por `l=Remoto` |
| [`gupy.sh`](../bot/sites/gupy.sh) | Gupy | perguntas padrão em `respostas_padrao_gupy` |
| [`linkedin.sh`](../bot/sites/linkedin.sh) | LinkedIn | limite diário de convites; ver prompt |
| [`programathor.sh`](../bot/sites/programathor.sh) | Programathor | só vagas de tech |
| [`geekhunter.sh`](../bot/sites/geekhunter.sh) | GeekHunter | exige perfil; fluxo parcial manual |
| [`vagas.sh`](../bot/sites/vagas.sh) | Vagas.com.br | termo com hífen no path |

Quer outro portal (Catho, Trampos, Revelo, InfoJobs, Solides…)? Copie o template,
abra um PR e ganhe seu lugar nesta tabela. Veja [`CONTRIBUTING.md`](../CONTRIBUTING.md).
