# Pull Request

## What changed and why

<!-- Describe what changed and why. Link related issues: Closes #NNN -->

## Checklist

- [ ] `./scripts/sanitize.sh` passes (blocking — no secrets or personal data)
- [ ] No personal data or secrets in the diff (no real CVs, credentials, tokens,
      CPF/CEP, real emails, absolute home paths, real deployment URLs —
      only placeholders like `SEU_NOME`, `seu-email@example.com`,
      `https://sua-url.vercel.app`)
- [ ] Tests / CI: `bash -n` clean, `node --check` clean (if `monitor/` touched),
      JSON valid, CI green (Linux + Windows jobs)
- [ ] Docs updated (`docs/` or `README.md` if behavior changed)
- [ ] If the bot was touched (`bot/`, `browser/`, `config/`, `scripts/`):
      dry-run tested with 1 manual round (`./bot/loop.sh` or `bot\loop.ps1`)
      and result noted below

## Test notes

<!-- Commands run + outcome, e.g. ./scripts/sanitize.sh → OK; 1 dry-run round → ok/blocked (reason) -->
