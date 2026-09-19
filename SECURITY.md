# Security Policy

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Email **jameson.henrique.dev@gmail.com** with:

1. A description of the vulnerability and its impact.
2. Steps to reproduce (proof of concept, logs, affected version/commit).
3. Your contact for follow-up.

> NOTE: contato de segurança do mantenedor (`jameson.henrique.dev@gmail.com`).

What to expect:

- Acknowledgment within 5 business days.
- Status updates at least every 14 days until resolution.
- Coordinated disclosure: please give us reasonable time to fix before
  disclosing publicly. Credit is given on request.

## Scope

In scope:

- Remote code execution via `bot/`, `browser/`, `scripts/` or `monitor/`.
- Secret or personal-data exfiltration paths (e.g. monitor snapshot leaking
  sensitive fields, allowlist bypass in `config/sites_permitidos.json`).
- Authentication/session handling flaws (browser profile, Chrome CDP exposure).

Out of scope:

- Automated job-application activity violating third-party Terms of Use
  (LinkedIn, Gupy, Indeed and other portals — see README legal notice).
- Rate-limit / quota exhaustion of free AI providers.
- Reports requiring real personal data to reproduce (never send us real CVs,
  credentials or tokens — use redacted placeholders).
- Theoretical issues without a reproducible proof of concept.

## Secret Hygiene (binding)

- **Never commit** `bot/dados_candidato.json`, `bot/aplicadas.json`, `bot/state/`,
  `bot/prompt_loop.runtime.md`, `bot/reconhecimento-*.json`, `*.log`, `logs/`,
  `cron.env` (`**/cron.env`, `**/cron*.env`), `**/auth.json`, PDFs (`*.pdf`),
  browser profiles or `*.bak-*` files. They are blocked by `.gitignore` — verify
  with `git status` before every push.
- Run `./scripts/sanitize.sh` before each commit/push. It is blocking
  (exit 1 on match). Recommended as a pre-commit hook:
  `ln -s ../../scripts/sanitize.sh .git/hooks/pre-commit`.
- Use only placeholder values in tracked files (`SEU_NOME`,
  `seu-email@example.com`, `SUA_EMPRESA`, `https://sua-url.vercel.app`).
- Full rules: [`docs/SEGURANCA.md`](docs/SEGURANCA.md).

## If a Secret Leaks

A seen secret is **compromised**:

1. **Rotate immediately** at the provider (issue a new key, revoke the old one).
2. Remove it from the code and commit the removal.
3. Removing it from git history does not un-burn it — rotation (step 1) is
   what actually protects you.
