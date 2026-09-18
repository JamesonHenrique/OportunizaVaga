Tarefa AVULSA (não faz parte do loop de candidaturas): manutenção do perfil Gupy.
Chrome real via CDP na porta 9222, já logado. Faça UM item por execução e pare.

Página: https://<sua-empresa>.gupy.io/candidates/profile (ou portal.gupy.io) — aba "Meu currículo".

Regra: NUNCA invente dado. Fonte única = $BOT_ROOT/bot/dados_candidato.json.

($BOT_ROOT é a raiz do clone; os scripts exportam essa variável automaticamente.)
Adapte os itens abaixo ao SEU perfil (os valores são EXEMPLO para um dev Java/Spring + Angular):

1. HABILIDADES. Adicionar, até o limite de 30, as do seu dados_candidato.json
   (EXEMPLO: Angular, APIs REST, PostgreSQL, JavaScript, Docker, Git, SQL, JUnit, n8n, Make).

2. EXPERIÊNCIA: adicionar "SEU_CARGO — SUA_EMPRESA, <período>".
   Descrever por período, NUNCA por "X anos de experiência".

3. IDIOMAS: conferir que estão os seus idiomas reais (EXEMPLO: Português nativo,
   Inglês Intermediário, Espanhol Básico). NUNCA declare idioma que você não tem.

NOTA TÉCNICA — por que o item 1 está travado (tentado em 2026-09-14, 4 estratégias falharam):
o autocomplete #skills-search-autocomplete abre a listbox e lista opções ao digitar de verdade,
mas selecionar a opção não habilita o botão "Adicionar". Falharam: clique normal (interceptado
por overlay .jss184/.jss262), Enter, ArrowDown+Enter, e dispatch sintético de
pointerdown/mousedown/mouseup/click via JS. Não repita essas 4 — ou ache caminho novo
(ex.: React onChange via setter nativo no input + evento 'change', ou navegar por Tab até a opção),
ou desista em <10 tentativas e relate "Gupy skills segue bloqueado".

Ao terminar: clique SALVAR, registre o que fez em aplicadas.json -> manutencao_gupy
(objeto {data, item}), feche as abas deixando 1 about:blank, e relate em até 5 linhas.
