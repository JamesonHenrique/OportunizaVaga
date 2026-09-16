Tarefa AVULSA (não faz parte do loop de candidaturas): manutenção do perfil Gupy.
Chrome real via CDP na porta 9222, já logado. Faça UM item por execução e pare.

Página: https://SUA-EMPRESA.gupy.io/candidates/profile — aba "Meu currículo".

Regra: NUNCA invente dado. Fonte única = ~/candidaturas/dados_candidato.json.

Itens pendentes (faça o primeiro que ainda não estiver feito, depois PARE e relate):

1. HABILIDADES (bloqueado hoje — ver nota técnica abaixo). Adicionar, até o limite de 30:
   Angular, APIs REST, PostgreSQL, JavaScript, Docker, Git, SQL, JUnit, n8n, Make.
   Já cadastradas: Java, TypeScript, Spring Boot.

2. EXPERIÊNCIA: adicionar "SUA_EMPRESA (LegalOps) — Estagiário de Automação RPA,
   ago/2026 até atual". Descrever por período, NUNCA por "X anos de experiência".

3. IDIOMAS: conferir que está Português nativo, Inglês Intermediário, Espanhol Básico.
   Alemão já foi removido em 2026-09-14 (era dado falso).

NOTA TÉCNICA — por que o item 1 está travado (tentado em 2026-09-14, 4 estratégias falharam):
o autocomplete #skills-search-autocomplete abre a listbox e lista opções ao digitar de verdade,
mas selecionar a opção não habilita o botão "Adicionar". Falharam: clique normal (interceptado
por overlay .jss184/.jss262), Enter, ArrowDown+Enter, e dispatch sintético de
pointerdown/mousedown/mouseup/click via JS. Não repita essas 4 — ou ache caminho novo
(ex.: React onChange via setter nativo no input + evento 'change', ou navegar por Tab até a opção),
ou desista em <10 tentativas e relate "Gupy skills segue bloqueado".

Ao terminar: clique SALVAR, registre o que fez em aplicadas.json -> manutencao_gupy
(objeto {data, item}), feche as abas deixando 1 about:blank, e relate em até 5 linhas.
