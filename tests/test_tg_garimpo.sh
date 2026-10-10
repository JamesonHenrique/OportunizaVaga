#!/bin/bash
# tests/test_tg_garimpo.sh — suite TAP (bash puro, offline, sem telethon) para bot/tg-garimpo.py.
# Cobre: pre-filtro de mensagens dirigido pelo perfil, extracao de links/e-mails/botoes, dedupe,
# gravacao preservando contadores de oferta e o bloco de prompt (com aviso de conteudo de terceiros).
# Fixture: tests/fixtures/telegram_msgs.json (mensagens sinteticas). Uso: bash tests/test_tg_garimpo.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TOTAL=6
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
echo '{"aplicadas": [{"chave": "x_1", "url": "https://empresa-e.example/apply/6"}]}' > "$TMP/aplicadas.json"
export BOT_PERFIL="$ROOT/config/perfis/junior-backend.example.json"
export STATE_DIR="$TMP" APLICADAS_FILE="$TMP/aplicadas.json" ROOT
export OV_TELEGRAM_CANAIS="$TMP/canais.json"
echo '{"canais": ["canal_teste"], "max_ofertas": 2}' > "$OV_TELEGRAM_CANAIS"
export SNIPPET="$TMP/snippet.py"

run_snippet() {
  python3 - >/dev/null <<'PYEOF'
import importlib.util, io, json, os, contextlib
root = os.environ["ROOT"]
spec = importlib.util.spec_from_file_location("tg", os.path.join(root, "bot", "tg-garimpo.py"))
tg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tg)   # telethon so e importado dentro de run()/harvest()
MSGS = json.load(open(os.path.join(root, "tests", "fixtures", "telegram_msgs.json"), encoding="utf-8"))
filtro = tg.Filtro(tg.vf.perfil_resolvido(os.environ["BOT_PERFIL"]))
def processa(vistos=None):
    vistos = set() if vistos is None else vistos
    out = []
    for m in MSGS:
        c = tg.processa_mensagem(filtro, "canal_teste", m["id"], "2026-09-28T10:00-03:00", m["text"], m["buttons"], [], vistos)
        if c:
            out.append(c)
    return out
exec(open(os.environ["SNIPPET"], encoding="utf-8").read())
PYEOF
}

# 1 — classify: nivel aceito + modelo aceito, sem tipo/nivel recusado.
cat > "$SNIPPET" <<'PYSNIP'
c = filtro.classify
assert c("Desenvolvedor Backend Junior 100% remoto, candidate-se agora mesmo")
assert not c("Dev Senior remoto, experiencia de 8 anos necessaria")          # sem nivel aceito
assert not c("Vaga Junior presencial em Sao Paulo, mande curriculo")          # sem modelo remoto
assert not c("Vaga Analista de BI Junior remoto, candidate-se")               # pular_tipos no titulo
assert not c("Engenheiro Senior Backend\nremoto\nrequisitos: java e spring\nvai mentorar o time junior")   # nivel recusado no titulo
assert c("Backend remoto\nRequisitos variados\nNivel: Junior") 
assert not c("Vaga Junior hibrida ou remota em SP")                            # modelo recusado sem 100% remoto
assert c("Vaga Junior hibrida ou 100% remoto em SP")
PYSNIP
run_snippet && relata 0 "classify aplica nivel/modelo/tipo do perfil" || relata 1 "classify aplica nivel/modelo/tipo do perfil"

# 2 — extract: links, botoes, e-mails; t.me e ruido.
cat > "$SNIPPET" <<'PYSNIP'
links, emails = tg.extract("Aplique em https://a.example/v/1, ou rh@a.example. Canal https://t.me/x/1", ["https://b.example/apply?u=1", "https://t.me/y/2", None], [])
assert links == ["https://a.example/v/1", "https://b.example/apply?u=1"], links
assert emails == ["rh@a.example"], emails
PYSNIP
run_snippet && relata 0 "extract junta links/botoes/e-mails e ignora t.me" || relata 1 "extract junta links/botoes/e-mails e ignora t.me"

# 3 — fixture completa: so as mensagens 1, 6 e 9 viram candidatas (7 e duplicata do link da 1).
cat > "$SNIPPET" <<'PYSNIP'
ids = [c["id"] for c in processa()]
assert ids == ["canal_teste/1", "canal_teste/6", "canal_teste/9"], ids
c6 = [c for c in processa() if c["id"].endswith("/6")][0]
assert c6["links"] == ["https://empresa-e.example/apply/6?utm=x"], c6
assert c6["post"] == "https://t.me/canal_teste/6"
PYSNIP
run_snippet && relata 0 "fixture: mensagens filtradas, dedupe por link, link do botao" || relata 1 "fixture: mensagens filtradas, dedupe por link, link do botao"

# 4 — grava preserva contadores de oferta entre colheitas e respeita max_saida.
cat > "$SNIPPET" <<'PYSNIP'
out = os.path.join(os.environ["STATE_DIR"], "telegram_vagas.json")
assert tg.grava(out, processa(), 48, 40) == 3
doc = json.load(open(out, encoding="utf-8"))
doc["vagas"][0]["ofertas"] = 1
json.dump(doc, open(out, "w", encoding="utf-8"))
assert tg.grava(out, processa(), 48, 2) == 2
doc = json.load(open(out, encoding="utf-8"))
assert doc["total"] == 2 and doc["vagas"][0]["ofertas"] == 1, doc
PYSNIP
run_snippet && relata 0 "grava preserva ofertas e limita a max_saida" || relata 1 "grava preserva ofertas e limita a max_saida"

# 5 — prompt: pula o que ja esta em aplicadas (url do botao), conta oferta e avisa que o texto e dado.
cat > "$SNIPPET" <<'PYSNIP'
out = os.path.join(os.environ["STATE_DIR"], "telegram_vagas.json")
tg.grava(out, processa(), 48, 40)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    assert tg.prompt(5) == 0
txt = buf.getvalue()
assert "DADO" in txt and "empresa-a.example/vagas/1" in txt and "empresa-f.example" in txt, txt
assert "empresa-e.example" not in txt                       # ja registrada em aplicadas.json
doc = json.load(open(out, encoding="utf-8"))
assert sorted(v["ofertas"] for v in doc["vagas"]) == [0, 1, 2], doc   # a 6 (ja registrada) nao foi ofertada
PYSNIP
run_snippet && relata 0 "prompt pula registradas, conta oferta e marca texto como dado" || relata 1 "prompt pula registradas, conta oferta e marca texto como dado"

# 6 — 10/10: registrada por URL canonica (sem substring): /vaga/1 nao e /vaga/12; utm e caixa do e-mail nao contam.
cat > "$SNIPPET" <<'PYSNIP'
p = os.path.join(os.environ["STATE_DIR"], "reg.json")
json.dump({"aplicadas": [{"chave": "k", "url": "https://x.example/vaga/12?utm_source=t"}],
           "bloqueados": {"b": {"motivo": "enviar para rh@empresa.example"}}}, open(p, "w"))
r = tg.conhecidos(p)
assert not tg.ja_conhecida({"links": ["https://x.example/vaga/1"]}, r)
assert tg.ja_conhecida({"links": ["https://x.example/vaga/12?utm_medium=z"]}, r)
assert tg.ja_conhecida({"emails": ["RH@empresa.example"]}, r)
v = set()
assert tg.processa_mensagem(filtro, "c", 1, None, "Desenvolvedor Junior remoto, vaga aberta para todo o Brasil: https://x.example/vaga/77?utm_source=a", [], [], v)
assert not tg.processa_mensagem(filtro, "c", 2, None, "Desenvolvedor Junior remoto, vaga aberta para todo o Brasil: https://x.example/vaga/77?utm_source=b", [], [], v)
PYSNIP
run_snippet && relata 0 "registrada e repostagem por URL canonica (sem falso positivo de substring)" || relata 1 "registrada e repostagem por URL canonica (sem falso positivo de substring)"

[ "$FAIL" -eq 0 ] || { echo "# $FAIL falha(s) de $TOTAL"; exit 1; }
exit 0
