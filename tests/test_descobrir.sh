#!/bin/bash
# tests/test_descobrir.sh — suite TAP (bash puro, offline) para bot/descobrir.py.
# Cobre: parsers (LinkedIn/Gupy), filtros de titulo por perfil, dedupe contra aplicadas.json,
# fila (coletar/prompt/marcar) com a rede simulada por fixtures em tests/fixtures/.
# Uso: bash tests/test_descobrir.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TOTAL=7
N=0
FAIL=0
echo "1..$TOTAL"

relata() { # relata <status: 0=ok> <descricao>
  N=$((N + 1))
  if [ "$1" -eq 0 ]; then
    echo "ok $N - $2"
  else
    echo "not ok $N - $2"
    FAIL=$((FAIL + 1))
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp tests/fixtures/aplicadas.descobrir.json "$TMP/aplicadas.json"
cat > "$TMP/descoberta.json" <<'JSON'
{"stack_evitar": ["php", "flutter"], "stack_preferida": ["python", "backend"], "max_ofertas": 2, "intervalo_min": 0}
JSON
export BOT_PERFIL="$ROOT/config/perfis/junior-backend.example.json"
export STATE_DIR="$TMP" APLICADAS_FILE="$TMP/aplicadas.json" OV_DESCOBERTA_CONFIG="$TMP/descoberta.json"
export ROOT
export SNIPPET="$TMP/snippet.py"

# Roda $SNIPPET com o modulo carregado, rede/relogio/sleep simulados.
run_snippet() {
  python3 - >/dev/null <<'PYEOF'
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import descobrir as d

FIX = os.path.join(os.environ["ROOT"], "tests", "fixtures")
d.agora = lambda: datetime.fromisoformat("2026-09-29T12:00:00-03:00")
d.time.sleep = lambda s: None
LI = open(os.path.join(FIX, "linkedin_search.html"), encoding="utf-8").read()
GU = open(os.path.join(FIX, "gupy_jobs.html"), encoding="utf-8").read()
d.get = lambda url, timeout=20: LI if "linkedin" in url else GU
exec(open(os.environ["SNIPPET"], encoding="utf-8").read())
PYEOF
}

# 1 — parser LinkedIn: 6 cards validos, ids, titulo sem HTML, empresa, data.
cat > "$SNIPPET" <<'PYSNIP'
jobs = d.parse_linkedin(LI)
assert len(jobs) == 6, len(jobs)
j = jobs[0]
assert j["id"] == "li:1234567890" and j["titulo"] == "Desenvolvedor Backend Júnior", j
assert j["empresa"] == "Acme Tech" and j["publicada"] == "2026-09-27", j
assert j["url"] == "https://www.linkedin.com/jobs/view/1234567890/", j
PYSNIP
run_snippet && relata 0 "parse_linkedin extrai id/titulo/empresa/data" || relata 1 "parse_linkedin extrai id/titulo/empresa/data"

# 2 — parser Gupy: descarta pais estrangeiro; sem pais assume Brasil.
cat > "$SNIPPET" <<'PYSNIP'
jobs = d.parse_gupy(d.gupy_jobs_da_pagina(GU))
assert [j["id"] for j in jobs] == ["gupy:9000001", "gupy:9000003"], jobs
assert jobs[0]["publicada"] == "2026-09-28" and jobs[0]["empresa"] == "Exemplo Gupy", jobs[0]
PYSNIP
run_snippet && relata 0 "parse_gupy filtra pais e normaliza campos" || relata 1 "parse_gupy filtra pais e normaliza campos"

# 3 — filtros de titulo dirigidos pelo perfil (nivel, tipo, modelo, stack, antiga, empresa).
cat > "$SNIPPET" <<'PYSNIP'
ctx = d.Ctx()
def m(titulo, **kw):
    v = {"titulo": titulo, "empresa": kw.get("empresa", "X"), "local": kw.get("local", "Brasil"), "publicada": kw.get("pub", "2026-09-28")}
    return d.motivo_filtro(ctx, v, kw.get("pular", []))
assert m("Desenvolvedor Backend Junior") is None
assert m("Desenvolvedor Backend") is None            # ambiguo passa (o robo le o anuncio)
assert m("Engenheiro Senior Java") == "nivel"
assert m("Dev Pleno") == "nivel"
assert m("Senior ou Junior Dev") is None             # nivel aceito presente
assert m("Analista de BI Junior") == "tipo"
assert m("Dev Junior Presencial") == "modelo"
assert m("Dev Junior", local="Sao Paulo - Hibrido") == "modelo"
assert m("Dev PHP Junior") == "stack"
assert m("Dev PHP e Python Junior") is None          # stack preferida resgata
assert m("Dev Junior", pub="2026-08-01") == "antiga"
assert m("Dev Junior", empresa="Acme Bloqueada Ltda", pular=["Acme Bloqueada"]) == "empresa"
PYSNIP
run_snippet && relata 0 "motivo_filtro respeita nivel/tipo/modelo/stack/idade/empresa" || relata 1 "motivo_filtro respeita nivel/tipo/modelo/stack/idade/empresa"

# 4 — ids conhecidos: url do LinkedIn, chave e bloqueados.
cat > "$SNIPPET" <<'PYSNIP'
ids, blobs, pular = d.ids_conhecidos(os.environ["APLICADAS_FILE"])
assert "li:6666666666" in ids and "gupy:9000003" in ids, ids
assert pular == ["Empresa Bloqueada"], pular
assert d.job_ids("indeed_x_1", {"url": "https://br.indeed.com/viewjob?jk=0123456789abcdef"}) == {"indeed:0123456789abcdef"}
assert d.job_ids("gupy_acme_1234567", {}) == {"gupy:1234567"}
PYSNIP
run_snippet && relata 0 "ids_conhecidos e job_ids leem url/chave/bloqueados" || relata 1 "ids_conhecidos e job_ids leem url/chave/bloqueados"

# 5 — coletar com fixtures: fila so tem as vagas boas, o resto vira filtrada.
cat > "$SNIPPET" <<'PYSNIP'
ctx = d.Ctx()
assert d.coletar(ctx, force=True) == 0
fila = json.load(open(ctx.fila_path, encoding="utf-8"))["vagas"]
nova = sorted(k for k, v in fila.items() if v["status"] == "nova")
assert nova == ["gupy:9000001", "li:1234567890"], nova
motivos = {k: v.get("motivo") for k, v in fila.items() if v["status"] != "nova"}
assert motivos["li:2222222222"] == "nivel" and motivos["li:3333333333"] == "tipo", motivos
assert motivos["li:4444444444"] == "modelo" and motivos["li:5555555555"] == "antiga", motivos
assert "li:6666666666" not in fila and "gupy:9000003" not in fila, "ja registradas nao entram"
PYSNIP
run_snippet && relata 0 "coletar monta a fila e classifica o resto (offline)" || relata 1 "coletar monta a fila e classifica o resto (offline)"

# 6 — prompt conta ofertas; marcar expira apos max_ofertas e fecha o que foi registrado.
cat > "$SNIPPET" <<'PYSNIP'
import io, contextlib
ctx = d.Ctx()
d.coletar(ctx, force=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    d.prompt(ctx, 1)
out = buf.getvalue()
assert "VAGAS PRÉ-FILTRADAS" in out and "DADOS" in out, out   # aviso de conteudo de terceiros
fila = json.load(open(ctx.fila_path, encoding="utf-8"))["vagas"]
assert sorted(v.get("mostrada", 0) for v in fila.values() if v["status"] == "nova") == [0, 1]   # shown, not yet an offer
for _ in range(2):
    with contextlib.redirect_stdout(io.StringIO()):
        d.prompt(ctx, 5)
# o robo registra uma delas: aplicadas ganha a url
ap = json.load(open(ctx.paths["aplicadas"], encoding="utf-8"))
ap["aplicadas"].append({"chave": "gupy_exemplo_9000001", "url": "https://exemplo.gupy.io/jobs/9000001"})
json.dump(ap, open(ctx.paths["aplicadas"], "w", encoding="utf-8"))
with contextlib.redirect_stdout(io.StringIO()):
    d.marcar(ctx)            # no round log: each round with an open offer counts once
fila = json.load(open(ctx.fila_path, encoding="utf-8"))["vagas"]
assert fila["gupy:9000001"]["status"] == "processada", fila["gupy:9000001"]
assert fila["li:1234567890"]["status"] == "nova" and fila["li:1234567890"]["ofertas"] == 1, fila["li:1234567890"]
with contextlib.redirect_stdout(io.StringIO()):
    d.prompt(ctx, 5)
    d.marcar(ctx)
fila = json.load(open(ctx.fila_path, encoding="utf-8"))["vagas"]
assert fila["li:1234567890"]["status"] == "expirada", fila["li:1234567890"]
PYSNIP
run_snippet && relata 0 "prompt conta ofertas; marcar fecha registradas e expira excedentes" || relata 1 "prompt conta ofertas; marcar fecha registradas e expira excedentes"

# 7 — marcar LOG: oferta so conta se o id aparece no log; DESCARTADA em texto vira bloqueado; duplicada filtrada.
cat > "$SNIPPET" <<'PYSNIP'
import contextlib, io
ctx = d.Ctx()
v = lambda i, e, t: {"id": "li:" + i, "fonte": "linkedin", "url": f"https://www.linkedin.com/jobs/view/{i}/",
                     "titulo": t, "empresa": e, "status": "nova", "score": 2, "ofertas": 0}
json.dump({"vagas": {"li:111": v("111", "Solfy", "Dev Jr"), "li:222": v("222", "Acme", "Backend Jr"),
                     "li:333": v("333", "Beta", "Front Jr")}}, open(ctx.fila_path, "w", encoding="utf-8"))
log = os.path.join(os.environ["STATE_DIR"], "r.log")
open(log, "w").write("navigate https://www.linkedin.com/jobs/view/222/\n111 | Dev Jr | DESCARTADA por REGRA 1 (so remoto)\n")
with contextlib.redirect_stdout(io.StringIO()):
    d.prompt(ctx, 5)
    d.marcar(ctx, log)
f = json.load(open(ctx.fila_path, encoding="utf-8"))["vagas"]
a = json.load(open(ctx.paths["aplicadas"], encoding="utf-8"))
assert f["li:111"]["status"] == "processada" and "li_111" in a["bloqueados"], f["li:111"]
assert f["li:222"]["ofertas"] == 1 and f["li:333"]["ofertas"] == 0 and "oferta_aberta" not in f["li:333"], f
assert d.descarte({"id": "li:9"}, "9 | x | NAO DESCARTADA, aplicar") is None
assert d._gemea({"empresa": "LINA ", "titulo": "Backend Júnior"}) == d._gemea({"empresa": "lina", "titulo": "Backend Junior"})
PYSNIP
run_snippet && relata 0 "marcar LOG: oferta so conta se aberta, descarte em texto registrado, duplicada" || relata 1 "marcar LOG: oferta so conta se aberta, descarte em texto registrado, duplicada"

[ "$FAIL" -eq 0 ] || { echo "# $FAIL falha(s) de $TOTAL"; exit 1; }
exit 0
