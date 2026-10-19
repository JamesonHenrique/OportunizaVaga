# Auditoria da identidade visual atual do OportunizaVaga

## Escopo e limites

A avaliação foi feita sobre os arquivos enviados nesta conversa:
- `OportunizaVaga-main`: repositório do robô, documentação e aplicação de monitoramento em `monitor/`.
- um segundo painel de monitoramento em Next.js, fora deste repositório.
- `assets/demo.gif`, folhas de estilo, layouts, logos e favicons presentes nesses pacotes.

A implantação online não foi validada tela a tela. A avaliação visual abaixo usa os fontes e o GIF de demonstração do repositório enviado.

## Diagnóstico resumido

A implementação atual tem uma base de interface acima da média para um projeto pessoal/open-source: existe um sistema de tokens CSS, tipografia sans-serif combinada com monoespaçada, hierarquia por painéis, indicadores operacionais, tema claro/escuro e estados de atividade. O dashboard organiza muita informação sem depender de um único gráfico gigante.

A marca, porém, comunica menos personalidade que o produto. O logo antigo combina pessoas, maleta, check e seta ascendente. Esses elementos são comuns em marcas de emprego, consultoria, recrutamento e treinamento. No tamanho pequeno do cabeçalho, boa parte do desenho vira detalhe ilegível.

Também há um problema técnico com os assets atuais: os SVGs do logo/ícone são wrappers de imagem PNG codificada em Base64, não vetores reais. Isso piora a manutenção, a nitidez em escalas diferentes e a possibilidade de editar o símbolo com precisão.

## Pontuação qualitativa

| Área | Nota estimada | Motivo |
|---|---:|---|
| Organização do dashboard | 7/10 | Hierarquia, indicadores e painéis úteis para monitoramento operacional. |
| Sistema de tokens | 8/10 | A folha atual centraliza cores, temas, tipografia e componentes. É uma boa base para evolução. |
| Distintividade do logo | 3/10 | Muitos clichés simultâneos e leitura fraca em tamanho pequeno. |
| Qualidade técnica dos masters de marca | 2/10 | SVGs atuais contêm PNG em Base64, em vez de geometria vetorial. |
| Diferenciação da paleta | 4/10 | Azul e verde muito saturados são familiares em dashboards de software e empregabilidade. |
| Consistência entre aplicações | 5/10 | Há duas árvores de monitoramento no material recebido; é preciso tratá-las como projetos relacionados, não fundi-las sem decisão. |

Estas notas são uma avaliação de design, não métricas de produto, conversão ou usabilidade medidas com usuários.

## O que preservar

- A estrutura de dashboard orientada a dados e operação.
- Os temas claro/escuro e os tokens CSS como base de manutenção.
- A fonte monoespaçada para logs, timestamps, modelos, identificadores e detalhes técnicos.
- A faixa de estado/heartbeat, indicadores operacionais, lista de candidaturas, histórico, bloqueios e terminal.
- A organização em componentes independentes.
- Os princípios de transparência: diferenciar dados reais, demo/fictícios, cache e informações desatualizadas.

## O que mudar

1. Substituir o logo complexo por um símbolo que funcione em 16–24 px e continue reconhecível em avatar e favicon.
2. Substituir os SVGs rasterizados por verdadeiros masters vetoriais.
3. Estabelecer uma única paleta de marca; separar cores da marca de cores semânticas de sucesso, aviso e erro.
4. Usar chartreuse como detalhe distintivo, nunca como texto pequeno sobre fundo claro.
5. Manter o azul como cor de interação e não usar gradientes em tudo.
6. Unificar escalas, raios, estados, foco, tipografia e espaçamento sem remover dados úteis da interface técnica.
7. Aplicar a mesma voz visual à página principal, monitor, README/GitHub, documentação e materiais de divulgação.

## Riscos a evitar

- Não transformar o painel em uma landing page de marketing; é uma ferramenta operacional densa.
- Não reescrever o motor de candidaturas para fazer um redesign.
- Não representar falha, bloqueio e sucesso apenas por cor.
- Não prometer emprego, entrevista garantida ou funcionamento irrestrito de todos os sites.
- Não ocultar ações que precisam de intervenção do usuário só para deixar a tela “limpa”.
- Não colocar dados pessoais, tokens, cookies, CVs ou conteúdo real de log em imagens públicas.
