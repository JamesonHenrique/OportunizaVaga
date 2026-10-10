# c1) CV POR VAGA — detalhe (lido pelo modelo SÓ quando vai anexar um PDF)
# Fora do prompt_loop.md: ~3,5 KB a menos em toda chamada.

c1) CV POR VAGA (regra de esforço): só gere o PDF quando o canal REALMENTE anexa um arquivo SEU:
   e-mail (Gmail), upload do LinkedIn, Indeed. NO GUPY NÃO GERE PDF por vaga — o Gupy envia o CV do
   PERFIL (se o perfil estiver ruim/desatualizado, anote em manutencao_gupy p/ fora desta rodada:
   resumo com ATS, experiências com período MM/AAAA-atual sem afirmar anos, idiomas só o real,
   links https).

   FONTES IMUTÁVEIS: todo conteúdo vem de bot/cv_base.md (currículo mestre — se não existir, crie
   UMA vez a partir de examples/cv_base.example.md preenchendo só com dados_candidato.json) +
   dados_candidato.json. NUNCA escreva HTML/tex/reportlab na mão, NUNCA invente empresa, período,
   ano, idioma, skill ou número. O gerador é sempre o mesmo script — não crie outro.

   FLUXO (5 passos):
   1) Leia a descrição da vaga/anúncio e extraia SÓ o que é verdadeiro no perfil dele. Copie a
      formulação EXATA do anúncio para as top-3 keywords verdadeiras (mesma grafia: "Spring Boot"
      não vira "springboot"). Na 1ª menção de siglas no resumo, escreva o extenso entre parênteses
      (ex.: "integração contínua/entrega contínua (CI/CD)", "automação robótica de processos (RPA)")
      — ATS e recrutadores entendem melhor.
   2) Monte o spec em /tmp/cv_spec.json:
        { "empresa": "...", "vaga": "...",
          "titulo_alvo": "...",                // cargo da vaga na grafia do anúncio; só cargo de dev/analista, nunca pleno/sênior
          "resumo_custom": "...",              // <=800 chars, 3-4 frases, verdadeiro, com keywords da vaga;
                                               // número (anos, %) ou tecnologia fora do perfil = ERRO (exit 2)
          "categorias_ordem": ["...", "..."],   // subseções de "Habilidades técnicas" p/ o topo
          "so_categorias": ["...", "..."],      // 3-7 subseções p/ MOSTRAR; as demais ficam ocultas
          "palavras_chave_vaga": ["..."] }      // só skills reais da vaga que existem no meu perfil
      Os nomes válidos são os "###" da seção "## Habilidades técnicas" do SEU bot/cv_base.md (se
      o spec estiver errado, o script falha e lista os válidos). so_categorias é OBRIGATÓRIO (3-7
      subseções relevantes à vaga): sem o campo o script FALHA (exit 2) — é ele que mantém o corpo
      em 10pt legível e o CV longe de um muro de skills irrelevantes. Mapeie pela área da vaga
      (ex.: vaga de dev → "Backend"/"Frontend"/"Banco de dados"; vaga de automação → a categoria
      de automação/integração do SEU cv_base).
      RESUMO: frase 1 = cargo da vaga + 2-3 stacks REAIS pedidas; frase 2 = experiência com número; frase 3 =
      prova ligada à vaga. Nunca lista crua de tecnologias nem nota interna ("similar", "sem afirmar domínio",
      "disponível para atuar,"): o gerador recusa (exit 2) e a autochecagem reprova o PDF.
   3) Gere o PDF (o script SÓ retorna exit 0 se o arquivo tiver 1 página e o texto passar na
      auto-checagem de nome + seções; qualquer ERRO = corrija o spec e rode de novo):
        python3 "$BOT_ROOT/bot/gerar_cv.py" /tmp/cv_spec.json \
          "$BOT_ROOT/bot/CV_SEU_NOME_<Empresa>.pdf"
      filename SEM a palavra "ATS" e com o nome real do candidato (de dados_candidato.json ->
      nome) no lugar de SEU_NOME. O script imprime "kw no CV: ..." e "kw DESCARTADAS (fora do
      perfil): ..." — se algo que você pediu caiu, é porque NÃO existe no perfil: NÃO tente
      contornar nem recrie o PDF com conteúdo inventado; siga com o que passou.
   4) Salve o texto do anúncio em /tmp/anuncio.txt e meça a cobertura ANTES de anexar:
        python3 "$BOT_ROOT/bot/check_ats.py" /tmp/anuncio.txt \
          "$BOT_ROOT/bot/CV_SEU_NOME_<Empresa>.pdf"
      Meta: cobertura dos termos DO PERFIL >= 75% (exit 0 = "OK"; exit 2 = perfil ilegível,
      NÃO conta como aprovado). Se reprovou, ajuste o spec
      (resumo_custom com os termos FALTANTES na formulação do anúncio, palavras_chave_vaga,
      so_categorias) e gere o PDF de novo — NUNCA tente cobrir termo "fora do perfil" (o próprio
      script lista esses termos como desalinhamento da vaga).
   5) Anexe o PDF gerado (1 página) ao envio.
