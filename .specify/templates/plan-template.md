# Template de Plano de Implementação

> Copie para `.specify/specs/<NNN>-<nome>/plan.md`. Descreve COMO implementar
> o spec correspondente, sem pular a constituição.

## Constituição aplicável

(Quais princípios de `memory/constitution.md` este plano precisa honrar.)

## Arquitetura / abordagem

(Componentes tocados, fluxo, decisões. 3–8 linhas + diagrama ASCII se ajudar.)

## Passo a passo

1. ...
2. ...

## Testes e validação

(Comando exato + resultado esperado. Ex.: `bash -n bot/loop.sh`,
`./bot/dry-run.sh`, `doctor.sh` exit 0.)

## Rollback

(Como desfazer: backups `.bak-<data>`, `git stash`, cron anterior em
`crontab.bak-*`.)
