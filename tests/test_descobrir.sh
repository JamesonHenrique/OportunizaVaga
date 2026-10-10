#!/bin/bash
# tests/test_descobrir.sh — suite TAP (bash puro, offline) para bot/descobrir.py.
# Cobre: parsers (LinkedIn/Gupy), filtros de titulo por perfil, dedupe contra aplicadas.json,
# fila (coletar/prompt/marcar) com a rede simulada por fixtures em tests/fixtures/.
# Uso: bash tests/test_descobrir.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TOTAL=19
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
export ROOT NOTIFY=true   # coletar may alert; never reach the real notifier
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
assert d.job_ids("indeed_x_1", {"url": "https://br.indeed.com/viewjob?jk=0123456789abcdef"}) == {"indeed:0123456789abcdef", "url:indeed.com/viewjob?jk=0123456789abcdef"}
# canonical url (reposts under new ids): one job = one url; recruiter profiles / homes / t.me are not identities
assert d.url_canon("https://vagas.example.com/vaga/AbC123/") == d.url_canon("https://www.vagas.example.com/vaga/AbC123") != ""
assert d.url_canon("https://vagas.example.com/vaga/AbC123") != d.url_canon("https://vagas.example.com/vaga/XyZ789")
assert d.url_canon("https://br.linkedin.com/in/fulana-") == "" and d.url_canon("https://t.me/canal/123") == ""
assert d.url_canon("https://acme.com/") == "" and d.url_canon("") == "" and d.url_canon("mailto:x@y.z") == ""
assert d.url_canon("https://www.linkedin.com/jobs/view/123/") == d.url_canon("https://br.linkedin.com/jobs/view/123") != ""
assert d.url_canon("https://boards.greenhouse.io/acme/jobs/55?gh_src=x") == "url:boards.greenhouse.io/acme/jobs/55"
# 10/10: unknown id params stay (two jobs, two keys); tracking params go; search pages are never a job
assert d.url_canon("https://x.com/vagas/detalhe?codigo=55") != d.url_canon("https://x.com/vagas/detalhe?codigo=56")
assert d.url_canon("https://x.com/vagas/detalhe?codigo=55&utm_source=tg&ref=a") == d.url_canon("https://x.com/vagas/detalhe?codigo=55")
assert d.url_canon("https://acme.com/vaga-12345") != "" and d.url_canon("https://acme.com/jobs/search?q=java") == ""
assert d.url_canon("https://www.linkedin.com/jobs/view/3912345678/?trk=a&refId=b") == d.url_canon("https://linkedin.com/jobs/view/3912345678")
# 10/10: company as whole words (all of them), and an explicit different level is a different job
assert not d.ja_registrada({"empresa": "SAP", "titulo": "Backend Java Developer"}, ["sapiens backend java developer"])
assert not d.ja_registrada({"empresa": "Banco Pan", "titulo": "Backend Java Developer"}, ["banco inter backend java developer"])
assert not d.ja_registrada({"empresa": "Banco Inter", "titulo": "Backend Java Pleno"}, ["banco inter backend java junior"])
assert d.ja_registrada({"empresa": "Banco Inter", "titulo": "Backend Java Junior"}, ["banco inter backend java junior"])
assert d.ja_registrada({"empresa": "Acme S.A.", "titulo": "Backend Java Developer"}, ["acme sa backend java developer"])
# near-twin titles: reposts match, two real postings of one company do not (measured on 57 real records)
A = lambda e, t: d._assinatura({"empresa": e, "titulo": t})
assert d.gemea_de({"empresa": "Acme | Eng", "titulo": "Back End C++(17)"}, [A("Acme | Eng", "Back End C++(17)")])
assert d.gemea_de({"empresa": "Beta", "titulo": "Desenvolvedor de Automacao e IA Jr (remoto)"}, [A("Beta (Oficial)", "Desenvolvedor de Automação e IA Jr")])
assert not d.gemea_de({"empresa": "Gama", "titulo": "Backend Java Junior (Remoto, qualquer lugar)"}, [A("Gama", "Backend Java – Sustentação (Remoto, qualquer lugar)")])
assert not d.gemea_de({"empresa": "Delta", "titulo": "Fullstack Backend Junior"}, [A("Delta", "Fullstack Backend - Trainee")])
assert not d.gemea_de({"empresa": "Acme", "titulo": "Backend Junior"}, [A("Outra", "Backend Junior")])
assert d.ja_registrada({"empresa": "XYZ", "titulo": "Software Engineer OpenText Exstream"}, ["xyz systems software engineer opentext exstream junior"])
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
# the echo of the model's own add-bloqueado is not a text discard (it would store the job twice)
assert d.descarte({"id": "li:4300000444"}, "$ python3 estado.py add-bloqueado g_4300000444 '{\"motivo\":\"DESCARTADA\"}'") is None
assert d._gemea({"empresa": "LINA ", "titulo": "Backend Júnior"}) == d._gemea({"empresa": "lina", "titulo": "Backend Junior"})
PYSNIP
run_snippet && relata 0 "marcar LOG: oferta so conta se aberta, descarte em texto registrado, duplicada" || relata 1 "marcar LOG: oferta so conta se aberta, descarte em texto registrado, duplicada"

# 8 — fonte fora do ar: aviso na hora; um termo falhando nao avisa; volta avisa 1x.
cat > "$SNIPPET" <<'PYSNIP'
msgs = []; d.notificar = msgs.append; fila = {}
d.avisar_fontes(fila, {"gupy": [4, 4, 0], "linkedin": [3, 0, 40]}, ["gupy:HTTPError"] * 4)
assert len(msgs) == 1 and "gupy" in msgs[0] and "HTTPError" in msgs[0] and fila["fontes_quebradas"] == ["gupy"], (msgs, fila)
d.avisar_fontes(fila, {"gupy": [4, 1, 0]}, ["gupy:URLError"])   # 0 vagas = still down
assert len(msgs) == 2 and "voltou" not in msgs[1], msgs
d.avisar_fontes(fila, {"gupy": [4, 0, 30]}, [])
assert len(msgs) == 3 and "voltou" in msgs[2] and fila["fontes_quebradas"] == [], msgs
PYSNIP
run_snippet && relata 0 "fonte fora do ar avisa na hora; volta avisa 1x" || relata 1 "fonte fora do ar avisa na hora; volta avisa 1x"

# 9 — instalacao privada: termos_arquivo, score_palavras, prompt_registro, OV_ESTADO_PY e caminho (fila|rodizio).
cat > "$SNIPPET" <<'PYSNIP'
import io, contextlib, subprocess
T = os.environ["STATE_DIR"]
json.dump({"termos": ["termo do arquivo"]}, open(T + "/termos.json", "w"))
json.dump({"termos_arquivo": T + "/termos.json", "score_palavras": ["automacao"], "prompt_registro": "RODAPE PRIVADO"},
          open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx()
assert ctx.termos == ["termo do arquivo"], ctx.termos
assert d.score(ctx, {"titulo": "Analista de Automação"}) >= 2 and d.score(ctx, {"titulo": "Desenvolvedor Java"}) < 2
json.dump({"vagas": {"li:4000000001": {"status": "nova", "score": 2, "titulo": "Dev", "empresa": "Acme", "fonte": "linkedin",
                                      "url": "https://www.linkedin.com/jobs/view/4000000001/"}}}, open(ctx.fila_path, "w"))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    d.prompt(ctx, 5)
assert "RODAPE PRIVADO" in buf.getvalue(), buf.getvalue()
chamadas = []
real_run = subprocess.run
d.subprocess.run = lambda cmd, **k: chamadas.append(cmd) or real_run(["true"])
os.environ["OV_ESTADO_PY"] = "/privado/estado.py"; os.environ["OV_RODADA"] = "R1"
rec = lambda c, u: {"chave": c, "empresa": "Acme", "vaga": "Dev", "status": "enviada", "url": u, "rodada": "R1"}
json.dump({"aplicadas": [rec("acme_a_4000000001", "https://www.linkedin.com/jobs/view/4000000001/"),
                         rec("acme_b_4000000002", "https://www.linkedin.com/jobs/view/4000000002/")],
           "bloqueados": {}}, open(ctx.paths["aplicadas"], "w"))
json.dump({"vagas": {"li:4000000001": {"status": "nova", "score": 2, "titulo": "Dev", "empresa": "Acme", "fonte": "linkedin",
                                      "id": "li:4000000001", "termo": "java junior", "ofertas": 1, "oferta_aberta": True,
                                      "url": "https://www.linkedin.com/jobs/view/4000000001/"}}}, open(ctx.fila_path, "w"))
open(T + "/rodada.log", "w").write("browser_navigate https://www.linkedin.com/jobs/view/4000000001/\n... RESULTADO enviadas=2 avaliadas=3 bloqueadas=0 quase_la=0 site=netvagas obs=x\n")
with contextlib.redirect_stdout(io.StringIO()):
    d.marcar(ctx, T + "/rodada.log")
cam = {(c[5], c[6]): c[7] for c in chamadas if "set-campo" in c}
assert all(c[1] == "/privado/estado.py" for c in chamadas), chamadas
assert cam == {("acme_a_4000000001", "caminho"): "fila", ("acme_b_4000000002", "caminho"): "rodizio",
               ("acme_a_4000000001", "descoberta"): "linkedin:java junior",
               ("acme_b_4000000002", "descoberta"): "rodizio:netvagas"}, cam
assert d.descoberta({"fonte": "telegram", "termo": "telegram:devsvagas"}) == "telegram:devsvagas"
assert d.descoberta({"fonte": "gupy"}) == "gupy" and d.descoberta(None, "fila") == "rodizio"
PYSNIP
run_snippet && relata 0 "instalacao privada: termos_arquivo, score_palavras, prompt_registro, OV_ESTADO_PY, caminho" || relata 1 "instalacao privada: termos_arquivo, score_palavras, prompt_registro, OV_ESTADO_PY, caminho"

# 10 — Gupy pela API paginada do portal (limit = gupy_limite, so remoto); erro na API = cai na pagina (__NEXT_DATA__).
cat > "$SNIPPET" <<'PYSNIP'
urls = []
API = json.dumps({"data": [{"id": 77, "name": "Dev Jr", "jobUrl": "https://x.gupy.io/job/1", "careerPageName": "X",
                            "publishedDate": "2026-09-29T10:00:00Z", "description": "Java remoto"}], "pagination": {"total": 1}})
d.get = lambda url, timeout=20: urls.append(url) or (API if "/api/job-search/jobs" in url else GU)
ctx = d.Ctx()
v = d.gupy(ctx, "dev jr")
assert [x["id"] for x in v] == ["gupy:77"] and "limit=100" in urls[0] and "workplaceType=remote" in urls[0] and len(urls) == 1, urls
pag = lambda off: json.dumps({"data": [{"id": off + i, "name": "Dev Jr", "jobUrl": f"https://x.gupy.io/job/{off + i}"} for i in range(100 if off < 200 else 50)],
                              "pagination": {"total": 100}})   # the real API lies about total
urls.clear(); d.get = lambda url, timeout=20: urls.append(url) or pag(int(url.split("offset=")[1].split("&")[0]))
assert len(d.gupy(ctx, "dev")) == 250 and len(urls) == 3 and "offset=200" in urls[2], urls
def quebra(url, timeout=20):
    urls.append(url)
    if "/api/job-search/" in url: raise OSError("api fora")
    return GU
d.get = quebra
assert d.gupy(ctx, "dev jr") and "job-search/term=" in urls[-1], urls[-2:]
PYSNIP
run_snippet && relata 0 "gupy: API paginada do portal, com fallback para a pagina" || relata 1 "gupy: API paginada do portal, com fallback para a pagina"

# 11 — titulo_exige: termo amplo traz outras areas; sem palavra da area = filtrada "area" (lista vazia = desligado).
cat > "$SNIPPET" <<'PYSNIP'
json.dump({"titulo_exige": ["desenvolvedor", "software", "trainee"]}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx()
assert d.motivo_filtro(ctx, {"titulo": "Analista Fiscal Junior"}, []) == "area"
assert d.motivo_filtro(ctx, {"titulo": "Desenvolvedor Júnior"}, []) is None
assert d.motivo_filtro(ctx, {"titulo": "Consultor(a) Técnico(a) Trainee"}, []) is None
json.dump({}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
assert d.motivo_filtro(d.Ctx(), {"titulo": "Analista Fiscal Junior"}, []) is None
PYSNIP
run_snippet && relata 0 "titulo_exige: outra area vira filtrada 'area'" || relata 1 "titulo_exige: outra area vira filtrada 'area'"

# 12 — LinkedIn: sufixo "remoto" na busca (o guest ignora f_WT) e card com cidade no local = "modelo" (perfil so remoto).
cat > "$SNIPPET" <<'PYSNIP'
json.dump({"linkedin_sufixo": "remoto", "linkedin_cidade_fora": True}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx(); urls = []
d.get = lambda url, timeout=20: urls.append(url) or LI
d.linkedin(ctx, "java junior"); d.linkedin(ctx, "python junior remoto")
assert "keywords=java+junior+remoto" in urls[0] and "keywords=python+junior+remoto&" in urls[1], urls
li = lambda t, l: {"titulo": t, "local": l, "fonte": "linkedin"}
assert d.motivo_filtro(ctx, li("Dev Java Jr", "São Paulo, SP"), []) == "modelo"
assert d.motivo_filtro(ctx, li("Dev Java Jr", "Belo Horizonte e Região"), []) == "modelo"
assert d.motivo_filtro(ctx, li("Dev Java Jr (Remoto)", "São Paulo, SP"), []) is None
assert d.motivo_filtro(ctx, li("Dev Java Jr", "Brasil"), []) is None
assert d.motivo_filtro(ctx, {"titulo": "Dev Java Jr", "local": "São Paulo, SP", "fonte": "gupy"}, []) is None
assert d.motivo_filtro(ctx, li("Dev Java Jr", "São Paulo, SP (Remoto)"), []) is None   # 10/10: logged-in card
assert d.motivo_filtro(ctx, li("Dev Java Jr", "São Paulo, São Paulo, Brasil (Híbrido)"), []) == "modelo"
# 10/10: a 429 pauses the LinkedIn searches of this collection; Easy Apply scores +1 and is tagged in the offer
import urllib.error as _ue
chamadas = []
def g429(url, timeout=20):
    chamadas.append(url); raise _ue.HTTPError(url, 429, "Too Many Requests", {}, None)
d.get = g429
try:
    d.linkedin(ctx, "java junior")
except _ue.HTTPError as e:
    assert e.code == 429
v1 = {"titulo": "Dev Java Jr", "local": "Brasil", "fonte": "linkedin", "id": "li:1"}
assert d.motivo_descricao(ctx, v1) is None and ctx.li_429 is True
n = len(chamadas); assert d.motivo_descricao(ctx, v1) is None and len(chamadas) == n   # no more requests
assert d.score(ctx, dict(v1, simplificada=True)) == d.score(ctx, v1) + 1
info = {}; d.linkedin_parse('<a data-tracking-control-name="public_jobs_apply-link-simple_onsite">', info)
assert info == {"simplificada": True}
json.dump({}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
assert d.motivo_filtro(d.Ctx(), li("Dev Java Jr", "São Paulo, SP"), []) is None   # off by default
PYSNIP
run_snippet && relata 0 "linkedin: sufixo remoto e cidade no local = modelo" || relata 1 "linkedin: sufixo remoto e cidade no local = modelo"

# 13 — paginacao: LinkedIn pagina 1 + N-1 a partir do cursor do termo (volta ao inicio na pagina vazia); Gupy ate a pagina curta.
cat > "$SNIPPET" <<'PYSNIP'
import re as _re
json.dump({"linkedin_paginas": 3, "linkedin_sufixo": "remoto"}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx(); starts = []
def card(i): return f'<li><a href="https://br.linkedin.com/jobs/view/dev-{i}?x"></a><h3 class="base-search-card__title">Dev Jr {i}</h3></li>'
def li_get(url, timeout=20):
    st = int(_re.search(r"start=(\d+)", url).group(1)); starts.append(st)
    return "".join(card(4000000000 + st + k) for k in range(10 if st < 50 else 0))
d.get = li_get
assert len(d.linkedin(ctx, "java junior")) == 30 and starts == [0, 10, 20] and ctx.li_cursor == {"java junior": 30}, (starts, ctx.li_cursor)
starts.clear(); d.linkedin(ctx, "java junior"); assert starts == [0, 30, 40] and ctx.li_cursor["java junior"] == 50, starts
starts.clear(); d.linkedin(ctx, "java junior"); assert starts == [0, 50] and ctx.li_cursor["java junior"] == 10, starts   # empty page wraps
pag = lambda off: json.dumps({"data": [{"id": off + i, "name": "Dev", "jobUrl": f"https://x.gupy.io/job/{off + i}"} for i in range(100 if off < 300 else 79)]})
urls = []; d.get = lambda url, timeout=20: urls.append(url) or pag(int(url.split("offset=")[1].split("&")[0]))
assert len(d.gupy(ctx, "analista")) == 379 and len(urls) == 4, len(urls)
PYSNIP
run_snippet && relata 0 "paginacao: LinkedIn incremental por cursor, Gupy ate o fim" || relata 1 "paginacao: LinkedIn incremental por cursor, Gupy ate o fim"

# 14 — coleta: triagem por descricao comeca pelo maior score (max_descricoes); prazo estourado nao abre busca e GRAVA a fila.
cat > "$SNIPPET" <<'PYSNIP'
import io, contextlib
json.dump({"fontes": ["linkedin"], "max_descricoes": 1, "intervalo_min": 0}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx()
json.dump({"vagas": {}}, open(ctx.fila_path, "w")); json.dump({"aplicadas": []}, open(ctx.paths["aplicadas"], "w"))
vs = [{"id": "li:4100000001", "fonte": "linkedin", "titulo": "Analista Junior", "empresa": "A", "url": "u1", "local": "Brasil"},
      {"id": "li:4100000002", "fonte": "linkedin", "titulo": "Desenvolvedor Backend Java Junior", "empresa": "B", "url": "u2", "local": "Brasil"}]
d.FONTES["linkedin"] = lambda c, t: [dict(v) for v in vs]
checadas = []; d.motivo_descricao = lambda c, v: checadas.append(v["id"]) or None
with contextlib.redirect_stdout(io.StringIO()):
    d.coletar(ctx, force=True)
assert checadas == ["li:4100000002"], checadas   # best score first, only 1 page fetched
json.dump({"fontes": ["linkedin"], "tempo_max_s": -1}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx(); json.dump({"vagas": {}}, open(ctx.fila_path, "w"))
with contextlib.redirect_stdout(io.StringIO()):
    d.coletar(ctx, force=True)
f = json.load(open(ctx.fila_path))
assert "linkedin:prazo" in f["stats"]["erros"] and f.get("ultima_coleta"), f.get("stats")
PYSNIP
run_snippet && relata 0 "coleta: triagem pelo maior score; prazo estourado grava a fila" || relata 1 "coleta: triagem pelo maior score; prazo estourado grava a fila"

# 15 — triar (05/10): link de perfil, vaga encerrada e descricao incompativel saem da fila antes da sessao; falha de rede nao corta.
cat > "$SNIPPET" <<'PYSNIP'
import io, contextlib
json.dump({}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx(); json.dump({"aplicadas": []}, open(ctx.paths["aplicadas"], "w"))
nova = lambda i, url, fonte="telegram": {"id": i, "fonte": fonte, "titulo": "Desenvolvedor Java Junior", "empresa": "E" + i,
                                         "url": url, "status": "nova", "score": 2}
json.dump({"vagas": {"a": nova("a", "https://br.linkedin.com/in/recrutadora-123"), "b": nova("b", "https://x.com/vaga/fechada"),
                     "c": nova("c", "https://x.com/vaga/ok"), "e": nova("e", "https://x.com/vaga/rede")}}, open(ctx.fila_path, "w"))
corpo = "Vaga remota para desenvolvedor Java junior com Spring Boot e APIs REST. " * 8
def fake(url, timeout=20):
    if url.endswith("rede"): raise OSError("offline")
    return ("Esta vaga foi encerrada " if url.endswith("fechada") else "") + "<p>" + corpo + "</p>"
d.get = fake; d.time.sleep = lambda s: None
with contextlib.redirect_stdout(io.StringIO()):
    d.triar(ctx, 8)
f = json.load(open(ctx.fila_path))["vagas"]
assert f["a"]["status"] == "filtrada" and "url" in f["a"]["motivo"], f["a"]
assert f["b"]["status"] == "filtrada" and "encerrada" in f["b"]["motivo"], f["b"]
assert f["c"]["status"] == "nova" and f["c"].get("desc_checada"), f["c"]
assert f["e"]["status"] == "nova" and f["e"].get("triagem_falhou"), f["e"]
PYSNIP
run_snippet && relata 0 "triar: perfil, encerrada e descricao ruim saem antes da sessao; rede fora nao corta" || relata 1 "triar: perfil, encerrada e descricao ruim saem antes da sessao; rede fora nao corta"

# 16 — boards respeitam robots.txt (05/10): caminho proibido nao e baixado; robots ilegivel = permitido.
cat > "$SNIPPET" <<'PYSNIP'
pedidos = []
def fake(url, timeout=20):
    pedidos.append(url)
    if url == "https://a.example/robots.txt": return "User-agent: *\nDisallow: /privado\n"
    if url == "https://b.example/robots.txt": raise OSError("404")
    return "ok"
d.get = fake; d._ROBOTS.clear()
assert d.get_robots("https://a.example/vagas") == "ok"
try:
    d.get_robots("https://a.example/privado/x"); raise AssertionError("baixou caminho proibido")
except PermissionError:
    pass
assert "https://a.example/privado/x" not in pedidos and pedidos.count("https://a.example/robots.txt") == 1, pedidos
assert d.get_robots("https://b.example/qualquer") == "ok"
PYSNIP
run_snippet && relata 0 "boards: robots.txt respeitado (proibido nao baixa; ilegivel permite)" || relata 1 "boards: robots.txt respeitado (proibido nao baixa; ilegivel permite)"

# 17 — embargo_dias (06/10): eu.dev.br esconde descricao e link por 48 h atras de passe pago; a vaga fica na fila
# ("nova") e so e oferecida/triada depois de publicada + N dias. Fonte sem embargo e vaga sem data nao esperam.
cat > "$SNIPPET" <<'PYSNIP'
from datetime import date
cfg = {"embargo_dias": {"eu.dev.br": 2}}
hoje = date(2026, 10, 6)
nova = lambda f, pub: {"status": "nova", "fonte": f, "publicada": pub, "score": 3, "titulo": "Dev Jr", "id": f + pub}
assert d.embargada(cfg, nova("eu.dev.br", "2026-10-05"), hoje)            # 1 dia: ainda no paywall
assert not d.embargada(cfg, nova("eu.dev.br", "2026-10-04"), hoje)        # 2 dias: anuncio aberto
assert not d.embargada(cfg, nova("linkedin", "2026-10-06"), hoje)         # fonte sem embargo
assert not d.embargada(cfg, {"fonte": "eu.dev.br", "publicada": None}, hoje)
assert not d.embargada({}, nova("eu.dev.br", "2026-10-06"), hoje)         # config sem a chave = comportamento antigo
fila = {"vagas": {"a": nova("eu.dev.br", "2026-10-06"), "b": nova("eu.dev.br", "2026-10-01"), "c": nova("gupy", "2026-10-06")}}
ids = sorted(v["id"] for v in d.pendentes(fila, cfg, hoje))
assert ids == ["eu.dev.br2026-10-01", "gupy2026-10-06"], ids
assert len(d.pendentes(fila)) == 3                                        # sem cfg (contagem do marcar): todas
PYSNIP
run_snippet && relata 0 "embargo_dias: fonte com paywall espera N dias na fila" || relata 1 "embargo_dias: fonte com paywall espera N dias na fila"

# 18 — fila sem perda (06/10): descobrir e tg-garimpo gravavam a fila inteira; o ultimo apagava as vagas novas do
# outro. salvar_fila relê sob trava e aplica so o que ESTE processo mudou desde que leu.
cat > "$SNIPPET" <<'PYSNIP'
import copy
vf = d.vf
base = {"vagas": {"a": {"status": "nova", "score": 2}}, "stats": {"telegram": {"em": "t0"}, "lidas": 1}, "termo_idx": 0}
meu = copy.deepcopy(base)
meu["vagas"]["a"]["status"] = "processada"; meu["vagas"]["b"] = {"status": "nova"}
meu["stats"]["lidas"] = 9; meu["termo_idx"] = 4
atual = copy.deepcopy(base)                                   # meanwhile tg-garimpo saved:
atual["vagas"]["c"] = {"status": "nova", "fonte": "telegram"}; atual["stats"]["telegram"] = {"em": "t1"}
out = vf.mesclar(base, meu, atual)
assert set(out["vagas"]) == {"a", "b", "c"}, out                          # nobody's new job is lost
assert out["vagas"]["a"]["status"] == "processada" and out["termo_idx"] == 4
assert out["stats"] == {"telegram": {"em": "t1"}, "lidas": 9}, out["stats"]  # both stats changes survive
sem_b = copy.deepcopy(meu); del sem_b["vagas"]["b"]; assert "b" not in vf.mesclar(base, sem_b, atual)["vagas"]
apagada = copy.deepcopy(base); del apagada["vagas"]["a"]                 # this run deleted a, nobody touched it
assert "a" not in vf.mesclar(base, apagada, copy.deepcopy(base))["vagas"]
p = os.environ["STATE_DIR"] + "/fila_mescla.json"
vf.save_json(p, atual)
vf.salvar_fila(p, base, meu)
assert set(vf.load_json(p, {})["vagas"]) == {"a", "b", "c"} and os.path.exists(p + ".lock")
PYSNIP
run_snippet && relata 0 "fila: salvar_fila mescla sob trava (nenhuma vaga nova se perde)" || relata 1 "fila: salvar_fila mescla sob trava (nenhuma vaga nova se perde)"

# 15 — 09/10: perfil remoto + hibrido com "cidades": hibrida/cidade so dentro da lista; Gupy grava o local real.
cat > "$SNIPPET" <<'PYSNIP'
perfil = json.load(open(os.environ["BOT_PERFIL"]))
perfil.update({"modelos": ["remoto", "hibrido"], "cidades": ["Paraná", "PR", "Curitiba", "Londrina"]})
pf = os.environ["STATE_DIR"] + "/perfil_rn.json"; json.dump(perfil, open(pf, "w"))
os.environ["BOT_PERFIL"] = pf
json.dump({"linkedin_cidade_fora": True, "boards": []}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx()
v = lambda t, l, f="gupy": {"titulo": t, "local": l, "fonte": f, "empresa": "X", "publicada": "2026-09-28"}
assert d.motivo_filtro(ctx, v("Dev Junior", "hibrido - São Paulo, São Paulo"), []) == "modelo"
assert d.motivo_filtro(ctx, v("Dev Junior", "hibrido - Curitiba, Paraná"), []) is None
assert d.motivo_filtro(ctx, v("Dev Junior", "hibrido - Londrina, PR"), []) is None
assert d.motivo_filtro(ctx, v("Dev Junior", "presencial - Curitiba, Paraná"), []) == "modelo"
assert d.motivo_filtro(ctx, v("Dev Junior", "remoto"), []) is None
assert d.motivo_filtro(ctx, v("Dev Junior Hibrido (Campinas)", "Brasil", "linkedin"), []) == "modelo"
assert d.motivo_filtro(ctx, v("Dev Junior", "São Paulo, SP", "linkedin"), []) == "modelo"
assert d.motivo_filtro(ctx, v("Dev Junior", "Curitiba, PR", "linkedin"), []) is None
assert d.motivo_filtro(ctx, v("Dev Junior (Remoto)", "São Paulo, SP", "linkedin"), []) is None
assert d.motivo_filtro(ctx, v("Dev Junior", "Brasil", "linkedin"), []) is None
assert d.motivo_filtro(ctx, v("Dev Junior Sprint", "Recife, PE", "linkedin"), []) == "modelo"   # "pr" only as a word
g = lambda **k: d.parse_gupy([dict({"id": 1, "jobUrl": "u", "name": "Dev"}, **k)])[0]["local"]
assert g(workplaceType="remote", city="", state="") == "remoto"
assert g(workplaceType="hybrid", city="Curitiba", state="Paraná") == "hibrido - Curitiba, Paraná"
assert g(workplaceType="on-site", city="Santos", state="São Paulo") == "presencial - Santos, São Paulo"
assert g() == "remoto"
assert d.gupy_buscas(ctx.info) == [{"workplaceType": "remote"}, {"workplaceType": "hybrid", "state": "Paraná"},
                                  {"workplaceType": "hybrid", "city": "Curitiba"}, {"workplaceType": "hybrid", "city": "Londrina"}]
assert d.gupy_buscas({"modelos": ["remoto"]}) == [{"workplaceType": "remote"}]
assert d.gupy_buscas({"modelos": ["remoto", "hibrido"]}) == [{"workplaceType": "remote"}, {"workplaceType": "hybrid"}]
assert d.gupy_buscas({"modelos": ["remoto", "presencial"]}) == [{}]
urls = []
job = lambda i: {"id": i, "name": "Dev Jr", "jobUrl": "https://x.gupy.io/job/%d" % i, "workplaceType": "remote"}
d.get = lambda url, timeout=20: urls.append(url) or json.dumps({"data": [job(1), job(2)] if "remote" in url else [job(2)]})
d.time.sleep = lambda s: None
v = d.gupy(ctx, "dev jr")
assert len(urls) == 4 and "workplaceType=hybrid&state=Paran%C3%A1" in urls[1] and "city=Curitiba" in urls[2], urls
assert sorted(x["id"] for x in v) == ["gupy:1", "gupy:2"], v   # same job from two searches = one listing
PYSNIP
run_snippet && relata 0 "hibrido so nas cidades do perfil; Gupy grava o modelo e o local reais" || relata 1 "hibrido so nas cidades do perfil; Gupy grava o modelo e o local reais"

[ "$FAIL" -eq 0 ] || { echo "# $FAIL falha(s) de $TOTAL"; exit 1; }
exit 0
