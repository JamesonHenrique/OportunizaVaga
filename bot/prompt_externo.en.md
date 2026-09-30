# c-Externo — detail (read ONLY when the application leaves the portal for an ATS/own site)
# Out of prompt_loop.en.md: ~2 KB less on every call.

c-Externo) NON-STANDARD ATS / SITE (rippling, greenhouse, lever, inhire.app, factorialhr, recrutei,
   the company's own site...):
   1. Redirected to another page/subdomain inside the ATS (e.g. company.inhire.app,
      ats.rippling.com/...)? That's NORMAL — keep going through the flow to the final submit button.
      Do not log a block for a redirect.
   2. Order of preference: form WITHOUT an account (greenhouse/lever/rippling often are) → "Continue
      with Google"/"Sign in with LinkedIn" ("email_contas" account, already logged into Chrome) → sign up
      with e-mail+password.
   3. Sign-up with a password: NEW strong password per site, always through the script:
      NEVER generate, type or read the password yourself (shell commands and fill_form go to the log). With
      the form open and the password fields visible, run:
      node $BOT_ROOT/bot/nova-senha.mjs <domain> <email_contas>
      It generates the password, saves it to ~/.config/oportunizavaga/credenciais.tsv (chmod 600, OUTSIDE
      the repo; path overridable via OV_CREDENTIALS_FILE) and fills password + confirmation straight into
      the tab. Fill the other fields with fill_form, without touching the password fields. NEVER write a
      password into aplicadas.json, a log, the final reply or the CV — aplicadas.json can be published to
      the monitor. In contas_criadas note only the site, e-mail, date and "password in credenciais.tsv".
      E-mail confirmation: open the Gmail of the "email_contas" account
      (mail.google.com/mail/?authuser=<email_contas>), click the verification link and go back to the form.
   4. Aggregator with no application link (e.g. a post with no external button): look for the SAME job
      (company + title) on LinkedIn, Gupy, Inhire or the company's careers site
      ("<company> careers" / "<company> we're hiring") and apply there. Only log a block if you can't
      find it on any channel.
   5. Fields: use dados_candidato.json + respostas_padrao_gupy; CV upload = generate the per-job PDF
      (rule c1). Missing datum (CPF, RG...) → quase_la, as in rule 4. Unsolvable captcha/long test →
      bloqueados.
