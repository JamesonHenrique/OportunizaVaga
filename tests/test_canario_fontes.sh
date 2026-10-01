#!/bin/bash
# tests/test_canario_fontes.sh — contrato dos parsers de portal contra fixtures SINTETICAS (offline) + canario
# (bot/canario-fontes.py) acusando parser quebrado. As fixtures fixam o markup que o projeto ASSUME; so o canario ao
# vivo (cron diario) detecta o portal ter mudado.
# Uso: bash tests/test_canario_fontes.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"

TOTAL=5
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp tests/fixtures/aplicadas.descobrir.json "$TMP/aplicadas.json"
cat > "$TMP/notify.sh" <<'SH'
#!/bin/bash
printf '%s\n' "$1" >> "$NOTIF_OUT"
SH
chmod +x "$TMP/notify.sh"
export ROOT BOT_PERFIL="$ROOT/config/perfis/junior-backend.example.json" STATE_DIR="$TMP" APLICADAS_FILE="$TMP/aplicadas.json"
export OV_DESCOBERTA_CONFIG="$TMP/desc.json" NOTIFY="$TMP/notify.sh" NOTIF_OUT="$TMP/notif.txt"
echo '{"fontes": ["linkedin", "gupy"]}' > "$OV_DESCOBERTA_CONFIG"

# Snippet comum: carrega o modulo com a rede trocada por fixtures.
cat > "$TMP/pre.py" <<'PYEOF'
import importlib.util, os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import descobrir as d
F = os.path.join(os.environ["ROOT"], "tests", "fixtures")
rd = lambda n: open(os.path.join(F, n), encoding="utf-8").read()
def carrega_canario():
    s = importlib.util.spec_from_file_location("canario", os.path.join(os.environ["ROOT"], "bot", "canario-fontes.py"))
    c = importlib.util.module_from_spec(s); s.loader.exec_module(c)
    return c
def rede_boa(url, timeout=20):
    if "seeMoreJobPostings" in url: return rd("linkedin_search.html")
    if "jobPosting" in url: return rd("linkedin_vaga.html")
    if "gupy.io" in url: return rd("gupy_busca_desc.html")
    raise AssertionError("url inesperada: " + url)
PYEOF

# 1 — contrato: LinkedIn busca, pagina de vaga e Gupy parseiam as fixtures.
"$PY" - <<PYEOF
exec(open("$TMP/pre.py").read())
d.get = rede_boa
ctx = d.Ctx()
li = d.linkedin(ctx, "x")
assert li and all(v["id"].startswith("li:") and v["titulo"] and v["url"] for v in li), li[:1]
texto, nivel = d.linkedin_detalhe("123")
assert len(texto) > 100 and nivel, (len(texto), nivel)
gp = d.gupy(ctx, "x")
assert gp and all(v["titulo"] and v["url"] for v in gp) and any(v["_descricao"].strip() for v in gp), gp
PYEOF
relata $? "contrato dos parsers: busca LinkedIn, pagina da vaga (descricao + nivel) e Gupy (descricao)"

# 2 — canario com portais saudaveis: sem falhas, exit 0, nada notificado.
: > "$NOTIF_OUT"
"$PY" - <<PYEOF
exec(open("$TMP/pre.py").read())
c = carrega_canario()
c.d.get = rede_boa
assert c.checar() == [], c.checar()
PYEOF
relata $? "canario: portais saudaveis = nenhuma falha"

# 3 — portal vazio / markup mudado: cada fonte quebrada e apontada.
"$PY" - <<PYEOF
exec(open("$TMP/pre.py").read())
c = carrega_canario()
c.d.get = lambda url, timeout=20: "<html></html>" if "linkedin" in url else '<script id="__NEXT_DATA__">{"props": {"pageProps": {"initialJobList": {"data": []}}}}</script>'
f = c.checar()
assert "LinkedIn busca: 0 vagas" in f and "Gupy busca: 0 vagas" in f, f
# LinkedIn search ok, job page without description/level; Gupy without description
def meio(url, timeout=20):
    if "seeMoreJobPostings" in url: return rd("linkedin_search.html")
    if "jobPosting" in url: return "<html><div>mudou</div></html>"
    return '<script id="__NEXT_DATA__">{"props": {"pageProps": {"initialJobList": {"data": [{"id": 1, "name": "Dev Jr", "jobUrl": "https://x.example/1"}]}}}}</script>'
c.d.get = meio
f = c.checar()
assert "LinkedIn vaga: descricao vazia" in f and "LinkedIn vaga: sem nivel de experiencia oficial" in f and "Gupy busca: sem descricao" in f, f
def quebra(url, timeout=20): raise OSError("rede")
c.d.get = quebra
assert c.checar() == ["LinkedIn busca: OSError", "Gupy busca: OSError"], c.checar()
PYEOF
relata $? "canario: portal vazio, pagina sem descricao/nivel, Gupy sem descricao e erro de rede sao acusados"

# 4 — so as fontes habilitadas em descoberta.json sao checadas.
echo '{"fontes": ["gupy"]}' > "$OV_DESCOBERTA_CONFIG"
"$PY" - <<PYEOF
exec(open("$TMP/pre.py").read())
c = carrega_canario()
chamadas = []
def so_gupy(url, timeout=20):
    chamadas.append(url)
    return rd("gupy_busca_desc.html")
c.d.get = so_gupy
assert c.checar() == [] and all("gupy" in u for u in chamadas) and chamadas, chamadas
PYEOF
relata $? "canario respeita 'fontes' (sem LinkedIn = nenhuma requisicao ao LinkedIn)"
echo '{"fontes": ["linkedin", "gupy"]}' > "$OV_DESCOBERTA_CONFIG"

# 5 — CLI: falha => exit 2 e notificacao; usa o notificador do ambiente (rede trocada por um wrapper sem rede real).
: > "$NOTIF_OUT"
"$PY" - <<PYEOF
exec(open("$TMP/pre.py").read())
c = carrega_canario()
c.d.get = lambda url, timeout=20: "<html></html>" if "linkedin" in url else '<script id="__NEXT_DATA__">{"props": {"pageProps": {"initialJobList": {"data": []}}}}</script>'
rc = c.main()
assert rc == 2, rc
PYEOF
RC=$?
[ "$RC" -eq 0 ] && grep -q "CANARIO.*LinkedIn busca: 0 vagas" "$NOTIF_OUT"
relata $? "main: parser quebrado => exit 2 e alerta enviado pelo notificador"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
