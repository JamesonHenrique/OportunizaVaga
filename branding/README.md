# branding/ — masters da identidade visual

Origem: `assets/KIT-IDENTIDADE-VISUAL-OPORTUNIZAVAGA.zip` (kit v1.0.0, pasta `OportunizaVaga-identidade-visual/branding/`), copiado sem redesenho. Documentos do kit: `docs/marca/`.

| Arquivo | Uso |
|---|---|
| `tokens.json` | Fonte canônica dos tokens (cor, tipo, espaço, raio, movimento). |
| `tokens.css` | Os mesmos tokens como CSS custom properties, com aliases do monitor. `monitor/app/globals.css` espelha esses valores. |
| `manifest-assets.json` | Inventário de todos os arquivos abaixo. |
| `logos/logo-horizontal-claro.svg` / `-escuro.svg` | Logo principal em fundo claro / escuro. PNGs são exports de conveniência (usados no README via `<picture>`). |
| `logos/logo-empilhado.svg` | Layouts quadrados, capas, cards sociais. |
| `logos/logo-monocromatico.svg` | Impressão e contextos de uma cor. |
| `logos/simbolo.svg` | Marca isolada para tamanhos pequenos (fundo transparente; em fundo claro o chartreuse perde contraste — prefira `icons/favicon.svg`). |
| `icons/favicon.svg` | Favicon e marca do cabeçalho do monitor (copiado para `monitor/public/icon.svg`). |
| `icons/app-icon.svg` + PNGs 192/512 | Ícone de app; derive rasters do SVG. |
| `patterns/trilhas.svg` | Fundo editorial sutil; nunca atrás de tabelas densas. |
| `social/og-banner.svg` / `.png` | Preview social (Open Graph / GitHub). |
| `reference/prancha-conceitual.png` | Moodboard; não é master de logo. |

## Divergências do kit original

- `--tx3` / `light.textTertiary`: `#68768A` → `#5D6B7F`. O valor do kit dava 4,30:1 sobre `--bg` e 3,96:1 sobre `--surface-3` (abaixo de WCAG AA 4,5:1).

## Observação sobre os SVGs com texto

Os logos horizontais/empilhado usam `<text>` com `font-family="Manrope, Arial"`. Fora de uma página que carregue a Manrope (ex.: `<img>`, GitHub), o texto cai para Arial. Para README e materiais externos, use os PNGs exportados.
