---
name: identity-system
description: Regras oficiais da identidade visual do OportunizaVaga para implementação, expansão de telas e auditoria.
license: MIT
compatibility: OpenCode
---

# OportunizaVaga — identidade visual

Antes de implementar uma nova tela ou alterar componentes:

1. Leia `branding/tokens.json`, `branding/tokens.css`, `branding/manifest-assets.json`, `docs/marca/GUIA-DE-MARCA.md` e `docs/marca/SISTEMA-DE-DESIGN.md`.
2. Use Manrope para UI e IBM Plex Mono para dados técnicos, logs e timestamps; mantenha fallback local de sistema.
3. Use Azul Noturno `#101826`, Cobalto `#3E63F5`, Chartreuse `#D7F36A`, Off White `#F7F7F2`, Cinza Névoa `#E6EAF0` e Coral `#FF725E` conforme os usos definidos. Não misture chartreuse de marca com sucesso semântico.
4. Consuma CSS variables; não replique códigos hexadecimais em cada componente.
5. Use o logo vetorial correto para fundos claros/escuros. O símbolo isolado é para tamanhos pequenos. Nunca crie SVG com PNG em Base64.
6. Toda informação de estado deve combinar rótulo textual e, quando útil, ícone; cor é redundante.
7. Preserve paridade entre light/dark, foco, teclado, reduced motion e reflow mobile.
8. Não mude o motor de candidaturas, fontes, dados, APIs, lógica de estado, polling, persistência, autenticação, bot, scripts ou proteções por conta de um redesign.
9. Diferencie dados reais, demos, cache, stale, erros, bloqueios e estados não confirmados. Não fabrique métricas.
10. Valide build/testes existentes e revise o diff; não declare sucesso de testes que não foram executados.
