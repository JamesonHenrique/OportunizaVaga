# Constituição — OportunizaVaga

Versão: 1.0.0 (2026-09-19). Vale para o deploy pessoal (`~/candidaturas`,
`~/linkedin-rh`, `~/monitor`) e para o repositório open source OportunizaVaga.
Em conflito entre praticidade e estes princípios, os princípios vencem.

## 1. Rodadas sem estado

Cada rodada do agente é uma sessão NOVA que não lembra a anterior. Todo estado
que importa vive em JSON versionado (`aplicadas.json`, `conectados.json`):
ler antes de agir, escrever antes de sair. Nunca confie na memória da sessão.

## 2. Nunca inventar dados do candidato

Tudo vem de `dados_candidato.json`. Dado ausente NÃO é chutado: vira entrada
em `bloqueados` com o motivo exato. Tempo de carreira nunca é afirmado em anos;
descreve-se por cargo e período. Essa regra é inegociável.

## 3. Fuso único: America/Fortaleza

Logs, nomes de arquivo e carimbos usam hora local com fuso
(`date '+%FT%T%:z'`). UTC só no `ROUND_START` interno de detecção de quota.
Data errada já gerou candidatura datada no dia errado — não repetir.

## 4. Custo zero

Só modelos gratuitos, em cascata (Zen → OpenRouter `:free` → NVIDIA →
opcionais). Quota esgotada = esperar e revezar, nunca pagar. Rodada cabe em
~8 min; 1 site por rodada em rodízio circular; no máximo 3 envios por rodada.

## 5. Uma instância por responsabilidade

`flock` em tudo: loop (`candidaturas-loop.lock`), dia (`linkedin-rh-dia.lock`),
browser compartilhado (`agent-chrome-9222.lock`). Segunda instância sai calada
ou espera com timeout — nunca opera em paralelo sobre o mesmo Chrome/estado.

## 6. Ruído não é bloqueio

Descarte de listagem (nível/modelo/stack) incrementa contadores, nunca cria
entrada em `bloqueados`. `bloqueados` é só para vaga/empresa real com motivo
concreto. Reencontro sem novidade não gera chave nova.

## 7. Conta do usuário em primeiro lugar

Respeitar limites das plataformas (LinkedIn: máx. 10 convites/dia, delay
60–180 s humanizado; parar em `LIMITE_LINKEDIN`). Insistir contra limite
expresso arrisca a conta — encerrar o dia é o comportamento correto.

## 8. Regra Zero de segredos

Nenhum token, senha ou dado pessoal em código, log, spec ou repo público.
Credenciais vivem em arquivos `600` fora do repo (`cron.env`) ou variáveis de
ambiente. Antes de exportar/publicar, rodar `scripts/sanitize.sh` + gitleaks.
Segredo visto em texto claro = comprometido = rotacionar.

## 9. Observabilidade total, log legível

Toda rodada publica no monitor e deixa resumo em ≤10 linhas no log. Dump
completo vive em `logs/`; `loop.log`/`dia.log` carregam só o fim. Falha
silenciosa é bug: watchdog e guardião existem para provar vida, não presumir.

## 10. Deploy pessoal ≠ código público

O repo open source contém schemas, exemplos e templates — nunca
`dados_candidato.json` nem `aplicadas.json` reais. O deploy pessoal adapta
paths e segredos localmente. Sincronizar melhorias do pessoal para o público
passa por sanitização (spec 005).
