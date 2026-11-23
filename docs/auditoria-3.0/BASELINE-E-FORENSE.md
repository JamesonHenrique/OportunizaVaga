# Baseline e forense da Lane B

Baseline observado em 2026-11-22, no commit `2b8c143` da branch `feat/oportunizavaga-3-product-evolution`.

| Verificação inicial | Resultado |
| --- | --- |
| `node --test monitor/*.test.mjs` | 13/13, saída 0 |
| `node --test tests/password-target.test.mjs` | 38/38, saída 0 |
| `bash scripts/validate.sh` | 12 exemplos válidos, saída 0 |
| `bash tests/test_vaga_check.sh` | 9/10, saída 1. Caso 6 perdeu a evidência de incompatibilidade de stack de uma segunda vaga Gupy com ID distinto. |
| `bash tests/test_vigia_vida.sh` | 7/7, saída 0 no ambiente padrão. Com proxy HTTP sintético indisponível e sem exceção para loopback, 5/7, saída 1. Os casos 4 e 5 não chegavam ao servidor da fixture. |
| `./scripts/sanitize.sh` | Saída 1, erro operacional. A worktree continha um symlink local `monitor/node_modules` para um diretório de dependências não versionado. Com esse caminho excluído só para o comando, a saída também foi 1, por correspondências de regras de URL, CEP e domínio em 14 arquivos já presentes no índice. |

## Repositórios e deploy

- `OportunizaVaga` contém o motor público, exemplos e o app Next.js em `monitor/`. O README do monitor documenta o deploy da demo na Vercel com raiz `monitor` e `MONITOR_DEMO=1` (dados fictícios).
- A operação pessoal documentada usa `~/candidaturas` como fonte do estado e `~/monitor` como projeto de painel privado separado. A topologia de produção é histórica e consta na constituição e no Segundo Cérebro. Esta auditoria verificou somente a worktree local, com dados sintéticos.
- O endpoint mantém ordem e histórico por instância, em memória. Ambos os segredos autorizam o mesmo feed de escrita. A leitura detalhada usa `MONITOR_SECRET`. `updatedAt` continua sendo a hora de recepção por compatibilidade e `freshness.ageMs` mede a idade desde `builtAt`.

## Inventário

| ID | Constatação e ajuste |
| --- | --- |
| P1-1, P1-2, P1-4, P1-5 | Escrita sem segredo, redação parcial, tamanho baseado apenas no cabeçalho e aceitação de snapshots fora de ordem. A API agora exige segredo, reconstrói o DTO público campo a campo, conta bytes do stream, valida o envelope e separa geração de recepção. |
| P1-6 | O publicador avulso não autenticava nem tinha prazo. O shell abria o log compartilhado em modo de truncamento. Os dois publicadores passam a autenticar e o shell abre o log em modo de anexação. |
| P1-7 | O retry diminuía o índice da cascata e reutilizava a identidade anterior. Cada execução recebe um UUID. Intenções pendentes exigem a mesma identidade de tentativa para reentrada. |
| P1-8 | A deduplicação precedia a avaliação da descrição e tratava vagas distintas do mesmo portal como uma só. A triagem agora antecede a deduplicação entre portais e URLs canônicas continuam identificando repostagens da mesma vaga. |
| P1-9 | A fila era lida apenas em `state/` e o snapshot descartava a evidência da saúde dos portais. O monitor lê os diretórios dos perfis, mantém o layout legado e prioriza a evidência mais recente por portal. |
| P2-1, P2-2 | Saúde usava temporário fixo sem lock. O sanitizador não cobria os nomes privados em diretórios arbitrários. A saúde agora usa o lock e a escrita atômica de `jsonlock` e o sanitizador verifica nomes também em arquivos locais ignorados. |
| P2-3, P2-4, P2-5 | Contadores diários misturavam UTC e data local, IDs de modelo eram cortados e a cauda usava expansão de arrays. A geração usa um fuso, preserva o ID completo e limita os bytes lidos dos logs. |
