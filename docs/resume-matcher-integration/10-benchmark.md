# Benchmark sintético de parsing e gate

## Escopo e método

Executado em 2026-11-07 com o Resume-Matcher no commit `d480551798b7aa97f5b57ba1972ee383bd882238` e exclusivamente com perfil, vaga e PDFs fictícios. Os mesmos bytes passaram por três caminhos: gate ATS legado (`cv-pronto.sh`), parser isolado do Resume-Matcher (`parse_check_file`) e gate integrado (`cv-pronto-integrado.sh`). O PDF atual foi produzido pelo gerador ReportLab do projeto; o caso legado é um fixture ReportLab com bullets tipográficos e heading que o parser não reconhece.

Comando reproduzível a partir do checkout privado que contém o script:

```bash
cd <checkout-privado-de-candidaturas>
uv run --offline --with reportlab python tests/benchmark_resume_matcher_quality_synthetic.py
```

O script verifica o commit pinado, cria arquivos temporários com permissão restrita, não usa LLM nem serviços externos e remove os fixtures ao terminar. Os tempos abaixo são desta máquina e não devem ser comparados como promessa de latência em outro ambiente.

## Resultados observados

| Caso | Gerador | ATS legado | Parser Resume-Matcher | Gate integrado |
|---|---:|---|---|---|
| PDF limpo do gerador atual (2.447 bytes) | 0,1733 s | `APPROVED`, caminho liberado (0,0504 s) | score 100, extração completa, 1 página, nenhum check não aprovado (4,1026 s) | `APPROVED`, manifesto e hashes da vaga/PDF conferidos, caminho liberado (4,3814 s) |
| Fixture legado com bullets/headings (1.781 bytes) | Fixture pronto | `APPROVED`, caminho liberado (0,0489 s) | score 85, extração completa, 1 página; checks `garbled_glyphs` e `section_headings` não passaram (4,1192 s) | `NEEDS_REVIEW`, sem caminho liberado nem manifesto aprovado (4,3058 s) |

Resultado geral do benchmark: `PASS`. O gate integrado aprovou o PDF limpo e reteve o fixture legado que o gate ATS antigo liberava apesar dos avisos independentes do parser. O teste de regressão `tests/test_resume_matcher_pdf_compatibility.py` passou com **3 testes** usando o mesmo CLI pinado.

## Inspeção visual

O PDF limpo renderiza em uma coluna, com hierarquia simples de seções, texto extraível e tamanho visualmente legível. O fixture é curto e ocupa apenas a parte superior da página, deixando bastante espaço vazio; isso não mede o aproveitamento de um currículo real mais denso. O fixture legado tem apresentação tipográfica simples e bullets, mas a checagem automática detecta problemas de glifos e identificação de seções. Essa inspeção é um sanity check de dois fixtures, não uma comparação visual ampla entre templates.

## Limites da comparação

- O teste compara gate ATS anterior, parser Resume-Matcher e gate integrado sobre os mesmos PDFs. Não compara três geradores independentes.
- Na revisão do commit pinado, `tailor_and_verify` valida `resume_data` escrito pelo chamador; não redige autonomamente o currículo. `export_resume_pdf` depende do frontend, então não foi comparado um PDF produzido pelo renderer do Resume-Matcher.
- `score 100` e `score 85` são resultados do parser neste fixture, não notas oficiais de ATS nem probabilidades de contratação.
- Não foram usados dados reais, candidaturas, portais, upload externo, LLM ou chamadas pagas.

## Próximas medições

Ampliar a avaliação visual com perfis sintéticos mais densos e variantes de desenvolvimento, QA/suporte e experiência inicial; testar inglês e o caso em que conteúdo essencial exige uma segunda página. A recepção em portal real permanece sem validação e requer um ambiente de teste autorizado.

## Lote privado de 50 PDFs sintéticos

O baseline PDF-only de 2026-11-07, executado antes de ativar `--require-compatibility`, gerou 50 specs, anúncios e perfis fictícios em diretório temporário e passou pelo `cv-lote.py`, gerador existente, gate ATS e parser local pinado. Resultado: `PASS`; 50/50 aprovados, 50 caminhos únicos, 50 pares de hashes/manifestos verificados, todos com uma página e score do parser 100; revisão `d480551798b7aa97f5b57ba1972ee383bd882238`. Tempo total 236,050 s (4,721 s/item; 12,709 itens/min), com 123.080 bytes agregados.

Na primeira revalidação final, o script passou a exigir `--require-compatibility --require-requirements-review` em todas as linhas. Confere título, hashes do anúncio, perfil, keywords, assessment e receipt, revisão upstream e resumos salvos no checkpoint. O teste de fumaça com um item passou em 10,016 s; a primeira execução de 50 vagas levou 496,064 s. Na reexecução mais recente, o lote passou em `501,277 s` (10,026 s/item; 5,985 itens/min), com 50/50 PDFs aprovados, 50 análises `ANALYZED`, 50 revisões tipadas `APPROVED` com zero barreiras obrigatórias, 50 pares de hashes, 50 caminhos únicos e todos os PDFs com uma página (123.080 bytes agregados). O parser marcou score 100 em todos os PDFs; o score de vaga foi 66,7 de match lexical e 100 de cobertura técnica em todos os fixtures. O Resume-Matcher permaneceu na revisão pinada `d480551798b7aa97f5b57ba1972ee383bd882238`.

As 50 recomendações foram `REVIEW_PROFILE_GAPS`. Portanto, o resultado comprova geração, verificação e associação em lote com revisões tipadas sintéticas, mas não indica compatibilidade suficiente para candidatura. As `JobKeywords` foram fixtures sintéticas hash-bound; o benchmark não executou `propose/approve` para cada descrição, nem simula revisão humana real. A saída `APPROVED` refere-se ao artefato e às revisões sintéticas, não à elegibilidade. A identidade sintética não apareceu no estado nem nos logs; não houve LLM ou candidatura externa. Os artefatos temporários foram removidos ao final. Esse benchmark não mede concorrência, pico de memória ou desempenho em outros equipamentos.

As 50 entradas usam um único perfil sintético com Java, Spring Boot, API REST e Docker, sempre com a categoria `Backend`; variam empresas, descrições e cinco títulos relacionados. Portanto, essa medição comprova throughput sequencial e associação dos artefatos, mas não cobre famílias distintas como QA, suporte, frontend/React, dados, Python ou Rust. A avaliação semântica por família continua pendente.
