# Instalação e operação

## Versão local usada nesta integração

Clone isolado em `~/tools/Resume-Matcher`, checkout detached em `d480551798b7aa97f5b57ba1972ee383bd882238` (versão 1.4.0), Python 3.13.5. Instalação atual feita com:

```bash
cd ~/tools/Resume-Matcher/apps/backend
uv sync --extra dev
```

O `SETUP.pt-BR.md` examinado indica `uv sync --group dev`, mas o `pyproject.toml` atual define `dev` como extra; esse comando documentado falha na revisão testada. A árvore local não contém dados reais de perfil.

## Configuração do gate público

O recurso é opt-in para manter instalação do OportunizaVaga sem dependência obrigatória:

```bash
export OV_RESUME_MATCHER_REQUIRED=1
export OV_RESUME_MATCHER_CLI="$HOME/tools/Resume-Matcher/apps/backend/.venv/bin/resume-matcher"
export OV_RESUME_MATCHER_REVISION=d480551798b7aa97f5b57ba1972ee383bd882238
```

Opcionalmente, defina `OV_RESUME_MATCHER_DATA_DIR` para um diretório local de dados privado ao usuário. Sem essa variável, o adaptador usa `~/.local/share/oportunizavaga/resume-matcher` (permissão inicial 0700); em POSIX, diretórios configurados com acesso de grupo/outros são recusados. O manifesto usa `~/.local/share/oportunizavaga/resume-matcher/manifests`, ou `OV_RESUME_MATCHER_MANIFEST_DIR`; cada entrada armazena somente hashes, resultado do parser, versão/política e data, sem descrição nem texto do currículo. Alternativa ao executável: `OV_RESUME_MATCHER_BACKEND_DIR` com o diretório absoluto `apps/backend` e `uv` disponível. Não configure as duas formas ao mesmo tempo.

```bash
bot/cv-pronto.sh /caminho/absoluto/anuncio.txt /caminho/absoluto/cv.pdf
```

Sem a flag `OV_RESUME_MATCHER_REQUIRED=1`, o portão mantém o comportamento pré-integração. Com a flag, qualquer erro do CLI bloqueia a liberação.

## Revisar requisitos e selecionar o PDF aprovado

Antes de selecionar o PDF, faça uma revisão tipada e hash-bound dos requisitos da vaga. O código determinístico só propõe trechos; uma pessoa precisa conferir a descrição oficial completa, corrigir os candidatos e marcar obrigatoriedade, status e referências de evidência. A revisão não decide elegibilidade.

```bash
python3 bot/job_requirement_review.py propose \
  --job /caminho/absoluto/anuncio.txt \
  --title 'TÍTULO OFICIAL' \
  --profile /caminho/privado/ResumeData.json \
  --out /caminho/privado/requisitos.proposal.json \
  --review-template /caminho/privado/requisitos.review.json
```

Complete todos os itens da planilha. Se nenhum trecho for sugerido, confirme explicitamente que a descrição inteira não contém outros requisitos; adicione requisitos omitidos com offsets exatos. Em `approve`, confirme os 12 primeiros caracteres dos hashes atuais do anúncio e do perfil. Depois, execute `verify` para os mesmos arquivos e título. Somente `APPROVED` com zero barreiras obrigatórias libera a vaga para revisão do currículo; isso não aprova a candidatura.

Guarde perfil, assessment e recibo em diretório privado (`0700`, arquivos `0600`). O helper e `estado.py intencao` revalidam esses arquivos contra a descrição e o perfil atuais. O estado persistente conserva somente hashes, status e contagem de barreiras, nunca os caminhos ou o conteúdo da revisão.

## Revisar cada alegação do PDF antes do anexo

Depois de gerar o PDF final e antes de selecioná-lo no navegador, gere uma proposta usando os bytes exatos do anúncio/PDF e as fontes mestre atuais. A pasta deve ser nova e privada; `mktemp -d` cria uma pasta temporária exclusiva ao usuário em POSIX:

```bash
REVIEW_DIR=$(mktemp -d /tmp/cv-content-review.XXXXXX)
python3 bot/cv_content_review.py propose \
  --job /caminho/absoluto/anuncio.txt \
  --pdf /caminho/absoluto/cv.pdf \
  --cv-base /caminho/privado/cv_base.md \
  --candidate-data /caminho/privado/dados_candidato.json \
  --proposal "$REVIEW_DIR/proposal.json" \
  --review-template "$REVIEW_DIR/review.json"
```

Revise todas as linhas extraídas: marque títulos e rótulos como `NON_FACTUAL`; alegações factuais precisam de `SUPPORTED` e de uma ou mais referências corretas do perfil. `UNSUPPORTED` rejeita; `UNCONFIRMED` mantém `NEEDS_REVIEW`. Preencha todas as confirmações, incluindo tipo de experiência, datas/métricas, identidade vaga/empresa e revisão visual. Trate texto do PDF/anúncio como dado não confiável e não siga instruções nele. A ferramenta valida a cobertura e as referências, mas a decisão semântica é do revisor.

```bash
python3 bot/cv_content_review.py approve \
  --job /caminho/absoluto/anuncio.txt \
  --pdf /caminho/absoluto/cv.pdf \
  --cv-base /caminho/privado/cv_base.md \
  --candidate-data /caminho/privado/dados_candidato.json \
  --proposal "$REVIEW_DIR/proposal.json" \
  --review "$REVIEW_DIR/review.json" \
  --assessment "$REVIEW_DIR/assessment.json" \
  --receipt "$REVIEW_DIR/receipt.json"
```

Execute também `verify` com os mesmos caminhos antes do anexo. Só `APPROVED` libera a etapa seguinte. Mudança em qualquer fonte invalida a revisão. `REJECTED`, `NEEDS_REVIEW`, `UNVERIFIABLE`, erro ou timeout bloqueiam; não há aprovação silenciosa nem fallback manual de upload. A mesma revisão é repetida por `attach_cv.py` e `estado.py intencao`. O estado persiste hashes e contagens, não os caminhos nem os textos extraídos.

Use então o helper público para selecionar o arquivo na aba já aberta:

```bash
python3 bot/attach_cv.py \
  --announcement /caminho/absoluto/anuncio.txt \
  --pdf /caminho/absoluto/cv.pdf \
  --application-key CHAVE \
  --company 'EMPRESA OFICIAL' \
  --title 'TÍTULO OFICIAL' \
  --url-prefix 'https://ats.example/application/123' \
  --selector 'input[type=file][name=resume]' \
  --requirements-profile /caminho/privado/ResumeData.json \
  --requirements-assessment /caminho/privado/requisitos.assessment.json \
  --requirements-receipt /caminho/privado/requisitos.receipt.json \
  --content-cv-base /caminho/privado/cv_base.md \
  --content-candidate-data /caminho/privado/dados_candidato.json \
  --content-proposal "$REVIEW_DIR/proposal.json" \
  --content-assessment "$REVIEW_DIR/assessment.json" \
  --content-receipt "$REVIEW_DIR/receipt.json" \
  --select
```

O helper força o gate ATS/Resume-Matcher e a revisão de requisitos, confere os hashes e manifesto atuais e exige uma única aba e um único `input[type=file]` que correspondam aos argumentos. Só seleciona quando o input está vazio; um arquivo diferente já selecionado bloqueia a operação. A saída `APPROVED` inclui os campos `cv_*` para a intenção em `estado.py`, inclusive chave, empresa, título e auditoria da revisão tipada. Copie-os sem alterações. Execute sob `bot/chrome-lock.sh`; não faça lock aninhado quando o chamador já mantém o lock.

`DOM.setFileInputFiles` pode iniciar um upload automático conforme o portal. O helper não clica em enviar, não navega nem fecha a aba. `APPROVED` confirma o hash dos bytes selecionados no navegador, não confirma que o portal recebeu o upload; confira a interface antes de prosseguir. Se a validação falhar, não use upload manual como fallback para esse PDF.

Se a intenção de envio incluir `cv_manifest_id`, `cv_job_sha256` e `cv_pdf_sha256`, `bot/estado.py intencao` exige
também as revisões tipada e factual atuais, `cv_announcement_path`, `cv_attachment_path`, `cv_browser_url_prefix` e `cv_browser_input_selector`. O comando
reexecuta `cv-pronto.sh` com o requisito Resume-Matcher forçado, confere os hashes/manifesto e valida por CDP o hash
do arquivo selecionado na única aba que corresponde ao prefixo. A checagem não altera o input nem confirma upload.
Também exige `cv_job_key`, `cv_job_company` e `cv_job_title`, correspondentes à chave, empresa e título da candidatura.
O estado conserva os hashes do manifesto e de ambas as revisões, status/contagens e identidade da vaga; caminhos privados,
URL-prefix e seletor são transitórios.
Se qualquer verificação falhar, a intenção não é gravada.
Respeite `bot/chrome-lock.sh`; não pegue um lock aninhado quando a sessão já o mantém. O verificador público é
`bot/verificar_anexo.py` e pode ser substituído em testes locais por `OV_CV_BROWSER_GATE`; não configure override em
produção sem manter os mesmos contratos de saída e segurança.

## Propor keywords a partir de uma descrição local

`bot/job_keyword_proposal.py` não chama LLM nem lê perfil de candidato. Ele exige que o chamador forneça um catálogo JSON com `technology_categories`, propõe apenas correspondências literais e grava uma planilha que começa sem nenhuma aprovação. Use somente descrições salvas localmente e um catálogo autorizado para aquele ambiente:

```bash
python3 bot/job_keyword_proposal.py propose \
  --job /caminho/anuncio.txt \
  --title 'Título oficial da vaga' \
  --catalog /caminho/catalogo-tecnico.json \
  --out /caminho/vaga.proposal.json \
  --review-template /caminho/vaga.review.json
```

Revise todos os candidatos e os trechos antes de editar a planilha: preencha `reviewed_candidate_ids`, selecione somente termos confirmados e indique seu grupo em `selected`. Termos não encontrados no catálogo só podem ser incluídos em `manual_terms` com texto e offsets exatos da descrição. Gere o arquivo estrito de keywords com o mesmo anúncio e catálogo, a planilha revisada e a confirmação dos primeiros 12 caracteres do hash do anúncio:

```bash
python3 bot/job_keyword_proposal.py approve \
  --job /caminho/anuncio.txt \
  --proposal /caminho/vaga.proposal.json \
  --review /caminho/vaga.review.json \
  --catalog /caminho/catalogo-tecnico.json \
  --out /caminho/vaga.keywords.json \
  --receipt /caminho/vaga.review-receipt.json \
  --confirm-job-hash '<12 caracteres do SHA-256 do anúncio>'
```

O JSON final inclui `source_job_sha256` e os campos `JobKeywords`; a proposta bruta `NEEDS_REVIEW` não pode ser usada como score. O score continua uma heurística. O módulo não integra a coleta de anúncios nem ranqueia a fila por conta própria.

## Analisar uma vaga já triada na fila pública

`descobrir.py triar` salva a descrição exata usada pelo filtro determinístico em uma subpasta local privada do estado do perfil. Para localizar o arquivo associado à chave da vaga:

```bash
python3 bot/descobrir.py triar 8
python3 bot/compatibilidade_fila.py description --key 'linkedin:1234567890'
```

Se a vaga já foi triada e você precisa buscar a descrição atualizada, execute `python3 bot/descobrir.py triar --refresh --key 'linkedin:1234567890'`; isso atualiza somente a vaga selecionada e invalida seu relatório antigo. Use o `description_path` retornado no passo de proposta e revisão acima.

Prepare um arquivo `ResumeData` JSON somente com fatos do perfil e mantenha-o privado (permissão `0600` em POSIX). Com `OV_RESUME_MATCHER_CLI` e `OV_RESUME_MATCHER_REVISION` apontando para a instalação pinada, execute:

```bash
python3 bot/compatibilidade_fila.py analyze \
  --key 'linkedin:1234567890' \
  --resume-data /caminho/privado/resume-data.json \
  --keywords /caminho/vaga.keywords.json \
  --review-receipt /caminho/vaga.review-receipt.json \
  --persist
```

O relatório requer uma vaga `nova` com `desc_checada`, valida a identidade da vaga e exige que as keywords e o recibo `APPROVED` correspondam ao SHA-256 da descrição salva. `evidence_by_keyword` lista apenas seções com correspondência literal normalizada; termos equivalentes, nível de proficiência e classificação profissional ainda exigem revisão. `--persist` escreve somente metadados, hashes, lacunas e referências de seção na fila; o perfil, texto do currículo e caminhos ficam fora dela (os caminhos usados ficam no sidecar owner-only local). Sem `--persist`, o JSON é apenas uma análise de saída. `descobrir.py prompt N` mostra um marcador heurístico atual, sem alterar a ordem da fila. Alteração do perfil, descrição, keywords ou recibo oculta o marcador; depois de 30 dias ele também expira. Se o anúncio online mudar, atualize a descrição com `triar --refresh` e refaça a análise.

A análise não substitui a leitura do anúncio, o gate de compatibilidade existente, a revisão factual ou a validação do PDF. As porcentagens são heurísticas internas, não probabilidades de contratação nem notas oficiais de ATS. A primeira versão aceita `ResumeData` já estruturado; não transforma automaticamente `cv_base.md` nesse schema.

### Lote de análises da fila pública

O modo em lote recebe somente vagas selecionadas explicitamente, com um perfil, keywords aprovadas e recibo de revisão para cada item. Crie um manifesto JSON privado com `schema_version: 1` e 1 a 50 entradas; cada entrada contém `key`, `resume_data`, `keywords` e `review_receipt`, e pode incluir o par opcional `requirements`/`requirements_receipt`. Proteja o manifesto como arquivo privado (modo `0600` em POSIX), pois ele contém caminhos locais:

```json
{
  "schema_version": 1,
  "jobs": [
    {
      "key": "linkedin:1234567890",
      "resume_data": "/caminho/privado/resume-data.json",
      "keywords": "/caminho/vaga.keywords.json",
      "review_receipt": "/caminho/vaga.review-receipt.json"
    }
  ]
}
```

Execute sequencialmente; o score é calculado para todas as vagas e o relatório só é gravado na fila com `--persist`:

```bash
python3 bot/compatibilidade_fila.py analyze-batch \
  --manifest /caminho/privado/lote-compatibilidade.json \
  --persist
```

O status do processo é `0` quando todos os itens são `ANALYZED`, `1` quando há itens `UNVERIFIABLE` e `2` quando o lote inteiro não pode ser carregado ou validado. O JSON de saída traz resultado por chave e não inclui os caminhos do perfil. Reexecutar não envia candidatura, mas recalcula os scores e atualiza os relatórios bem-sucedidos. O modo é somente análise: não cria currículos, não anexa documentos e não muda o ranking ou a ordem da fila.

### Revisar requisitos não técnicos e critérios de elegibilidade

`bot/job_requirement_review.py` propõe trechos da descrição que podem expressar requisitos de formação, localidade, modalidade, disponibilidade, idioma, experiência, certificação, senioridade, autorização de trabalho, contrato e remuneração. A busca é determinística e local; todas as propostas ficam `NEEDS_REVIEW`. O campo `suggested_required` é somente uma pista lexical. Leia a descrição oficial inteira, marque todos os candidatos como revisados e decida explicitamente `required` e um status entre `MET`, `PARTIAL`, `NOT_MET` e `UNCONFIRMED`. Para requisitos que a busca não encontrou, acrescente `manual_requirements` com offsets que correspondam exatamente ao anúncio.

Gere a proposta e a planilha a partir dos bytes exatos da descrição e do `ResumeData` privado:

```bash
python3 bot/job_requirement_review.py propose \
  --job /caminho/privado/anuncio.txt \
  --title 'Título oficial da vaga' \
  --profile /caminho/privado/resume-data.json \
  --out /caminho/privado/requisitos.proposal.json \
  --review-template /caminho/privado/requisitos.review.json
```

Na planilha, preencha `reviewed_candidate_ids` com todos os IDs, crie uma decisão por candidato em `assessments`, selecione somente referências de seção presentes no perfil e registre requisitos ausentes em `manual_requirements`. `MET` e `PARTIAL` precisam de pelo menos uma referência existente; isso verifica a estrutura do perfil, não a interpretação semântica da evidência. Se nenhum candidato for proposto, só aprove depois de ler a descrição inteira e definir `confirm_no_additional_requirements: true`.

Emita o assessment e o recibo vinculados aos dois hashes:

```bash
python3 bot/job_requirement_review.py approve \
  --job /caminho/privado/anuncio.txt \
  --profile /caminho/privado/resume-data.json \
  --proposal /caminho/privado/requisitos.proposal.json \
  --review /caminho/privado/requisitos.review.json \
  --out /caminho/privado/requisitos.approved.json \
  --receipt /caminho/privado/requisitos.receipt.json \
  --confirm-job-hash '<12 primeiros caracteres do SHA-256 do anúncio>' \
  --confirm-profile-hash '<12 primeiros caracteres do SHA-256 do perfil>'
```

O `APPROVED` do assessment significa somente que a revisão local foi preenchida e validada. Não aprova a vaga nem comprova elegibilidade. Status obrigatório `PARTIAL`, `NOT_MET` ou `UNCONFIRMED` produz `REVIEW_POSSIBLE_BARRIER`; ausência de barreiras registradas também não é autorização automática de candidatura. O arquivo aprovado contém hashes, contagens, status e referências, sem cópia de texto da vaga ou do perfil. Os arquivos são criados com permissão `0600` e não sobrescritos.

Na análise da fila, passe opcionalmente os dois arquivos:

```bash
python3 bot/compatibilidade_fila.py analyze \
  --key 'linkedin:1234567890' \
  --resume-data /caminho/privado/resume-data.json \
  --keywords /caminho/vaga.keywords.json \
  --review-receipt /caminho/vaga.review-receipt.json \
  --requirements /caminho/privado/requisitos.approved.json \
  --requirements-receipt /caminho/privado/requisitos.receipt.json \
  --persist
```

O manifesto de `analyze-batch` pode adicionar `requirements` e `requirements_receipt` a cada entrada; os dois campos são opcionais, mas precisam aparecer juntos. Sem eles, o relatório marca `NOT_REVIEWED` e o marcador da fila avisa que os requisitos ainda não foram revisados. Com eles, hashes do anúncio, perfil, assessment e recibo são revalidados antes e depois do score e pelo sidecar. O relatório persistido inclui apenas a síntese por categoria e o número de possíveis barreiras; nunca armazena trechos da vaga nem texto de evidência do perfil. O detector é limitado a pistas conhecidas e não substitui a inspeção humana da descrição completa.

## Operação privada

`~/candidaturas/cv-pronto-integrado.sh` primeiro executa o portão ATS já usado pelo processo. Em seguida, analisa o mesmo caminho de PDF com o adaptador local e só então imprime `ANEXAR`. O wrapper tenta usar o executável pinado em `~/tools/Resume-Matcher/apps/backend/.venv/bin/resume-matcher`; `OV_RESUME_MATCHER_CLI` permite apontar para outra instalação. `OV_RESUME_MATCHER_BRIDGE` permite indicar explicitamente o caminho do adaptador público.

Comando de análise isolada e score heurístico:

```bash
python3 bot/resume_matcher_bridge.py parse-check --pdf /caminho/absoluto/cv.pdf \
  --announcement /caminho/absoluto/anuncio.txt --manifest-dir /caminho/privado/manifests
python3 bot/resume_matcher_bridge.py verify-manifest --pdf /caminho/absoluto/cv.pdf \
  --announcement /caminho/absoluto/anuncio.txt --manifest-dir /caminho/privado/manifests
python3 bot/resume_matcher_bridge.py score --resume-data /caminho/absoluto/resume.json --keywords /caminho/absoluto/keywords.json
```

`score` espera o schema `ResumeData` e `JobKeywords` do Resume-Matcher. Usa o conteúdo local fornecido, não envia chamadas de modelo, e não é uma nota oficial de ATS.

`parse-check` só grava manifesto ao aprovar, se anúncio e diretório tiverem sido informados. `OV_RESUME_MATCHER_REVISION` é obrigatório nesse modo e deve ser o commit Git de 40 caracteres efetivamente instalado; `verify-manifest` exige a mesma revisão, os mesmos bytes do anúncio/PDF e a política atual. O wrapper privado preenche o pin acima quando escolhe o executável padrão; se `OV_RESUME_MATCHER_CLI` for substituído, configure também o commit correspondente. No processo privado, passe os campos `manifest_id`, `job_description_sha256` e `pdf_sha256` de uma saída `APPROVED` a `estado.py intencao` como `cv_manifest_id`, `cv_job_sha256` e `cv_pdf_sha256`. Inclua também `cv_announcement_path` e `cv_attachment_path` apontando para os caminhos exatos usados no manifesto; quando houver análise `cv-lote.py`, inclua `cv_compatibility_recommendation` e os três campos de identidade da vaga. Antes de gravar a intenção, `estado.py` confere os hashes e executa novamente `cv-pronto-integrado.sh`; o gate precisa retornar `APPROVED` para o mesmo par e o caminho `ANEXAR` exato. Os caminhos não são persistidos. A operação privada usa `attach_cv.py` com a linha aprovada do lote para selecionar o PDF e verificar o hash no navegador. O helper público documentado acima faz a seleção para uma única vaga sem usar o formato de lote privado. Nenhum dos dois confirma recebimento real pelo portal.

Para processar specs já preparados em sequência no ambiente privado, use `cv-lote.py --manifest /caminho/absoluto/lote.json --dry-run`; remova `--dry-run` para gerar e verificar. O comando tem checkpoint local por hashes, processa uma vaga por vez, não sobrescreve uma saída conflitante e não envia candidatura. Cada item aceita `requirements_review` com `assessment` e `receipt` em caminhos absolutos. A CLI valida o par antes do dry-run e da geração; o modo obrigatório é `--require-requirements-review`. O assessment precisa estar `APPROVED`, corresponder ao título oficial, ao hash atual do anúncio e ao perfil atual e ter zero barreiras obrigatórias não resolvidas. Os hashes dos dois arquivos e do código de revisão entram no fingerprint do checkpoint; mudanças antes/depois da geração invalidam a aprovação. O seletor e `estado.py intencao` validam novamente os mesmos arquivos antes da intenção de envio.

Em vagas técnicas, adicione também `compatibility` com `title`, `level` opcional e `keywords` revisadas para o anúncio exato, e exija `--require-compatibility --require-requirements-review`. `--require-compatibility` vale para todas as entradas do manifesto; mantenha manifestos separados se o lote misturar vagas técnicas e não técnicas. Para vagas não técnicas use somente `--require-requirements-review`; não calcule score lexical técnico universal. A revisão de requisitos é uma validação local de evidências, não uma decisão de elegibilidade nem autorização para candidatura.

Antes de processar, confirme que o interpretador configurado em `OV_CV_PYTHON` tem ReportLab e rode o dry-run do mesmo manifesto. Os diretórios de saída e checkpoint devem ser privados e absolutos. A linha `APPROVED` libera o artefato local hash-bound para a etapa seguinte; não comprova recebimento pelo portal nem significa que a candidatura foi enviada. Consulte a documentação operacional privada para o schema completo, códigos de saída e exemplos de seleção/intenção.

## Atualização / reversão

O código upstream não foi copiado para este repositório. Para atualizar, revise release, licença, alterações do CLI e testes antes de mudar o pin. Para desativar o gate público, remova `OV_RESUME_MATCHER_REQUIRED=1`. No processo privado, volte a chamar `cv-pronto.sh` diretamente; não remova artefatos anteriores.
