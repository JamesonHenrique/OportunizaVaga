# Sistema de design — OportunizaVaga

Este documento define como transformar a marca em componentes reutilizáveis sem perder a natureza de dashboard técnico.

## Fonte de verdade

- `branding/tokens.json`: tokens semânticos e de marca canônicos.
- `branding/tokens.css`: CSS variables com aliases compatíveis com os estilos atuais do monitor.
- `branding/logos/*.svg` e `branding/icons/*.svg`: masters vetoriais.
- `branding/manifest-assets.json`: inventário dos assets.

Evite duplicar cores hexadecimais espalhadas por componentes. Componentes devem consumir tokens. Em casos onde um token existente é referenciado por muitas classes, mantenha aliases temporários e faça a migração em mudanças pequenas.

## Princípios de layout

- Content width desktop: até 1280 px; manter layout principal dentro dessa largura.
- Gutter: 32 px em desktop, 24 px em tablet, 16 px em telas móveis.
- Espaçamento base: múltiplos de 4 px; valores comuns 8, 12, 16, 24, 32 e 48 px.
- Cards: raio padrão 12 px, borda fina e sombra quase imperceptível. Não colocar cada linha dentro de um cartão separado.
- Tabelas e listas: usar alinhamento, divisórias e estados tipográficos para densidade; manter alvos clicáveis claros.
- Navigation/status strip: sticky só onde já melhora o uso; não acrescentar cabeçalho vertical enorme num painel operacional.

## Componentes

### Botões

- Primary: cobalto sólido; texto claro; altura-alvo 40–44 px.
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

Use números grandes apenas para medidas úteis, título claro e contexto temporal. Adicione tendência somente quando os dados permitirem comparação real. Não mostrar percentagens fabricadas nem somar categorias incompatíveis.

### Terminal e logs

Fundo escuro dedicado em ambos os temas, fonte IBM Plex Mono, contraste alto, timestamps alinhados e truncamento com acesso ao conteúdo completo. Não transformar logs em texto de marketing. Não expor segredos ou PII.

### Gráficos

Use a paleta com parcimônia e legendas legíveis. Estados semânticos devem permanecer semanticamente corretos; não reutilize chartreuse para sucesso só porque é uma cor de marca. Eixos, período e unidade precisam estar claros.

### Alertas e exceções

Mensagem com: o que ocorreu, impacto observado, se requer ação e ação recomendada. Diferenciar informação, aviso, erro e estado bloqueado. Alertas stale/instância fria não devem parecer sucesso.

### Skeleton, vazio, falha e stale

- Loading: skeleton proporcional ao componente que vai aparecer; respeitar reduced motion.
- Empty: dizer que não há resultados e indicar filtro/ação que pode ajudar, sem prometer resultados.
- Error: mensagem curta, detalhe expandível e tentativa/recovery quando seguro.
- Stale/cache: expor quando os dados foram atualizados pela última vez e deixar claro que o cache não é prova de atividade atual.
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
- Alvos interativos confortáveis (ideal 40–44 px); controles de ícone têm tooltip/label acessível.
- Respeitar `prefers-reduced-motion`.
- Zoom 200% sem esconder ações essenciais; teclado sem armadilhas.

## Mapeamento sugerido para as telas atuais

### Dashboard / início

Hero curto com status do monitor, atualização recente e frase “Sua busca, em movimento.”; métricas de candidaturas e oportunidades; primeiro plano para “Precisa de você”; lista de atividades recentes. Não criar novos números só para preencher cards.

### Candidaturas

Busca/filtro, lista/tabela com empresa, cargo, data, fonte e status. Exportar CSV deve parecer uma ação secundária visível; manter a semântica dos dados já existentes.

### Bloqueios e pendências

Agrupar pelo impacto e data; explicar motivo e próxima ação. Não ocultar bloqueio atrás de apenas um ponto colorido.

### Robô / terminal

Estado do ciclo, último heartbeat, evidência de escrita do log, fontes/modelos usados e painel de log. Diferenciar “rodando”, “aguardando”, “parado”, “dados desatualizados”, “erro” e “demo”.

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
