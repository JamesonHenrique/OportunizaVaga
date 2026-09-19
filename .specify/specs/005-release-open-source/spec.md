# Spec 005 — Release open source (publicação segura do OportunizaVaga)

- **Tipo:** trilha de publicação (do deploy pessoal para repo público)
- **Status:** rascunho (2026-09-19; scan Regra Zero do deploy: limpo)
- **Relacionadas:** 001–004 (o que será publicado)

## 1. Visão geral

Transformar o sistema pessoal (que contém CV, e-mail, chat ID, segredos e
histórico real) num repositório público que qualquer pessoa instala sem expor
nada de ninguém. A regra de ouro: **o repo público nunca contém dado real** —
só schemas, exemplos e templates com placeholders. Todo artefato passa por
sanitização mecânica + revisão humana antes do push.

## 2. Usuários e personas

- **Mantenedor (dono do deploy):** extrai, sanitiza e publica.
- **Adotante:** clona, roda `install.sh`, preenche `.env`, usa.
- **Auditor:** confere que o repo não vaza nada (gitleaks + grep).

## 3. Escopo

### Dentro

- Inventário de divergências entre as cópias (`OportunizaVaga` ×
  `opensource/oportunizavaga`) e consolidação numa única origem.
- `sanitize.sh` cobrindo: `aplicadas.json`, `conectados.json`, `dados_candidato.json`,
  prompts, logs, `.env`, nomes de arquivos com empresa.
- `.env.example`, `config/*.example.json`, `config/*.template.md` para tudo.
- `LICENSE` (MIT, já existe — confirmar), `CITATION.cff` (já existe), docs
  de uso ético e custo (já existem — revisar).
- CI mínimo: gitleaks + `validate-config.sh` nos exemplos + `bash -n` nos scripts.
- Sincronização das cópias: uma origem, resto espelho (acabar com o drift).

### Fora

- Publicar o deploy pessoal como está (proibido).
- Suporte oficial Windows (só `install.ps1` best-effort, já existe).
- Loja/marketplace (pós-MVP).

## 4. Requisitos funcionais

- [FR-01] Nenhum arquivo com dado real entra no repo: lista bloqueada
  (`aplicadas.json`, `conectados.json`, `dados_candidato.json`, `.env`,
  `cron.env`, `logs/`, `*.log`) no `.gitignore` + teste de CI que falha se existirem.
- [FR-02] `sanitize.sh` converte deploy real → exemplos públicos (troca valores
  por placeholders, mantém estrutura) com relatório do que trocou.
- [FR-03] Todo exemplo valida no schema (`validate-config.sh` no CI).
- [FR-04] Gitleaks no CI bloqueia push com segredo (Telegram token, API keys,
  chat IDs, e-mails pessoais).
- [FR-05] Docs obrigatórios revisados: README (quickstart ≤10 min), USO-ETICO,
  CUSTO, SEGURANCA, ARQUITETURA.
- [FR-06] Uma única origem: consolidar `OportunizaVaga` × `opensource/oportunizavaga`
  (hoje divergem em `loop.sh`, `sanitize.sh`, docs e `sites/*.sh`); a outra vira espelho.
- [FR-07] `install.sh` instala do zero em Ubuntu/Debian limpo até `doctor.sh` verde.
- [FR-08] CHANGELOG mantido por release (o que mudou, como migrar `.env`/schemas).

## 5. Requisitos não funcionais

- [NFR-01] Scan completo (Regra Zero) <5 min.
- [NFR-02] Instalação limpa <15 min até o doctor verde.
- [NFR-03] Zero falso-positivo documentado sem explicação (ex.: PNG inline em `assets/logo.svg`).

## 6. Critérios de aceite

- [AC-01] Clone fresco + `install.sh` + `.env` preenchido → `doctor.sh` exit 0.
- [AC-02] `sanitize.sh` no deploy real → diff dos exemplos contém zero valores reais (grep de e-mail/chat ID/CPF retorna vazio).
- [AC-03] Push proposital com token fake → CI bloqueia (gitleaks vermelho).
- [AC-04] `diff -r` entre origem e espelho → vazio (sem drift).
- [AC-05] Revisor externo (ou checklist) confirma: README instala, docs éticos lidos, licença presente.

## 7. Riscos e perguntas abertas

| # | Risco / pergunta | Mitigação / resposta |
|---|------------------|----------------------|
| R1 | Histórico git antigo contém segredo | Reescrever histórico ou republicar squash (BFG); verificar antes do anúncio |
| R2 | Adotante usa p/ spam em massa | USO-ETICO + limites conservadores como default (10 convites/dia, 3 candidaturas/rodada) |
| R3 | Drift volta entre cópias | FR-06 + CI que compara origem×espelho (ou remove o espelho) |
| Q1 | Nome final do projeto? | OportunizaVaga (confirmar disponibilidade PyPI/npm se publicar pacotes) |
