# Guia de marca — OportunizaVaga

**Versão:** 2.0.0  
**Status:** direção proposta para adoção no produto  
**Assinatura pública:** *Sinal que vira movimento.*

## 1. Essência

OportunizaVaga transforma a busca por oportunidades de uma atividade fragmentada em um fluxo que pode ser entendido e acompanhado. A marca não promete conseguir emprego para ninguém. Ela representa descoberta, organização, execução controlada e visibilidade do que aconteceu.

### Promessa

**Mais visibilidade sobre a busca. Mais controle sobre cada etapa.**

### Personalidade

- **Atenta:** encontra sinais relevantes entre muita informação.
- **Prática:** prefere evidências e próximos passos a frases de motivação vazias.
- **Transparente:** identifica o que foi encontrado, enviado, bloqueado, atualizado ou não confirmado.
- **Independente:** a ferramenta serve à pessoa que está procurando trabalho.
- **Técnica, sem frieza:** apresenta detalhes e logs quando ajudam, mas explica o que significam.

### Frases de apoio

- “Encontre oportunidades. Acompanhe o que acontece.”
- “Vagas encontradas. Candidaturas no controle.”
- “O que foi feito, o que falta e o que precisa de você.”
- “Menos busca perdida. Mais clareza no processo.”

Evite afirmações como “emprego garantido”, “candidatura perfeita”, “zero bloqueios” ou “aplica em todas as plataformas” sem comprovação robusta.

## 2. Conceito gráfico: sinal que vira movimento

O símbolo é construído a partir de três ideias:

1. **Arco circular aberto:** um radar incompleto, indicando busca contínua e possibilidade de seguir adiante.
2. **Trajeto diagonal:** representa o caminho da descoberta para a ação.
3. **Ponto chartreuse:** a oportunidade que merece atenção.

A marca não deve ser desenhada como um alvo completo, maleta, pessoa, check de aprovação ou seta genérica. A geometria vetorial entregue nesta pasta é a referência para novas exportações.

## 3. Assinatura

- Nome oficial: **OportunizaVaga** (sem espaço, respeitando a capitalização).
- Assinatura principal: **Sinal que vira movimento.**
- Descritor técnico quando necessário: **Busca e monitoramento de vagas**.
- Em contextos de software livre: “Projeto open-source” ou “Código aberto”, apenas nos canais em que isso seja factual.

Não acrescente slogans à assinatura horizontal em espaços muito estreitos; use apenas o símbolo.

## 4. Cores

| Token | Hex | Função |
|---|---|---|
| Azul Noturno | `#101826` | Base, profundidade, texto principal e superfícies escuras. |
| Cobalto | `#3E63F5` | Interação, navegação ativa, links e descoberta. |
| Chartreuse | `#D7F36A` | Ponto-sinal, destaque curto e detalhe distintivo. |
| Off White | `#F7F7F2` | Fundo claro principal e texto em áreas escuras. |
| Cinza Névoa | `#E6EAF0` | Linhas, fundos auxiliares e organização. |
| Coral | `#FF725E` | Intervenção/atenção pontual; usar com moderação. |

### Regras de aplicação

- Cobalto é a principal cor de ação.
- Chartreuse é um acento de marca, não uma cor universal de sucesso. Não use chartreuse para texto pequeno sobre branco/off-white.
- Sucesso, alerta, erro e informação têm cores semânticas próprias nos tokens, diferentes da paleta de marca quando isso for necessário para manter significado e contraste.
- Não pinte todos os cartões; prefira superfície neutra, borda, tipografia e poucos acentos.
- Evite gradiente em fundos grandes, botões e todos os indicadores ao mesmo tempo.
- Não use coral como sinônimo de marca primária; reserve-o para chamar atenção para algo que exige intervenção.

## 5. Tipografia

### Manrope

Fonte principal para wordmark textual, títulos, rótulos e textos de interface. Pesos recomendados: 400, 500, 600, 700 e 800. Em headings grandes, use tracking levemente negativo e mantenha boa legibilidade.

### IBM Plex Mono

Fonte técnica para terminal, timestamps, nomes de modelos, ids, números com necessidade de alinhamento e detalhes operacionais. Não use em parágrafos longos nem em toda a interface.

Use fallbacks de sistema. O produto deve continuar utilizável caso a fonte externa não carregue. Não incluir arquivos de fonte no pacote.

## 6. Logo e área de proteção

- Use o SVG claro sobre branco, off-white ou cinzas muito claros.
- Use o SVG escuro sobre azul noturno ou superfícies suficientemente profundas.
- Use a versão monocromática em impressão, documentos de uma cor e limitações técnicas.
- Use o símbolo isolado para favicon e avatar; não reduza o wordmark para um tamanho em que “OportunizaVaga” perca legibilidade.
- Preserve a proporção e o espaço transparente interno dos arquivos SVG.
- Área livre mínima recomendada: 0,5× a altura do símbolo em cada lado.
- Logo horizontal: evitar abaixo de 150 px de largura; abaixo disso, usar somente o símbolo.
- Símbolo: 20 px é o mínimo recomendado para interface; validar visualmente a versão favicon em 16 px.

### Nunca

- Esticar, inclinar ou redesenhar a marca por CSS.
- Aplicar sombra, contorno, brilho ou gradiente ao logo.
- Trocar as cores do símbolo para indicar estados semânticos.
- Inserir o logo sobre padrões complexos sem uma base contrastante.
- Transformar o símbolo em outro ícone genérico de vaga ou confirmação.

## 7. Elementos gráficos

- **Trilhas:** linhas curvas/angulares com poucos pontos de parada, representando caminho e acompanhamento.
- **Pontos de sinal:** pequenos círculos em chartreuse ou cobalto, usados como detalhe, não como confete.
- **Grade de pontos:** padrão técnico de baixa opacidade para capas e áreas vazias.
- **Monoespaçada:** reservar para o conteúdo operacional.
- **Cartões de vaga:** hierarquia de cargo, empresa, localização/remoto, fonte, data e status; etiquetas curtas e úteis.

A trilha SVG em `branding/patterns/trilhas.svg` é decorativa e não deve ficar atrás de informação densa.

## 8. Tom de voz

Escreva em português brasileiro simples, preciso e sem promessas exageradas. Mostre a ação e o estado antes de explicar detalhes técnicos. Quando necessário, explique o termo técnico em uma segunda linha.

Preferir:
- “Última atualização há 4 min” em vez de “sync ativo”.
- “O robô está aguardando a próxima rodada” em vez de “idle”.
- “Precisa de você: confirme os dados ausentes” em vez de apenas “erro de execução”.
- “Dados fictícios — demonstração” sempre que os números não forem reais.

Evitar jargão sem explicação, gamificação infantil, emojis frequentes, alarmismo e frases genéricas como “O futuro começa agora”.

## 9. Imagem e divulgação

Use capturas reais e sanitizadas da interface, diagramas simples do fluxo e screenshots sintéticos identificados como demo. Evite fotos genéricas de pessoas apertando as mãos, currículos sobre uma mesa ou pessoas apontando para gráficos. Nunca publique dados de candidato, cookies, e-mails, CVs, segredos ou logs reais.

## 10. Marca dentro do produto

A interface principal é uma ferramenta operacional, não uma página de publicidade. Preserve densidade informacional quando ela dá visibilidade ao trabalho. Dê destaque às exceções, aos próximos passos e à proveniência dos dados. Não esconder estado stale, cache, falhas, bloqueios ou ações pendentes.
