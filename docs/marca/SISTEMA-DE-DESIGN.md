# Sistema de design — OportunizaVaga

**Versão** 3.0.0

**Direção** Instrumento de Precisão

O monitor organiza as informações por decisão: conferir o estado da automação, agir sobre pendências e entender o ritmo dos envios.

## Fonte de verdade

- `branding/tokens.json` é a fonte canônica dos tokens.
- `branding/tokens.css` expõe os tokens como variáveis CSS. Os blocos temáticos são espelhados em `monitor/app/globals.css`.
- `branding/logos/*.svg` e `branding/icons/*.svg`: masters vetoriais.
- `branding/manifest-assets.json`: inventário dos assets.

Componentes consomem variáveis CSS. Ao alterar um token, sincronize o JSON e os dois arquivos CSS.

| Categoria | Tokens | Valores |
|---|---|---|
| Tipografia | `--fs-micro`, `--fs-small`, `--fs-body`, `--fs-h3`, `--fs-h2`, `--fs-h1`, `--fs-display` | 12, 13, 14, 16, 20, 28 e 48 px com raiz de 16 px. |
| Espaçamento | `--space-*` | Grade de 4 px. A escala oferece 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 e 80 px. |
| Raios | `--radius-xs`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-pill` | 4, 8, 12, 16 e 999 px. Cards e painéis usam `--radius-md`. |
| Movimento | `--motion-fast`, `--motion-normal`, `--motion-slow`, `--motion-ease` | 120, 180 e 280 ms com `cubic-bezier(0.2, 0.75, 0.25, 1)`. |
| Interação | `--target-min` | Mínimo de 40 px para os alvos. |
| Gráficos | `--chart-*` | Barras, hoje, seleção, zero, grade, eixos, faixa de hoje e tooltip nos dois temas. |

## Princípios de layout

- A área principal tem largura máxima de 1440 px. As margens internas são de 32 px no desktop, 24 px com a lateral compacta, 20 px no tablet e 16 px até 640 px.
- Cards usam borda fina, raio de 12 px e sombra discreta. Tabelas e listas usam alinhamento e divisórias para manter a leitura em alta densidade.
- A barra de contexto acompanha a rolagem. A navegação usa lateral com rótulos a partir de 1200 px, lateral compacta entre 1024 e 1199 px e barra inferior abaixo de 1024 px.

## Componentes

### Botões

- O botão primário usa cobalto sólido, texto claro e altura mínima de 40 px.
- Secondary: fundo de superfície, borda e texto principal.
- Tertiary: baixo peso visual, para ações secundárias.
- Destructive: cor semântica de erro, apenas para exclusão/parada irreversível.
- Toda ação precisa de hover/focus/pressed/disabled/loading quando aplicável. Não usar chartreuse como fundo primário de botão sem checar contraste.

### Campos

Rótulo visível, texto auxiliar quando necessário, borda discreta, foco cobalto bem visível e erro com texto explícito. Placeholder não substitui label.

### Cartões de vaga

Ordem sugerida: cargo; empresa e localidade; badges úteis (remoto/híbrido, nível, fonte); data; status atual; motivo de compatibilidade ou próxima ação, se houver. Não inventar score de compatibilidade se o motor não o fornece.

### Status e tags

Status deve ter pelo menos um rótulo textual. Cor e ícone são redundância visual, não o único canal. Diferenciar estados como encontrado, elegível, enviado, pendente, bloqueado, falhou, stale/cache e fictício/demo.

### Métricas (KPIs)

O Início tem quatro indicadores com rótulo e contexto próprios.

| Indicador | Fonte e recorte |
|---|---|
| Enviadas hoje | Último dia da série de envios, com total de sete dias e rodadas de hoje como contexto. |
| Precisa de você | Itens visíveis que requerem ação humana, com destaque para os críticos. |
| Respostas de empresas | Total de candidaturas com status de teste, próxima etapa, entrevista, respondida ou encerrada, a partir dos registros ou das contagens agregadas disponíveis. |
| Novas vagas | Total de novas vagas que passaram pelos filtros da última coleta. |

Use `0` para contagens confirmadas e `—` quando o dado estiver indisponível. Identifique indicadores baseados em retratos em cache ou sem sinal.

### Terminal e logs

Fundo escuro dedicado em ambos os temas, fonte IBM Plex Mono, contraste alto, timestamps alinhados e truncamento com acesso ao conteúdo completo. Não transformar logs em texto de marketing. Não expor segredos ou PII.

### Gráficos

Início e Candidaturas usam o mesmo componente de envios diários com a mesma janela de 14 dias corridos, incluindo hoje. Use o fuso do retrato. Preencha os dias sem registro com zero quando houver contagem diária, destaque hoje com faixa e rótulo e informe quando a contagem estiver indisponível. Indique período e unidade na legenda e use `--chart-*` para as cores. O gráfico usa um único foco de teclado. As setas selecionam o dia, Home e End movem para as extremidades, Esc limpa a seleção e o leitor de tela recebe um resumo da série.

### Alertas e exceções

Mensagem com: o que ocorreu, impacto observado, se requer ação e ação recomendada. Diferenciar informação, aviso, erro e estado bloqueado. Alertas stale/instância fria não devem parecer sucesso.

### Skeleton, vazio, falha e stale

- Loading: skeleton proporcional ao componente que vai aparecer; respeitar reduced motion.
- Empty: dizer que não há resultados e indicar filtro/ação que pode ajudar, sem prometer resultados.
- Error: mensagem curta, detalhe expandível e tentativa/recovery quando seguro.
- Aos 7 min de idade (`420000` ms), o retrato fica desatualizado e o monitor exibe **Sem sinal**. A API informa o limiar e usa `builtAt` como referência. Para retratos antigos, a interface pode recorrer a `receivedAt` ou `updatedAt`.
- Na partida sem retrato, informe que nenhuma atualização foi recebida. Quando a atualização falhar e houver um retrato anterior, identifique **Em cache** e mostre a última confirmação.
- A visão pública exibe agregados permitidos e identifica a origem. A lista de candidaturas, o terminal e textos operacionais privados ficam no acesso autorizado, quando disponíveis.
- Demo: etiqueta visível “Dados fictícios — demonstração”.

## Temas claro e escuro

Os temas devem transmitir a mesma identidade. O claro usa Off White e superfícies quase brancas; o escuro usa Azul Noturno e camadas azul-grafite. Não basta inverter branco/preto. Verifique especialmente bordas, texto secundário, chips, terminal, charts e elementos desabilitados.

## Responsividade

- 320–479 px: uma coluna, navegação adaptada, tabelas com rolagem horizontal localizada ou cards equivalentes; nunca overflow global.
- 480–767 px: uma coluna predominante, KPIs em 2 colunas quando couberem.
- 768–1023 px: layout de 1–2 colunas conforme a prioridade dos dados.
- 1024 px ou mais: painel em duas colunas onde a informação realmente beneficie da comparação.
- Em telas estreitas, deixar o resumo e “precisa de você” acima de terminais ou métricas secundárias.

## Acessibilidade e movimento

- Texto normal: contraste mínimo WCAG AA 4,5:1; texto grande 3:1.
- Foco visível de pelo menos 2 px e offset claro.
- Não depender só de cor para estado.
- Alvos interativos de pelo menos 40 px. Controles com apenas ícone têm nome acessível.
- Respeitar `prefers-reduced-motion`.
- Zoom 200% sem esconder ações essenciais; teclado sem armadilhas.

## Organização das abas

A navegação renderiza uma área de trabalho por vez. Ao trocar de aba, o foco vai para o conteúdo principal e a navegação marca o item ativo com `aria-current`. LinkedIn e Telegram aparecem quando o retrato oferece dados desses canais.

### Dashboard / início

O **Operational Command Header** abre com um título operacional e três blocos: estado do robô, última atualização confirmada e itens que precisam de intervenção. Identifique cache, demo ou visão pública quando aplicável. Abaixo, entram **Precisa de você**, os quatro indicadores, o gráfico de 14 dias e o **Monitor da Automação**.

### Candidaturas

Busca/filtro, lista/tabela com empresa, cargo, data, fonte e status. Exportar CSV deve parecer uma ação secundária visível; manter a semântica dos dados já existentes.

### Bloqueios e pendências

Agrupar pelo impacto e data; explicar motivo e próxima ação. Não ocultar bloqueio atrás de apenas um ponto colorido.

### Robô / terminal

Exiba o estado do ciclo, o último sinal confirmado, fontes e modelos, com evidência de escrita e terminal quando disponíveis. Diferencie a atividade do robô da idade do retrato e do modo de acesso.

### Diagnóstico / saúde / fontes

Usar cards de diagnóstico leves, timestamp, evidência e explicação curta. Não afirmar que todos os sites estão funcionando sem uma verificação do último ciclo.

### Relatórios / funil

Mostrar intervalo de datas, denominadores e limites da métrica. Não confundir páginas encontradas, elegíveis, enviadas, convites ou entrevistas.

### Configuração e documentação

Explicar opções em linguagem direta. Para qualquer configuração que exponha dados ou permita automação, manter confirmação e descrição do efeito.

## Microcopy recomendada

- “Última atualização há 4 min.”
- “Sem atividade nova neste ciclo.”
- “Dados em cache — a fonte não confirmou uma atualização recente.”
- “Precisa de você.”
- “Ação não confirmada.”
- “Dados fictícios — demonstração.”
- “Ver motivo” / “Tentar novamente” / “Abrir log”.
