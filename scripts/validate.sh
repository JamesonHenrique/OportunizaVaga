#!/bin/bash
# scripts/validate.sh — valida os JSONs do projeto contra os schemas em config/.
# Alvos: examples/*.example.json (obrigatorios) + bot/dados_candidato.json e
# bot/aplicadas.json quando existirem (dados locais, gitignored — nunca commite).
# Usa python3+jsonschema (draft 2020-12) se disponivel; senao faz checagem
# estrutural minima embutida (JSON valido + chaves obrigatorias).
# Exit 0 = tudo ok; 1 = alguma falha. Chamado pelo setup e pelo CI.
set -u
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT" || exit 1

# pares arquivo|schema|obrigatorio(1 = falha se ausente)
PARES=(
  "examples/dados_candidato.example.json|config/dados_candidato.schema.json|1"
  "examples/aplicadas.example.json|config/aplicadas.schema.json|1"
  "bot/dados_candidato.json|config/dados_candidato.schema.json|0"
  "bot/aplicadas.json|config/aplicadas.schema.json|0"
)

ARGS=()
for p in "${PARES[@]}"; do
  f="${p%%|*}"; resto="${p#*|}"; s="${resto%%|*}"; req="${resto##*|}"
  if [ ! -f "$f" ]; then
    if [ "$req" = "1" ]; then
      echo "  [FALHA] $f ausente"
      exit 1
    else
      echo "  [pq] $f ausente — pulando (dado local, gitignored)."
    fi
  elif [ ! -f "$s" ]; then
    echo "  [FALHA] schema ausente: $s"
    exit 1
  else
    ARGS+=("$f|$s")
  fi
done

command -v python3 >/dev/null 2>&1 || { echo "  [FALHA] python3 nao encontrado (necessario p/ validar)."; exit 1; }

python3 - "${ARGS[@]}" <<'PYEOF'
import json, sys

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    HAVE = True
except ImportError:
    HAVE = False
    print("  [..] pacote 'jsonschema' ausente — checagem estrutural minima.")

def minima(doc, schema, rotulo):
    erros = []
    if not isinstance(doc, dict):
        return [rotulo + ": raiz precisa ser objeto JSON"]
    for k in schema.get("required", []):
        if k not in doc:
            erros.append(rotulo + ": chave obrigatoria ausente: '" + k + "'")
    props = schema.get("properties", {})
    if "rodizio" in props and isinstance(doc.get("rodizio"), dict):
        for k in props["rodizio"].get("required", []):
            if k not in doc["rodizio"]:
                erros.append(rotulo + ": chave obrigatoria ausente: 'rodizio." + k + "'")
    if "aplicadas" in doc and not isinstance(doc["aplicadas"], list):
        erros.append(rotulo + ": 'aplicadas' precisa ser array")
    return erros

falhas = 0
for arg in sys.argv[1:]:
    f, s = arg.split("|", 1)
    try:
        doc = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print("  [FALHA] %s: JSON invalido (%s)" % (f, e))
        falhas = 1
        continue
    try:
        schema = json.load(open(s, encoding="utf-8"))
    except Exception as e:
        print("  [FALHA] %s: schema invalido (%s)" % (s, e))
        falhas = 1
        continue
    if HAVE:
        errs = sorted(Draft202012Validator(schema).iter_errors(doc),
                      key=lambda e: list(e.path))
        if errs:
            falhas = 1
            for e in errs:
                loc = "/".join(str(x) for x in e.path) or "(raiz)"
                print("  [FALHA] %s: %s -> %s" % (f, loc, e.message))
        else:
            print("  [ok] %s (jsonschema, draft 2020-12)." % f)
    else:
        errs = minima(doc, schema, f)
        if errs:
            falhas = 1
            for e in errs:
                print("  [FALHA] " + e)
        else:
            print("  [ok] %s (minima: chaves obrigatorias presentes)." % f)

sys.exit(1 if falhas else 0)
PYEOF
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
  echo "validate: OK."
else
  echo "validate: FALHOU (veja itens [FALHA] acima)."
fi
exit "$STATUS"
