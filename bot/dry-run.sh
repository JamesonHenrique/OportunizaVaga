#!/bin/bash
# bot/dry-run.sh — simula UMA rodada sem se candidatar (teste sem risco).
# So LE arquivos: valida os JSONs, mostra o site do rodozio e lista o que a
# rodada FARIA (site, termos de busca, limite, modelo preferido). Nao abre
# browser, nao chama o opencode, nao escreve nada, nao se candidata.
# Requer apenas bash + python3 (funciona sem Chrome/opencode instalados).
# Uso: ./bot/dry-run.sh [--json]   (--json = saida maquina em JSON)
set -u

JSON_OUT=0
for a in "$@"; do
  case "$a" in
    --json) JSON_OUT=1 ;;
    -h|--help)
      echo "Uso: bot/dry-run.sh [--json]"
      echo "Simula uma rodada sem se candidatar. Exit 0 = rodada simulada ok."
      exit 0 ;;
    *) echo "opcao desconhecida: $a (use --help)" >&2; exit 2 ;;
  esac
done

BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BOT_ROOT/bot" || exit 1

command -v python3 >/dev/null 2>&1 || { echo "ERRO: python3 nao encontrado." >&2; exit 1; }

# Modelo preferido = primeiro da escada em bot/loop.sh (fonte unica de verdade).
MODELO_PREFERIDO="$(grep -oE '"opencode/[^"]+"' "$BOT_ROOT/bot/loop.sh" 2>/dev/null | head -1 | tr -d '"')"
[ -z "$MODELO_PREFERIDO" ] && MODELO_PREFERIDO="opencode/muse-spark-1.3-contributor-free"

DADOS_REAIS=1
[ -f "dados_candidato.json" ] || DADOS_REAIS=0
APLIC_REAIS=1
[ -f "aplicadas.json" ] || APLIC_REAIS=0

export DRY_MODELO="$MODELO_PREFERIDO" DRY_JSON="$JSON_OUT"
export DRY_DADOS="$([ "$DADOS_REAIS" = "1" ] && echo dados_candidato.json || echo ../examples/dados_candidato.example.json)"
export DRY_APLIC="$([ "$APLIC_REAIS" = "1" ] && echo aplicadas.json || echo ../examples/aplicadas.example.json)"
export DRY_DADOS_REAIS="$DADOS_REAIS" DRY_APLIC_REAIS="$APLIC_REAIS"

python3 <<'PYEOF'
import json, os

def carrega(caminho, rotulo):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, "%s: JSON invalido ou ilegivel (%s)" % (rotulo, e)

modelo = os.environ["DRY_MODELO"]
saida_json = os.environ["DRY_JSON"] == "1"
dados_caminho = os.environ["DRY_DADOS"]
aplic_caminho = os.environ["DRY_APLIC"]
dados_reais = os.environ["DRY_DADOS_REAIS"] == "1"
aplic_reais = os.environ["DRY_APLIC_REAIS"] == "1"

erros = []
dados, e = carrega(dados_caminho, "dados_candidato")
if e:
    erros.append(e)
else:
    for k in ("nome", "email", "telefone", "linkedin", "local"):
        if k not in dados:
            erros.append("dados_candidato: chave obrigatoria ausente: '%s'" % k)

aplic, e = carrega(aplic_caminho, "aplicadas")
if e:
    erros.append(e)
    rodizio, ordem, proximo = {}, [], "?"
else:
    rodizio = aplic.get("rodizio", {}) if isinstance(aplic, dict) else {}
    ordem = rodizio.get("ordem", [])
    proximo = rodizio.get("proximo", "?")
    if not isinstance(aplic, dict) or "aplicadas" not in aplic:
        erros.append("aplicadas: chave obrigatoria ausente: 'aplicadas'")
    if not proximo or proximo == "?":
        erros.append("aplicadas: chave obrigatoria ausente: 'rodizio.proximo'")

if ordem and proximo in ordem:
    seguinte = ordem[(ordem.index(proximo) + 1) % len(ordem)]
else:
    seguinte = "?"

# Termos espelham bot/prompt_loop.md (secao b, TERMOS) — a rodada real alterna
# entre eles priorizando o stack real de dados_candidato.json.
termos = [
    "desenvolvedor fullstack junior",
    "backend junior remoto",
    "desenvolvedor junior remoto",
    "trainee desenvolvedor remoto",
]
limite = 3  # regra 5 do prompt_loop.md: maximo 3 candidaturas novas por rodada
n_aplic = len(aplic.get("aplicadas", [])) if isinstance(aplic, dict) else 0
bloq = aplic.get("bloqueados", {}) if isinstance(aplic, dict) else {}
n_bloq = len(bloq) if isinstance(bloq, dict) else 0

if erros:
    if saida_json:
        print(json.dumps({"ok": False, "dry_run": True, "erros": erros},
                         ensure_ascii=False))
    else:
        print("dry-run: FALHOU — corrija antes de rodar o loop real:")
        for x in erros:
            print("  [FALHA] " + x)
    raise SystemExit(1)

if saida_json:
    print(json.dumps({
        "ok": True,
        "dry_run": True,
        "site": proximo,
        "site_seguinte": seguinte,
        "ordem_rodizio": ordem,
        "termos_busca": termos,
        "limite_candidaturas": limite,
        "modelo_preferido": modelo,
        "dados_fonte": ("bot/dados_candidato.json"
                        if dados_reais else "examples/dados_candidato.example.json"),
        "estado_fonte": ("bot/aplicadas.json"
                         if aplic_reais else "examples/aplicadas.example.json"),
        "aplicadas_registradas": n_aplic,
        "bloqueados_registrados": n_bloq,
        "browser_aberto": False,
        "candidaturas_enviadas": 0,
    }, ensure_ascii=False))
else:
    print("dry-run: UMA rodada simulada (nada foi enviado, nenhum browser aberto).")
    print("  JSONs validos: %s | %s" % (dados_caminho, aplic_caminho))
    print("  site desta rodada (rodizio.proximo): %s" % proximo)
    print("  site seguinte sera: %s" % seguinte)
    print("  termos de busca que usaria: %s" % "; ".join(termos))
    print("  limite: %d candidaturas novas (regra 5)" % limite)
    print("  modelo preferido (1o da escada em bot/loop.sh): %s" % modelo)
    print("  estado atual: %d aplicadas, %d bloqueados" % (n_aplic, n_bloq))
PYEOF
