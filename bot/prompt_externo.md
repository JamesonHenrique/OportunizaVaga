# c-Externo — detalhe (lido SÓ quando a candidatura sai para um ATS/site próprio)
# Fora do prompt_loop.md: ~2 KB a menos em toda chamada.

c-Externo) ATS / SITE SEM PADRÃO (rippling, greenhouse, lever, inhire.app, factorialhr, recrutei,
   site próprio da empresa...):
   1. Redirecionou para outra página/subdomínio dentro do ATS (ex.: empresa.inhire.app,
      ats.rippling.com/...)? É NORMAL — continue o fluxo até o botão final de envio. Não registre
      bloqueio por redirecionamento.
   2. Ordem de preferência: formulário SEM conta (greenhouse/lever/rippling costumam ser) → "Continuar
      com Google"/"Entrar com LinkedIn" (conta "email_contas", já logada no Chrome) → cadastro com
      e-mail+senha.
   3. Cadastro com senha: senha forte NOVA por site, sempre via script:
      NUNCA gere, digite ou leia a senha você mesmo (comando de shell e fill_form vão para o log). Com o form
      aberto e os campos de senha visíveis, rode:
      node $BOT_ROOT/bot/nova-senha.mjs <dominio> <email_contas>
      Ele gera a senha, grava em ~/.config/oportunizavaga/credenciais.tsv (chmod 600, FORA do repositório;
      caminho configurável em OV_CREDENTIALS_FILE) e preenche senha + confirmação direto na aba. Preencha os
      demais campos com fill_form, sem tocar nos campos de senha. NUNCA escreva senha em aplicadas.json, log,
      resposta final ou CV — aplicadas.json pode ser publicado no monitor. Em contas_criadas anote só site,
      e-mail, data e "senha em credenciais.tsv".
      Confirmação por e-mail: abra o Gmail da conta "email_contas" (mail.google.com/mail/?authuser=<email_contas>),
      clique no link de verificação e volte ao form.
   4. Agregador sem link de candidatura (ex.: vaga só com texto, sem botão externo): procure a MESMA
      vaga (empresa + título) no LinkedIn, Gupy, Inhire ou no site de carreiras da empresa
      ("<empresa> carreiras" / "<empresa> trabalhe conosco") e aplique por lá. Só registre bloqueio se
      não achar em nenhum canal.
   5. Campos: use dados_candidato.json + respostas_padrao_gupy; upload de CV = gere o PDF por vaga
      (regra c1). Dado ausente (CPF, RG...) → quase_la, como na regra 4. Captcha insolúvel/teste
      longo → bloqueados.
