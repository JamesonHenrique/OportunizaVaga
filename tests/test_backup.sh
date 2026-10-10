#!/bin/bash
# tests/test_backup.sh — scripts/backup-jsons.sh + scripts/restore-json.py (saida TAP).
# Tudo num diretório temporário: OV_STATE_ROOT/OV_BACKUP_DIR apontam para fora do bot real.
# Uso: bash tests/test_backup.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"

TOTAL=10
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT
export OV_STATE_ROOT="$TMPD/bot" OV_BACKUP_DIR="$TMPD/backups"
mkdir -p "$OV_STATE_ROOT/state/front" "$OV_BACKUP_DIR"
cp tests/fixtures/aplicadas.valida.json "$OV_STATE_ROOT/aplicadas.json"
cp tests/fixtures/aplicadas.valida.json "$OV_STATE_ROOT/state/front/aplicadas.json"

# Rotação da raiz não pode apagar backups de perfil (o glob antigo "aplicadas.*" casava os dois).
for i in $(seq -w 1 20); do touch "$OV_BACKUP_DIR/aplicadas.perfil-front.202601${i}-0800.json"; done
for i in $(seq -w 1 20); do echo '{"aplicadas":[]}' > "$OV_BACKUP_DIR/aplicadas.202601${i}-0800.json"; done
bash scripts/backup-jsons.sh >/dev/null 2>&1
relata $? "backup com fontes válidas sai 0"
NRAIZ=$(ls "$OV_BACKUP_DIR"/aplicadas.[0-9]*.json | wc -l)
NPERF=$(ls "$OV_BACKUP_DIR"/aplicadas.perfil-front.*.json | wc -l)
[ "$NRAIZ" -eq 14 ]; relata $? "rotação da raiz mantém 14 (obtido: $NRAIZ)"
[ "$NPERF" -eq 14 ]; relata $? "perfil mantém as próprias 14, não é podado pela raiz (obtido: $NPERF)"

# Fonte corrompida: backup pulado, exit != 0, cópias boas preservadas.
ANTES=$(ls "$OV_BACKUP_DIR"/aplicadas.[0-9]*.json | sort)
printf '{"aplicadas": [' > "$OV_STATE_ROOT/aplicadas.json"
bash scripts/backup-jsons.sh >/dev/null 2>&1
[ $? -ne 0 ]; relata $? "fonte corrompida faz o backup sair != 0"
DEPOIS=$(ls "$OV_BACKUP_DIR"/aplicadas.[0-9]*.json | sort)
[ "$ANTES" = "$DEPOIS" ]; relata $? "fonte corrompida não entra na rotação nem apaga cópias boas"

# restore: --verificar acusa backup inválido.
RUIM="$OV_BACKUP_DIR/aplicadas.$(date -u -d @0 +%Y%m%d)-0000.json"   # carimbo antigo, fora da rotação
printf 'lixo' > "$RUIM"
"$PY" scripts/restore-json.py --verificar >/dev/null 2>&1
[ $? -eq 1 ]; relata $? "--verificar sai 1 com backup inválido"
"$PY" scripts/restore-json.py "$RUIM" --aplicar >/dev/null 2>&1
RC=$?
CORPO=$(cat "$OV_STATE_ROOT/aplicadas.json")
[ $RC -ne 0 ] && [ "$CORPO" = '{"aplicadas": [' ]; relata $? "backup inválido é recusado e o destino fica intocado"

# restore válido: simulação não altera; --aplicar troca e guarda o atual.
BOM=$(ls -t "$OV_BACKUP_DIR"/aplicadas.perfil-front.[0-9]*.json | head -1)
echo '{"aplicadas":[{"chave":"so-no-atual"}]}' > "$OV_STATE_ROOT/state/front/aplicadas.json"
SAIDA=$("$PY" scripts/restore-json.py "$BOM" 2>&1)
grep -q '"so-no-atual"' "$OV_STATE_ROOT/state/front/aplicadas.json" && grep -q 'risco de reenvio' <<<"$SAIDA"
relata $? "simulação não altera o destino e avisa aplicadas que seriam esquecidas"
"$PY" scripts/restore-json.py "$BOM" --aplicar >/dev/null 2>&1
cmp -s <("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])))' "$BOM") \
       <("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])))' "$OV_STATE_ROOT/state/front/aplicadas.json")
relata $? "--aplicar restaura o conteúdo do backup no perfil certo"
ls "$OV_BACKUP_DIR"/aplicadas.perfil-front.pre-restore.*.json >/dev/null 2>&1 \
  && grep -q 'so-no-atual' "$OV_BACKUP_DIR"/aplicadas.perfil-front.pre-restore.*.json
relata $? "estado anterior guardado como pre-restore antes de substituir"

exit $((FAIL > 0))
