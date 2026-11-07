# ADR: integração local por CLI

- **Estado:** aceita para a primeira integração.
- **Data:** 2026-11-06.
- **Resume-Matcher examinado:** `main` no commit `d480551798b7aa97f5b57ba1972ee383bd882238`, versão Python `1.4.0`; licença Apache-2.0.

## Evidência técnica

O backend declara `resume-matcher` e `resume-matcher-mcp` como entrypoints. O CLI faz chamadas ao mesmo registro de ferramentas MCP e aceita JSON estruturado. `parse_check_file` recebe um caminho absoluto de PDF/DOCX, não chama LLM e retorna extraibilidade, páginas, checks e preview de texto. `score_resume` aceita `resume_data` e `keywords` sem exigir registro persistido. A renderização de PDF e parte das verificações de currículo dependem do frontend. `tailor_and_verify` valida/guarda/inspeciona dados escritos pelo agente chamador; o próprio Resume-Matcher não escreve o currículo por conta própria. Sua verificação de preservação também não substitui um verificador factual semântico.

O backend atual usa SQLite local por padrão. `DATA_DIR` define o armazenamento. Se MCP estiver em um volume Docker e CLI/MCP rodarem em ambientes distintos, cada um vê o próprio banco sem um volume compartilhado; o parser do PDF funciona sem perfil persistido. A configuração oficial não oferece um mecanismo mágico de compartilhamento entre o volume do contêiner e um cliente MCP no host. MCP/HTTP não são usados pelo fluxo de anexo: um processo CLI local reduz estado operacional e não expõe porta de rede. O backend FastAPI não é usado porque não há autenticação no serviço; ele não deve ser exposto publicamente sem uma camada de autenticação/autorização.

## Alternativas comparadas

| Alternativa | Decisão | Motivo nesta etapa |
|---|---|---|
| A. Serviço/API | Adiada | Adds processo, porta, autenticação e disponibilidade; o gate só precisa de uma checagem local. |
| B. MCP | Adiada | Bom para agentes interativos, mas o consumidor atual é um script shell determinístico e já há CLI oficial com os mesmos tools. |
| C. CLI | Escolhida | Entrada e saída JSON, códigos de saída e timeout; simples de chamar sem frontend. |
| D. Copiar módulos | Rejeitada | Criaria acoplamento e obrigações de manutenção; nenhuma cópia de código do Resume-Matcher foi feita. |
| E. Híbrida | Escolhida | Mantém gerador e verificações locais, adicionando parsing independente. |
| F. Melhorar apenas o motor atual | Mantida como fallback | Continua válido se o upstream ficar indisponível; o novo gate é opt-in no OportunizaVaga público. |

## Aditivo: proposta de keywords (2026-11-07)

O backend upstream contém `extract_job_keywords`, que chama `complete_json` e portanto depende do provedor LLM configurado; a CLI pinada não expõe esse comando. Foi implementado em `bot/job_keyword_proposal.py` um extrator lexical genérico que recebe catálogo técnico do chamador: produz somente propostas com trechos de origem, exige revisão explícita e emite `JobKeywords` vinculado ao hash da descrição. A proposta bruta não satisfaz o schema aceito pelo gate. Essa escolha evita adicionar chamadas externas e tokens, com a limitação de que termos fora do catálogo podem faltar e a classificação de obrigatório/desejável precisa de revisão. A operação privada usa um lançador fino e mantém seu catálogo fora deste repositório; a descoberta pública não chama o extrator automaticamente nem processa vagas não técnicas.

## Aditivo: seleção do anexo no formulário (2026-11-07)

Foi adicionado `bot/attach_cv.py` para conectar o gate existente ao input do formulário. O helper reexecuta o gate ATS/Resume-Matcher com o anúncio e PDF atuais, exige um identificador estável e a identidade da vaga, procura uma única aba e um único input file e só seleciona quando o input está vazio. Um arquivo pré-selecionado diferente, input ambíguo, timeout ou erro bloqueia a operação. Depois da seleção, o verificador read-only compara novamente o hash dos bytes no navegador; o helper não clica em enviar, navega nem fecha a aba. A seleção do input pode disparar upload automático do portal, então os bytes podem sair do host; a saída declara `portal_receipt_verified: false` até confirmação visível. O caller precisa usar o lock compartilhado do Chrome.

## Aditivo: revisão tipada obrigatória no anexo e na intenção (2026-11-07)

O antigo booleano `--requirements-reviewed` foi removido porque não identificava qual vaga, perfil ou decisão humana havia sido revisada. `bot/job_requirement_review.py` emite proposta, assessment e recibo localmente; a proposta contém spans heurísticos e exige conferência da descrição completa, revisão explícita dos requisitos obrigatórios e evidências. Assessment e recibo ficam ligados por hashes ao anúncio e ao `ResumeData`. O código não declara elegibilidade: qualquer barreira obrigatória com status diferente de `MET` bloqueia o anexo.

`bot/attach_cv.py` agora exige os caminhos do perfil, assessment e recibo e revalida os três antes de selecionar. `estado.py intencao` revalida novamente antes de gravar o estado e persiste apenas hashes, status e quantidade de barreiras, não os caminhos nem o conteúdo privado. `add-aplicada` transfere essa auditoria hash-bound da intenção confirmada para o registro enviado. Falha de leitura, alteração ou divergência resulta em bloqueio tipado. O fluxo sem CV continua compatível; nenhum booleano legado libera anexos com CV.

## Aditivo: análise explícita da fila pública (2026-11-07)

`bot/compatibilidade_fila.py` permite analisar uma única vaga já triada, usando a descrição local vinculada à chave da fila, `JobKeywords` e recibo aprovados para o hash exato do anúncio, `ResumeData` em arquivo privado e a CLI oficial com revisão upstream fixada. A análise permanece opt-in e advisory: não altera ranking, não rejeita vaga e não envia candidatura. A persistência grava apenas métricas, lacunas e hashes na fila; caminhos locais ficam em sidecar owner-only. `descobrir.py prompt` só mostra o marcador enquanto os arquivos, hashes, identidade da vaga e permissões do sidecar continuarem válidos.

Esta extensão foi escolhida em vez de acionar análise em toda coleta porque os termos técnicos ainda exigem aprovação humana e a fila pública não possui uma etapa completa para requisitos não técnicos. O fluxo não gera `ResumeData` automaticamente e não representa compatibilidade de contratação. A descrição deve ser atualizada com `triar --refresh --key KEY` antes de refazer a análise se a fonte remota mudar.

O comando `analyze-batch` amplia a mesma decisão para até 50 chaves explícitas em manifesto owner-only. Ele processa serialmente, não muda o ranking, continua após falhas individuais e retorna `UNVERIFIABLE` para cada vaga que não pôde ser analisada. Um pin inválido ou manifesto inseguro bloqueia o lote antes de chamar o scorer. `--persist` grava relatórios de sucesso individualmente; sem a opção, o comando é somente leitura. O lote não cria specs, PDFs ou candidaturas.

Os relatórios também apontam `evidence_by_keyword`: referências a seções do `ResumeData` que contêm o termo literal após normalização de caixa, espaços e acentos. Não retornam trechos, nomes de seções personalizadas ou outros textos do currículo. Esse mapa melhora a rastreabilidade, mas não prova proficiência, experiência profissional ou equivalência semântica; a revisão humana continua necessária.

## Política do portão

- `APPROVED`: parsing `full`, score interno >= 80, 1 ou 2 páginas e sem falhas/avisos nos checks do parser.
- `REJECTED`: falha de severidade alta.
- `NEEDS_REVIEW`: parsing parcial, aviso/falha não crítica, score abaixo de 80 ou mais de 2 páginas.
- `UNVERIFIABLE`: ferramenta indisponível, timeout, resposta inválida ou nenhuma extração.

Somente `APPROVED` permite imprimir `ANEXAR`. A pontuação é heurística de parsing, não uma probabilidade de contratação nem uma nota oficial de ATS. O parser não verifica verdade factual; `cv_fatos.py` e a revisão baseada em evidências continuam necessários.

## Segurança e privacidade

O adaptador não usa shell, limita PDF a 4 MiB, não envia conteúdo para LLM e passa ao subprocesso apenas `PATH`, `HOME`, `DATA_DIR`, locale e configuração mínima de certificados. Variáveis como chaves de API não são encaminhadas. O subprocesso roda no diretório de dados do adaptador para não carregar `.env` do checkout do Resume-Matcher. O serviço web do upstream não é iniciado nem exposto.

Quando habilitado, o portão cria um manifesto JSON privado e imutável (modo 0600 dentro de diretório 0700) para o par exato de hashes SHA-256 do anúncio e do PDF. Antes de liberar `ANEXAR`, ele reabre o manifesto, confere política/revisão configuradas e rehash os dois arquivos. `estado.py intencao` registra hashes e identidade da vaga; caminhos, prefixo de URL e seletor são usados somente durante a validação e não persistem. A referência é transferida à candidatura confirmada por `add-aplicada`. A seleção do input está implementada, mas não prova o recebimento remoto do portal.

## Fontes

- [Repositório Resume-Matcher](https://github.com/srbhr/Resume-Matcher)
- [Release 1.4.0](https://github.com/srbhr/Resume-Matcher/releases/tag/v1.4.0)
- [Issue sobre MCP, parser ATS e banco local](https://github.com/srbhr/Resume-Matcher/issues/1011)
