# AGENTS.md — OportunizaVaga

Regras para agentes (OpenCode, Claude Code, Codex) neste repositório. O `monitor/AGENTS.md` é gerado pelo `next dev` e trata só da versão do Next.js; não coloque regras de projeto nele.

## Identidade visual

- A marca é “OportunizaVaga”; assinatura: “Sua busca, em movimento.”
- Fonte canônica: `branding/tokens.json`, `branding/tokens.css`, `branding/manifest-assets.json`, `branding/logos/`, `branding/icons/` e `docs/marca/GUIA-DE-MARCA.md`.
- `monitor/app/globals.css` espelha os valores de `branding/tokens.css` nos blocos de tokens; componentes leem só variáveis CSS. Mudou um token? Atualize os dois.
- Chartreuse (`--brand-lime`) é acento de marca, nunca sucesso semântico nem texto pequeno em fundo claro. `--brand-green` é alias de sucesso semântico.
- Status sempre com texto/ícone além da cor. Contraste WCAG AA nos dois temas.
- Skill reutilizável: `.opencode/skills/identity-system/`. Agentes: `.opencode/agents/` (`brand-auditor`, `accessibility-reviewer`, `qa-reviewer` são somente leitura; `ui-implementer` edita só apresentação).

## Limites

- Antes de mexer, inspecione `git status`, a estrutura do repositório, os scripts disponíveis e a arquitetura do monitor. Preserve alterações locais não relacionadas.
- `monitor/` deste repositório (demo OSS) e o monitor privado são projetos distintos. Não os mescle automaticamente.
- Redesign é de apresentação. Não altere lógica do bot, adaptadores de portais, fluxo de candidaturas, APIs, polling, persistência, secrets, autenticação, ou regras de privacidade/consentimento.
- Faça mudanças incrementais, valide build/testes e inspecione o diff.
- Não afirme que todos os portais, candidaturas ou APIs funcionam só porque o dashboard tem uma aparência mais polida.
