#!/bin/bash
# funnel.sh — funil vistas → aplicadas → respostas a partir de aplicadas.json.
# Uso: ./scripts/funnel.sh [--aplicadas PATH] [--csv [PATH]]
#   --csv: exporta o funil em CSV (padrão: funil.csv no diretório atual).
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APLICADAS="${BOT_APLICADAS:-$BOT_ROOT/bot/aplicadas.json}"
CSV=""

while [ $# -gt 0 ]; do
  case "$1" in
    --aplicadas) APLICADAS="$2"; shift 2 ;;
    --csv) CSV="${2:-funil.csv}"; if [[ "$CSV" == --* ]]; then CSV="funil.csv"; shift 1; else shift 2 2>/dev/null || shift 1; fi ;;
    -h|--help) echo "Uso: $(basename "$0") [--aplicadas PATH] [--csv [PATH]]"; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

[ -f "$APLICADAS" ] || { echo "aplicadas.json não encontrado: $APLICADAS" >&2; exit 1; }
export FUNNEL_APLICADAS="$APLICADAS" FUNNEL_CSV="$CSV"
python3 -c "
import csv, json, os
ap = json.load(open(os.environ['FUNNEL_APLICADAS']))
apl = ap.get('aplicadas', [])
bloq = ap.get('bloqueados', {}) or {}
desc = ap.get('descartes_listagem', {}) or {}
desc_total = desc.get('total', sum(v for k, v in desc.items() if isinstance(v, (int, float)) and k != 'total'))
vistas = int(desc_total or 0) + len(apl) + len(bloq)
aplicadas = len(apl)
# Resposta = entrada aplicada com desfecho registrado (status diferente de 'enviada' ou com respondida_em/desfecho).
resps = [a for a in apl if (a.get('status') not in (None, '', 'enviada')) or a.get('respondida_em') or a.get('desfecho')]
taxa_ap = (aplicadas / vistas * 100) if vistas else 0.0
taxa_rp = (len(resps) / aplicadas * 100) if aplicadas else 0.0
rows = [('vistas', vistas), ('aplicadas', aplicadas), ('respostas', len(resps))]
print('Funil vistas -> aplicadas -> respostas')
for etapa, qtd in rows: print('  %-10s %d' % (etapa, qtd))
print('Taxa vistas->aplicadas: %.1f%% | aplicadas->respostas: %.1f%%' % (taxa_ap, taxa_rp))
print('Descartes na listagem: %s | Bloqueadas: %d' % (desc, len(bloq)))
csv_path = os.environ['FUNNEL_CSV']
if csv_path:
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['etapa', 'quantidade'])
        w.writerows(rows)
    print('CSV exportado: ' + csv_path)
"
