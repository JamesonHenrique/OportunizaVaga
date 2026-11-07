# Testes e evidências da integração

## Testes sintéticos do adaptador

`tests/test_resume_matcher_bridge.py` cobre: aprovação limpa, falha crítica, aviso, parsing parcial, baixa pontuação, ausência de extração, contrato inválido, isolamento de variáveis de credencial, chamada do score estruturado e manifesto (persistência, idempotência, hashes de entrada e revisão).

`tests/test_cv_pronto.sh` gera um PDF com dados fictícios e usa um CLI falso para verificar: compatibilidade sem a flag nova, manifesto persistido e revalidado antes da liberação, bloqueio sem commit pinado, bloqueio em `NEEDS_REVIEW`, bloqueio se o CLI não está configurado e ausência de `ANEXAR` para arquivo ausente.

`~/candidaturas/tests/test_resume_matcher_wrapper.py` usa um portão ATS falso e um PDF sintético; verifica que o caminho só é exposto com `APPROVED` e que revisão necessária bloqueia. `test_cv_manifest_state.py` verifica que a referência validada atravessa `intencao` até `add-aplicada`, e que um PDF diferente não pode substituir a intenção.

`~/candidaturas/tests/test_cv_lote.py` cobre geração sequencial, retomada, perfil/vaga alterados, falhas tipadas, arquivo conflitante sem sobrescrita, revisão manual e o gate de compatibilidade anterior à geração. Os casos novos cobrem título/keywords vinculados, bloqueio e retomada com relatório. Um teste adversarial confirma que uma instrução maliciosa escrita na descrição da vaga não é encaminhada ao gerador; o spec permanece como a entrada autoritativa de conteúdo. Um teste composto usa o wrapper privado e a ponte reais com ATS e CLI fictícios; só cria perfil, descrição e PDF temporários.

`~/candidaturas/tests/test_vaga_compatibilidade.py` usa currículo e anúncios fictícios. Valida o mapeamento por seção, vínculo da extração ao hash/título, uso da ponte com diretório temporário isolado, falha fechada e, quando disponível, score upstream real.

`~/candidaturas/tests/test_compatibilidade_fila.py` usa fila fictícia e verifica CLI JSON, análise somente leitura, persistência sob o lock oficial, preservação do ranking, recusa de vaga fora de `nova`, conflito quando vaga muda no meio da análise e falha de saída inválida. `tests/test_descobrir.sh` confirma que um relatório só aparece para título e URL correspondentes e que o score visível da fila não muda. No uso privado, também compara o hash de perfil capturado no relatório com o hash atual do currículo mestre.

## Teste contra o upstream pinado

O teste de ponta a ponta deve usar PDF fictício gerado pelo `bot/gerar_cv.py`, com `DATA_DIR` separado em temporário, e chamar o executável real do checkout pinado. O processo deve registrar somente status, score, páginas e hash; nunca o preview de texto.

## Baseline conhecido antes da implementação

- Testes shell do OportunizaVaga: passavam antes desta mudança.
- `scripts/validate.sh` e compilação Python: passavam.
- `scripts/sanitize.sh` no checkout de trabalho já falhava devido a arquivos locais ignorados presentes antes da mudança. Eles foram preservados e não lidos.
- A suíte privada já tinha 291 casos aprovados e 13 falhas preexistentes não relacionadas; comparar com nova execução antes de atribuir regressão.
- Os testes JavaScript não encontravam `node` pelo PATH dentro do checkout; existe instalação local em `~/.local/share/fnm/node-versions/v24.21.0/installation/bin/node`.

Resultados observados nesta revisão:

| Comando | Resultado nesta revisão |
|---|---|
| Diagnóstico privado + fila + lote + manifesto | 40 passaram; inclui análise da fila com persistência, hashes contra alterações concorrentes, isolamento de perfil, 9 testes de compatibilidade, execução do adaptador/ponte em lote com gate e CLI falsos, isolamento entre vagas e score upstream real com perfil sintético |
| Adaptador `tests/test_resume_matcher_bridge.py` | 13 passaram |
| Fila OportunizaVaga `bash tests/test_descobrir.sh` | 20 passaram; marcador opcional validado sem mudança no score de descoberta |
| Smoke composto da fila privada | CLI upstream real no commit `d480551798b7aa97f5b57ba1972ee383bd882238`; perfil/vaga/queue fictícios; `ANALYZED`, 66,7% lexical, 66,7% skills, Docker ausente; fila sem alteração |
| Portão público `bash tests/test_cv_pronto.sh` | 9 passaram nesta revisão |
| Wrapper privado `tests/test_resume_matcher_wrapper.py` | 4 passaram |
| Persistência privada de referência `tests/test_cv_manifest_state.py` | 3 passaram |
| Lote privado `tests/test_cv_lote.py` | 17 passaram; inclui análise antes de renderizar, bloqueio fail-closed, isolamento por vaga e retomada sem regenerar |
| E2E sintético CLI real → wrapper privado → estado | `APPROVED`, manifesto revalidado, hashes herdados em `add-aplicada`; sem envio externo |
| Testes shell existentes do OportunizaVaga | 31 scripts passaram |
| Testes Python do OportunizaVaga (`pytest tests/`) | 44 passaram |
| Testes Node do monitor | 13 passaram com o diretório do Node instalado incluído no `PATH` |
| `scripts/validate.sh` | passou |
| Ruff, compilação Python e `git diff --check` | passaram |
| `scripts/sanitize.sh` em árvore temporária limpa com as alterações integradas | passou |
| CLI real, PDF sintético de uma página | `APPROVED`, score 100, extraibilidade full |
| CLI real, score de perfil/requisitos fictícios | keyword match 60%, score heurístico 64; sem LLM |
| Diagnóstico privado com CLI upstream real e dados fictícios | keyword match 75%, skills coverage 66,7%, Docker reportado ausente; processamento local e sem LLM |
| Gerador público + CLI real, perfil de exemplo incompleto | `NEEDS_REVIEW`, uma página, score 85, checks `garbled_glyphs`, `section_headings`, `dates`; corretamente bloqueado, sem `ANEXAR` |
| Wrapper privado + gate ATS público + CLI real, PDF e perfil fictícios | exit 0; um único caminho `ANEXAR`; hashes do anúncio e do PDF registrados |
| Suíte upstream `uv run --no-sync pytest -q` | 1971 passaram, 5 falharam, 7 ignorados, 2 desmarcados; falhas em testes de deadlines/retirement de processamento; ainda sem baseline independente do upstream |
| Reexecução dos cinco casos upstream que falharam | 3 testes de deadline falharam de novo por não atingir o evento dentro do limite de 0,2 s; 2 casos de retirement passaram isoladamente |
| Suíte privada `tests/run.sh` | Execução atual: 295 passaram, 14 falharam. A execução anterior disponível foi 294/14; o número de falhas permaneceu igual. As falhas são em verificações legadas de filtros/configuração, triagem e plugins, não relacionadas aos módulos de compatibilidade/fila ou ao prompt de descoberta alterados nesta integração. |
| `scripts/sanitize.sh` na árvore de trabalho original | continua bloqueado pela presença de arquivos locais ignorados preexistentes; eles foram preservados. A cópia temporária limpa foi usada para validar apenas os arquivos de código/documentação versionáveis. |

O teste do gerador mostra que o Resume-Matcher pode bloquear um PDF de exemplo incompleto, mesmo que o gerador termine e o ATS local aprove. Isso é comportamento fail-closed. Não use esse fixture sintético como conclusão sobre o currículo privado.

## Paginação e falha de extração (2026-11-07)

`tests/test_resume_pagination.py` usa um perfil fictício denso e confirma que um limite ausente continua sendo uma página, `max_paginas: 2` é a única exceção permitida e entradas inválidas são recusadas antes de criar o PDF. O teste também confirma que a extração preserva o último item do currículo. O gerador público e o gerador usado pelo checkout privado passaram no teste equivalente; o segundo é chamado pelo symlink `<private-candidaturas-checkout>/gerar_cv.py` que aponta para `<public-checkout>/bot/gerar_cv.py`.

O teste privado adicional percorreu o gerador, `pdfinfo`, o parser real pinado do Resume-Matcher, `cv-pronto-integrado.sh` e `cv-lote.py` com anúncio/perfil sintéticos. O parser reportou duas páginas, extraibilidade `full` e checks aprovados; o gate liberou `ANEXAR` com manifesto verificado para o par exato. O lote preservou `page_count: 2` e retornou `attach_path` cujo hash corresponde ao manifesto e à descrição. A inspeção das duas imagens confirmou A4, coluna única e corpo em 9,5 pt, legível no fixture. Não houve dados reais, LLM, portal ou envio. Testes diretos também confirmam que texto extraído ausente ou vazio retorna erro de verificação nos dois geradores, sem aprovação silenciosa.

## Validação adicional de 2026-11-07

O fixture anterior de PDF incompleto continua sendo um caso negativo válido. Um novo fixture sintético completo identificou as causas concretas: `•` virava `(cid:127)` no parser e `Habilidades técnicas` não correspondia ao sinônimo exato de seção `Habilidades`; o fixture também posicionava o e-mail na primeira linha de metadados, que é substituída pelo cargo-alvo. A correção alterou somente a saída do gerador: hífen ASCII, título renderizado `Habilidades` e autochecagem para esse alias. O texto mestre não foi renomeado e a regra de bloqueio não foi reduzida.

| Comando/fluxo | Resultado observado |
|---|---|
| `pytest tests/test_resume_matcher_pdf_compatibility.py -q` | 2 passaram: gerador usado pela operação privada e cópia do OportunizaVaga; CLI real pinado, uma página, parsing 100, todos os checks `pass` |
| E2E sintético `cv-lote.py --require-compatibility` | `ANALYZED` + `APPROVED`; score heurístico de keywords 100%, parser 100, uma página, manifesto verificado e caminho de anexo correspondente ao PDF/hash exatos |
| Lote E2E de três vagas fictícias | 3/3 `APPROVED`, PDFs distintos e manifestos vinculados a cada descrição; 27,31 s total, 9,10 s/item sequencial, sem LLM. Não mede 50 vagas nem concorrência. |
| Testes focados privados de compatibilidade, fila, lote, estado, wrapper e PDF | 47 passaram |
| `tests/test_resume_matcher_bridge.py` | 13 passaram |
| `bash tests/test_descobrir.sh` + `bash tests/test_cv_pronto.sh` | 20 + 9 passaram |
| `bash tests/run.sh` | 295 passaram e 14 falharam; as mesmas 14 falhas legadas já observadas antes, em filtros/configuração, triagem, plugins e guardas de ferramentas, fora dos módulos alterados nesta integração |
| Ruff nos dois geradores, compilação Python e `git diff --check` | passaram |

O E2E chama parsing e score locais, não um serviço de contratação. A liberação de caminho não equivale a upload, candidatura enviada ou recomendação de contratação.

A inspeção visual do PDF sintético confirmou uma coluna, hierarquia simples, contato legível e corpo em 12 pt; o fixture é deliberadamente curto e deixa espaço livre na página. Isso valida a renderização básica e a legibilidade do exemplo, não o aproveitamento visual de currículos reais mais extensos.

## Revalidação da intenção de envio (2026-11-07)

`estado.py intencao` agora recebe os caminhos exatos do anúncio e do `attach_path`, rehasha os arquivos e chama o wrapper integrado novamente antes de persistir os hashes. A chamada do parser ocorre fora da trava do estado; imediatamente antes de gravar, os arquivos são rehashados sob a trava para detectar alteração durante a verificação.

| Verificação | Resultado |
|---|---|
| `tests/test_cv_manifest_state.py`, `tests/test_cv_lote.py`, wrapper, análise de compatibilidade e compatibilidade dos PDFs | 42 passaram; inclui E2E com wrapper/bridge reais e dependências sintéticas, associação do lote ao registro de intenção, bloqueio de PDF alterado e concorrência do gate sem bloquear outras gravações de estado |
| `bash tests/run.sh estado` | 50 passaram |
| `bash tests/test_descobrir.sh`, `bash tests/test_cv_pronto.sh`, `tests/test_resume_matcher_bridge.py` | 20, 9 e 13 passaram |
| Regressão privada completa `bash tests/run.sh` | 295 passaram, 14 falharam em verificações legadas de triagem/configuração/plugins; os testes da integração e o filtro de estado passaram |

Os testes de intenção usam dados e arquivos sintéticos. Eles demonstram que o estado não aceita um caminho/hash diferente do par aprovado e, no OportunizaVaga, bloqueia quando o verificador simulado não observa o arquivo esperado. Não usam Chrome real nem substituem um teste de upload autorizado.

## Integração pública de intenção e arquivo selecionado

`tests/test_cv_intent_gate.py` executa `bot/estado.py intencao` contra gates locais fictícios. Cobre aprovação do par anúncio/PDF, gravação somente dos três hashes, herança para `add-aplicada`, bloqueio de hash selecionado divergente, referência parcial, ausência de seletor, `DO_NOT_PREPARE`, arquivo alterado entre preflight e trava de estado, tentativa de remover a referência numa repetição e compatibilidade da intenção antiga sem manifesto.

`tests/test_verificar_anexo.py` usa um cliente CDP simulado: confere arquivo correto em iframe, hash incorreto, inputs múltiplos, aba ambígua, frame indisponível, prefixo de URL e que o verificador não clica, navega ou fecha abas. `tests/test_cv_intent_e2e_resume_matcher.py` gera um currículo totalmente fictício, chama o parser local pinado real, passa pelo gate, usa um verificador de navegador sintético e confere a associação dos hashes em `intencao` e `add-aplicada`. Ele é pulado se o CLI local ou ReportLab não estiver disponível.

Após essa alteração, `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/ -q` passou com 60 testes; `bash tests/test_estado.sh` passou com 30/30; `bash tests/test_cv_pronto.sh` com 9/9; `bash tests/test_descobrir.sh` com 20/20; e `bash scripts/validate.sh` passou. `py_compile` e `git diff --check` também passaram. Os dados desses testes são sintéticos; upload para portal ainda não foi testado.

## E2E local em Chrome real (2026-11-07)

Um harness local da operação privada exercitou os gates de intenção privado e público usando currículo gerado de dados sintéticos, ATS/Resume-Matcher reais e CLI no commit `d480551798b7aa97f5b57ba1972ee383bd882238`. O formulário serviu apenas em `127.0.0.1`; o Chrome usou perfil temporário e a sessão compartilhada não foi tocada.

| Fluxo | Arquivo ausente | Hash divergente | PDF aprovado exato | Estado persistido |
|---|---|---|---|---|
| `candidaturas/estado.py intencao` | Bloqueou, sem intenção | Bloqueou, sem intenção | Gravou intenção com hashes do manifesto | Sem caminhos; `aplicadas` vazia |
| `OportunizaVaga/bot/estado.py intencao` | Bloqueou, sem intenção | Bloqueou, sem intenção | Gravou intenção com hashes do manifesto | Sem caminhos; `aplicadas` vazia |

Após as recusas e aprovações do gate, o harness enviou o PDF ao endpoint sintético em `127.0.0.1`, confirmou a resposta e o SHA-256 recebido, e só então executou `add-aplicada`. O registro final herdou os hashes aprovados e removeu a intenção pendente. A submissão local foi uma simulação controlada; nenhuma candidatura real foi submetida. O harness não faz parte da suíte pública versionada e não valida upload a portal ou recebimento remoto.

No mesmo ciclo, a regressão pública focada `uv run --offline --with pytest --with reportlab pytest tests/test_cv_intent_gate.py tests/test_cv_intent_e2e_resume_matcher.py tests/test_resume_matcher_bridge.py tests/test_verificar_anexo.py -q` passou com 29 testes. Essa suíte mantém o verificador de navegador simulado; o Chrome real foi validado somente pelo harness E2E local descrito acima.

Em 2026-11-07, o harness privado `~/candidaturas/tests/e2e_cv_intent_chrome.py` foi ampliado para passar por `cv-lote.py --require-compatibility` antes dos dois gates `estado.py intencao`. Com dados fictícios e CLI upstream pinada real, o teste confirmou título e hash da vaga na análise, PDF aprovado de uma página, rejeição de arquivo ausente e hash divergente, intenção vinculada aos hashes e identidade corretos, recebimento do mesmo PDF no endpoint local e registro sintético em `add-aplicada` somente após confirmação. O fluxo privado usou o seletor baseado na linha aprovada do lote; o fluxo público usou `bot/attach_cv.py` e repetiu o gate local. A recomendação heurística foi `REVIEW_UNCONFIRMED_REQUIREMENTS`, mantendo explícita a necessidade de revisão humana. O teste usa Chrome descartável em localhost, não envia candidaturas reais e não comprova upload ou recebimento em portal.

## Proposta local de keywords com revisão explícita

O núcleo lexical genérico está em `bot/job_keyword_proposal.py` neste repositório. Ele recebe um catálogo explicitamente fornecido, não chama LLM, não lê perfil de candidato e produz apenas uma proposta `NEEDS_REVIEW`. O lançador privado `~/candidaturas/extrair_keywords_vaga.py` carrega esse núcleo e fornece o catálogo privado local. O operador revisa todos os IDs, seleciona os termos, vincula termos manuais a spans exatos e confirma o prefixo do SHA-256 da descrição antes de gerar o `JobKeywords` consumível pelo gate. A proposta bruta é rejeitada pelo contrato existente. A coleta de portais e `cv-lote.py` ainda não chamam essa etapa automaticamente.

O smoke anterior, antes de mover o núcleo genérico ao repositório público, percorreu anúncio e perfil fictícios, `NEEDS_REVIEW` → recibo `APPROVED` → CLI pinada real no commit `d480551798b7aa97f5b57ba1972ee383bd882238`, com score determinístico 66,7% lexical/66,7% skills e Docker ausente. Após a refatoração, o smoke foi repetido via lançador privado, que carregou o núcleo público e o catálogo privado local: revisou três candidatos fictícios, aprovou três termos e chamou a ponte pública com o CLI real pinado. O score lexical foi 66,7%, com Docker ausente. Não houve LLM nem dados reais de candidato.

| Verificação | Resultado observado neste checkpoint |
|---|---|
| Testes Python públicos `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/` | 73 passaram, incluindo paginação e falha de extração fail-closed |
| Testes privados focados de currículo, lote, manifesto, compatibilidade, fila, anexo e wrapper | 88 passaram |
| `tests/test_resume_matcher_pdf_compatibility.py` | 20 passaram; inclui duas páginas nos geradores privado/público, parser real pinado, gate integrado com manifesto exato e extração não verificável bloqueada |
| `bash tests/test_cv_pronto.sh` | 9/9 passaram; casos de aprovação, revisão, manifesto, falha de auditoria e PDF ausente |
| `bash scripts/validate.sh` no OportunizaVaga | passou |
| `py_compile`, `git diff --check` | passaram nos arquivos novos do núcleo e do lançador |
| Smoke via lançador privado, ponte e CLI Resume-Matcher real | `NEEDS_REVIEW` → `APPROVED`; anúncio e currículo fictícios; 66,7% de match lexical, Docker ausente; commit `d480551798b7aa97f5b57ba1972ee383bd882238` |
| `bash tests/test_descobrir.sh` | 20 passaram; inclui ocultar o marcador quando o hash do perfil não corresponde |
| Regressão privada completa `bash tests/run.sh` | 298 passaram, 14 falharam no runner offline. O filtro isolado `bash tests/run.sh vaga_check` passou 4/4; as falhas de execução completa incluem triagem, políticas de filtro, funil e guardas/plugins e seguem sem diagnóstico causal. |

A extração por catálogo pode omitir termos ausentes e sugerir classificação errada; os números do Resume-Matcher continuam heurísticos e não equivalem à probabilidade de contratação. Nenhum dado real de candidato é usado nos testes sintéticos.

## Benchmark sintético de parsing e gate (2026-11-07)

O script de benchmark do checkout privado comparou cada PDF sintético no gate ATS legado, parser `parse_check_file` do Resume-Matcher pinado e gate integrado. `uv run --offline --with reportlab python tests/benchmark_resume_matcher_quality_synthetic.py` terminou com `PASS`: o PDF limpo do gerador atual foi aprovado pelos três caminhos (parser score 100); o fixture legado foi aprovado pelo gate ATS antigo, recebeu score 85 e avisos `garbled_glyphs`/`section_headings` no Resume-Matcher, e foi retido pelo gate integrado como `NEEDS_REVIEW` sem liberar caminho. A regressão `uv run --offline --with pytest --with reportlab pytest tests/test_resume_matcher_pdf_compatibility.py -q` passou com 3 testes.

Os tempos foram medidos nesta máquina, sem LLM, serviço externo, dados reais ou candidatura. A inspeção visual do PDF atual confirmou uma coluna e texto legível, mas o fixture curto deixa muito espaço em branco. O teste não compara um currículo gerado pelo renderer do Resume-Matcher: na revisão pinada, a CLI valida conteúdo escrito pelo chamador e a exportação PDF exige o frontend. Não é um score oficial de ATS nem evidência de contratação. A tabela e o método completos estão em `docs/resume-matcher-integration/10-benchmark.md` no checkout público.

## Revalidação das suítes (2026-11-07)

| Comando | Resultado atual | Interpretação |
|---|---|---|
| `bash tests/run.sh` no checkout privado | Exit 1; 300 passaram e 14 falharam em 2026-11-07 | As falhas visíveis seguem em triagem/filtros/configuração, paridade da CLI, guardas/plugins e funil; nenhuma está nos testes focados do pipeline de currículo. A suíte completa continua sem estar verde. |
| `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/ -q` no OportunizaVaga | 84 passaram | Suíte Python pública completa verde após adicionar o seletor hash-bound. |
| Testes focados do seletor público, gate de intenção, verificador, bridge e paginação | 48 passaram | Executados com fixtures sintéticos e CDP falso; não acessaram Chrome compartilhado nem portal. |
| `bash tests/test_cv_pronto.sh` | 9/9 passaram | O gate existente continua bloqueando falha, timeout, manifesto inválido e PDF ausente. |
| `python3 <private-candidaturas-checkout>/tests/e2e_cv_intent_chrome.py` | `PASS`; fluxo privado e público, zero candidaturas reais | Chrome headless com perfil temporário, endpoint HTTP sintético em loopback, CLI Resume-Matcher pinada e seletores correspondentes a cada checkout. |
| Testes focados privados de currículo/lote/manifesto/compatibilidade/fila/anexo/wrapper | 88 passaram | Inclui gate real pinado para PDF sintético de duas páginas e bloqueio de extração vazia. |
| Benchmark e regressão de compatibilidade do PDF no checkout privado | Benchmark `PASS`; 20 testes de compatibilidade passaram | Confirma parsing/gate de PDF limpo, bloqueio do fixture legado e aceitação controlada da exceção de duas páginas. |

## Revalidação da revisão tipada no anexo e na intenção (2026-11-07)

O booleano `--requirements-reviewed` foi retirado do helper público. Os testes agora criam `ResumeData`, assessment e recibo sintéticos em arquivos `0600`, vinculados ao anúncio e ao título exatos. A cobertura verifica anexo aprovado, recibo ausente, recibo adulterado, avaliação obsoleta, barreira obrigatória `UNCONFIRMED`/`NOT_MET`, persistência somente de auditoria segura, associação vaga/PDF e transferência da referência para `add-aplicada` após confirmação.

| Comando | Resultado |
|---|---|
| `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/test_job_requirement_review.py tests/test_cv_intent_gate.py tests/test_attach_cv.py tests/test_cv_intent_e2e_resume_matcher.py -q` | 39 passaram |
| `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/ -q` | 121 passaram |
| `bash tests/test_cv_pronto.sh` | 9/9 passaram |
| `bash tests/test_descobrir.sh` | 20/20 passaram |
| Testes focados privados `test_revisar_requisitos_vaga.py`, `test_attach_cv.py`, `test_cv_manifest_state.py`, `test_cv_lote.py` | 55 passaram |
| `uv run --offline --with reportlab python tests/e2e_cv_intent_chrome.py` | `PASS`; gate público e privado, Chrome descartável e formulário localhost |
| `py_compile`, `python3 -m json.tool config/aplicadas.schema.json`, `--help` | passaram |

O E2E confirma o hash dos bytes recebidos pelo endpoint sintético, uma submissão local por fluxo, associação ao manifesto e registro somente após a resposta `CONFIRMED`. Não acessa portais reais nem o Chrome compartilhado; `real_applications_submitted=0`. Upload remoto real, operação em portal e recibos de ATS comercial não foram testados.

## Suíte privada ampliada — reexecução atual (2026-11-07)

`bash tests/run.sh` terminou com **307 aprovados e 8 falhas**. As falhas exibidas estão nos blocos de triagem `vaga_check`, limite Gmail, paridade OSS, golden set, funil e filtros. Nenhum desses casos é teste do novo gate de currículo; isso não substitui a análise causal de cada falha nem prova que as mudanças preexistentes não contribuíram. A suíte focada privada e o E2E sintético público/privado passaram.

O runner privado declara executar sobre cópias temporárias e substituir o notificador por um stub; a execução foi feita sem abrir o Chrome compartilhado e sem envio externo. O diagnóstico e a atribuição causal das oito falhas permanecem pendentes.

## Revalidação do sidecar da análise de fila pública (2026-11-07)

| Verificação | Resultado |
|---|---|
| `PYTHONPATH=. uv run --offline --with pytest pytest tests/test_compatibilidade_fila.py -q` | 7 passaram; inclui CLI Resume-Matcher pinada com dados sintéticos e sidecar rejeitado quando o diretório perde permissões privadas |
| `bash tests/test_descobrir.sh` | 20/20 passaram; inclui ocultação de relatório desatualizado |
| `bash tests/test_cv_pronto.sh` | 9/9 passaram; os gates existentes continuam fail-closed |
| `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/ -q` | 91 passaram |
| `python3 -m py_compile bot/compatibilidade_fila.py bot/descobrir.py tests/test_compatibilidade_fila.py` e `git diff --check` | passaram |

Os dados são sintéticos e a CLI upstream é a revisão local pinada. Não houve acesso ao Chrome compartilhado ou a portais, nem candidatura enviada. A suíte cobre permissões do sidecar no POSIX; o fallback de leitura usado em Windows não foi exercitado neste checkpoint.

## Lote público de análises (2026-11-07)

`tests/test_compatibilidade_fila.py` verifica lote com três entradas sintéticas: duas vagas `nova` são analisadas e persistidas em relatórios separados; uma vaga já enviada resulta em `UNVERIFIABLE`, sem interromper a terceira. O teste confirma execução serial (duas chamadas ao scorer), ausência de caminhos de perfil na saída e que a entrada não analisável não recebe relatório. Outro caso rejeita chaves duplicadas antes de qualquer chamada ao scorer. O pin ausente também é recusado antes de pontuar o perfil. Um teste de processo chama `analyze-batch` com o CLI upstream pinado real e entradas sintéticas, incluindo o status parcial e o código de saída. As referências de evidência contêm somente rótulos de seção, sem trechos do perfil ou nomes personalizados. A suíte pública completa passou com 96 testes; o lote não gerou PDFs, anexos ou envios.

No checkout privado, a suíte focada de geração, compatibilidade, lote, manifesto e anexo passou com 113 testes. O benchmark `tests/benchmark_cv_lote_synthetic.py` processou 50 PDFs fictícios: 50 aprovados, 50 caminhos únicos e 50 pares de hashes verificados em 236,05 s. Essa execução não habilitou `--require-compatibility`; a combinação de análise de vaga e geração foi testada em lotes menores, não em 50 itens. Os testes não acessaram portais nem enviaram candidaturas.

## Lote privado de 50 com compatibilidade e revisão tipada obrigatórias (2026-11-07)

O benchmark privado cria `JobKeywords`, assessments e receipts sintéticos por vaga, todos associados aos hashes de entrada, e executa `cv-lote.py --require-compatibility --require-requirements-review`. O relatório confere título, hash de anúncio/perfil/keywords/assessment/receipt, revisão upstream e checkpoint por vaga. O ambiente temporário configura explicitamente o core de requisitos e as regras OSS necessários.

| Verificação | Resultado |
|---|---|
| `python3 -m py_compile tests/benchmark_cv_lote_synthetic.py` | passou |
| Benchmark com 1 vaga | `PASS`; 1 análise e 1 par de hashes em 10,028 s |
| Reexecução com 50 vagas e os dois gates obrigatórios | `PASS`; 50 PDFs aprovados, 50 análises vinculadas, 50 revisões tipadas aprovadas, 50 caminhos únicos, todos com uma página, 501,277 s |
| Scores reportados | Parser PDF: 100 em 50/50; match lexical: 66,7 em 50/50; cobertura técnica: 100 em 50/50 |
| Recomendações da análise | 50 `REVIEW_PROFILE_GAPS`; nenhuma vaga foi classificada como elegível automaticamente |
| Privacidade e efeitos externos | Identidade sintética ausente do estado/logs; nenhum LLM ou envio externo |

Os assessments são fixtures sintéticos, não revisão humana real, e o benchmark não executa `propose/approve` de keywords para cada descrição. `APPROVED` valida os artefatos e suas associações; os avisos `REVIEW_PROFILE_GAPS` continuam exigindo revisão humana de compatibilidade. O benchmark não comprova upload em portal real, elegibilidade, qualidade de contratação ou desempenho em outra máquina.

## Revisão hash-bound de requisitos não técnicos — 2026-11-07

`tests/test_job_requirement_review.py` cobre extração de trechos por categoria, citação exata, confirmação de candidatos, classificação tipada, evidências vinculadas a seções existentes, requisitos manuais por offsets, confirmação explícita quando nenhum cue é encontrado, invalidação por alteração da vaga/perfil/assessment e tratamento inerte de texto de prompt injection. Também confere permissões `0600` e recusa sobrescrita.

`tests/test_compatibilidade_fila.py` cobre integração na análise individual e em lote, estado `NOT_REVIEWED` sem recibo, status `REVIEW_POSSIBLE_BARRIER`, revalidação antes/depois do score, ocultação do marcador após alteração do assessment, isolamento de arquivos no sidecar e recusa de manifesto com apenas metade do par de revisão.

| Verificação | Resultado |
|---|---|
| `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/test_job_requirement_review.py tests/test_compatibilidade_fila.py -q` | 28 passaram |
| `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/ -q` | 112 passaram |
| `bash tests/test_descobrir.sh` | 20/20 passaram |
| `bash tests/test_cv_pronto.sh` | 9/9 passaram |
| `py_compile`, `--help` e `git diff --check` | passaram |

Todos os dados são sintéticos; não houve acesso ao Chrome compartilhado, leitura do estado privado de candidaturas, upload, envio real ou chamada a LLM. Esse parágrafo descreve o checkpoint daquela etapa; os checkpoints posteriores abaixo registram a integração subsequente ao lote privado e aos gates de anexo/intenção.

## Lote privado com revisão tipada obrigatória — revalidação 2026-11-07

`candidaturas/cv-lote.py` foi revalidado exigindo o assessment e o recibo hash-bound por item; em vagas técnicas também exigiu análise de compatibilidade do Resume-Matcher. A suíte focada cobriu revisão obrigatória ausente ou não resolvida, alteração de perfil e dos arquivos de revisão, conflitos de chave/saída, retomada, associação entre currículo e vaga, erro do gerador, instruções hostis dentro do anúncio e revalidação no registro de intenção.

| Verificação | Resultado observado |
|---|---|
| Testes focados de lote, revisão, anexo, manifesto e compatibilidade | 68 passaram |
| `uv run --offline --with reportlab python tests/e2e_cv_intent_chrome.py` | `PASS`; ambos os checkouts, PDF exato recebido em localhost com hash confirmado, arquivo vazio e hash errado bloqueados sem mudança de estado, zero candidaturas reais |
| `python3 cv-lote.py --help` | mostra `--require-compatibility` e `--require-requirements-review` |
| Benchmark sintético de 50 vagas com os dois gates | `PASS`; 50 PDFs associados, detalhes em [10-benchmark.md](10-benchmark.md) |

O E2E usa Chrome headless descartável e servidor loopback; não acessa o perfil Chrome compartilhado ou portais reais. Os 50 assessments são fixtures, não revisão humana. Portanto, essas evidências validam o pipeline local de geração, verificação, associação e recebimento sintético, mas não upload real, elegibilidade nem envio de candidatura. A suíte privada completa foi reexecutada: 307 testes passaram e 8 falharam em triagem, limite Gmail, paridade OSS, golden set, funil e filtros; o diagnóstico causal continua pendente.

## Revisão factual final hash-bound no gate público — 2026-11-07

`tests/test_cv_content_review.py` usa PDFs e fontes sintéticas para verificar proposta/planilha, recibo aprovado, decisão não suportada/não confirmada, referência ausente, entrada malformada, fonte alterada, PDF inválido, caminho simbólico, permissão `0600`, adulteração do assessment/receipt, limite de saída do parser e timeout. A extração lê `stdout` em pipe, guarda no máximo 1 MiB + 1 byte e encerra o processo se ultrapassar o limite ou exceder 30 segundos; o parser recebe os mesmos bytes do PDF que são hashados. Os arquivos de saída só podem ser criados em diretório owner-only e não sobrescrevem arquivos existentes.

`tests/test_attach_cv.py` e `tests/test_cv_intent_gate.py` agora verificam que a revisão final é obrigatória antes de abrir o Chrome e antes de gravar `intencao`. O estado herda os hashes e contagens do recibo somente após preflight aprovado, sem persistir os caminhos privados. O E2E de geração cria a revisão com fixture sintético e a revalida durante o registro da intenção.

| Verificação | Resultado observado |
|---|---|
| Testes focados `test_cv_content_review.py`, `test_cv_intent_gate.py`, `test_attach_cv.py` | 37 passaram |
| E2E `test_cv_intent_e2e_resume_matcher.py` | 1 passou; gerador, CLI Resume-Matcher pinada e gate de conteúdo até intenção sintética |
| Suíte Python pública `PYTHONPATH=. uv run --offline --with pytest --with reportlab pytest tests/ -q` | 139 passaram |
| `bash tests/test_cv_pronto.sh` | 9/9 passaram |
| `bash tests/test_descobrir.sh` | 20/20 passaram |
| `py_compile`, Ruff, parse do schema e `git diff --check` | passaram |

Os testes preenchem recibos sintéticos por código para validar o contrato; não comprovam julgamento factual humano, revisão de currículo real, upload em portal ou envio de candidatura. O checkout privado ainda não está ligado a `cv_content_review.py`; não extrapole o resultado público para a operação privada.
