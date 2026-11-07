# c1) PER-JOB CV — detail (read by the model ONLY when it is about to attach a PDF)
# Out of prompt_loop.en.md: ~3.5 KB less on every call.

c1) PER-JOB CV (effort rule): only generate the PDF when the channel REALLY attaches a file of
   YOURS: e-mail (Gmail), LinkedIn upload, Indeed. ON GUPY DON'T GENERATE a per-job PDF — Gupy sends
   the PROFILE CV (if the profile is bad/outdated, note it in manutencao_gupy for outside this round:
   ATS summary, experiences with MM/YYYY-present period without claiming years, only real languages,
   https links).

   IMMUTABLE SOURCES: all content comes from bot/cv_base.md (master CV — if it doesn't exist, create
   it ONCE from examples/cv_base.example.md filling only from dados_candidato.json) +
   dados_candidato.json. NEVER write HTML/tex/reportlab by hand, NEVER invent company, period, year,
   language, skill or number. There is always the same generator script — don't create another.

   FLOW (5 steps):
   1) Read the job description and extract ONLY what is true in your profile. Copy the EXACT wording
      from the posting for the top-3 truthful keywords (same spelling: "Spring Boot" must not become
      "springboot"). On the 1st mention of an acronym in the summary, write it out in parentheses
      (e.g. "continuous integration/delivery (CI/CD)", "robotic process automation (RPA)") — ATS and
      recruiters understand better.
   2) Build the spec at /tmp/cv_spec.json:
        { "empresa": "...", "vaga": "...",
          "titulo_alvo": "...",                // job title as written in the posting; developer/analyst roles only, never mid/senior
          "resumo_custom": "...",              // <=800 chars, 3-4 sentences, truthful, with job keywords;
                                               // a number (years, %) or technology not in the profile = ERROR (exit 2)
          "categorias_ordem": ["...", "..."],   // subsections of "Habilidades técnicas" for the top
          "so_categorias": ["...", "..."],      // 3-7 subsections to SHOW; the rest stay hidden
          "palavras_chave_vaga": ["..."] }      // only real job skills that exist in my profile
      Valid names are the "###" items under "## Habilidades técnicas" in YOUR bot/cv_base.md (if the
      spec is wrong, the script fails and lists the valid ones). so_categorias is MANDATORY (3-7
      subsections relevant to the job): without it the script FAILS (exit 2) — it is what keeps the
      body at 10pt and the CV away from a wall of irrelevant skills. Map by job area (e.g. dev job →
      "Backend"/"Frontend"/"Banco de dados"; automation job → the automation/integration category of
      YOUR cv_base).
      SUMMARY: sentence 1 = the posting's title + 2-3 REAL stacks it asks for; sentence 2 = experience with a
      number; sentence 3 = proof tied to the job. Never a raw tech list nor internal notes ("similar",
      "sem afirmar domínio"): the generator refuses (exit 2) and the self-check fails the PDF.
   3) Generate the PDF (the script only returns exit 0 if the file has 1 page and the text passes the
      name + sections self-check; any ERROR = fix the spec and run again):
        python3 "$BOT_ROOT/bot/gerar_cv.py" /tmp/cv_spec.json \
          "$BOT_ROOT/bot/CV_YOUR_NAME_<Company>.pdf"
      filename WITHOUT the word "ATS" and with the candidate's real name (from dados_candidato.json
      -> nome) instead of YOUR_NAME. The script prints "kw no CV: ..." and "kw DESCARTADAS (fora do
      perfil): ..." — if something you asked for was dropped, it does NOT exist in the profile: DON'T
      work around it nor regenerate the PDF with invented content; proceed with what passed.
   4) Save the posting text to /tmp/anuncio.txt and measure coverage BEFORE attaching:
        python3 "$BOT_ROOT/bot/check_ats.py" /tmp/anuncio.txt \
          "$BOT_ROOT/bot/CV_YOUR_NAME_<Company>.pdf"
      Target: coverage of PROFILE terms >= 75% (exit 0 = "OK"; exit 2 = unreadable profile,
      NOT a pass). If it failed, adjust the spec
      (resumo_custom with the MISSING terms in the posting's wording, palavras_chave_vaga,
      so_categorias) and regenerate — NEVER try to cover an "outside profile" term (the script itself
      lists those as a job misalignment).
   5) Attach the generated PDF (1 page) to the submission.
