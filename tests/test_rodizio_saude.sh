#!/bin/bash
# tests/test_rodizio_saude.sh — suite minima em bash puro (sem framework), saida TAP.
# Cobre: bot/rodizio-saude.py (pausa progressiva 12h->48h de site SECO, minimo de sites ativos, ordem do dia).
# Uso: bash tests/test_rodizio_saude.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
SAUDE="bot/rodizio-saude.py"

TOTAL=12
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

TMPDIR_STATE="$(mktemp -d)"
TMP_STATE="$TMPDIR_STATE/aplicadas.json"
cp examples/aplicadas.example.json "$TMP_STATE"
cleanup() { rm -rf "$TMPDIR_STATE"; }
trap cleanup EXIT

# 1 — pre roda sem erro numa rodada sem sites pausados (nada a pular).
OUT1="$(python3 "$SAUDE" pre "$TMP_STATE" 2>&1)"
ST1=$?
if [ "$ST1" -eq 0 ]; then
  relata 0 "pre roda sem erro sem sites pausados"
else
  echo "$OUT1"
  relata 1 "pre roda sem erro sem sites pausados"
fi

# 2 — site com 3 rodadas seguidas ja sem candidatura (seed) + mais 1 rodada vazia = pausa (4a).
python3 - "$TMPDIR_STATE/rodizio_saude.json" <<'PYEOF'
import json, sys
json.dump({"sites": {"indeed": {"rodadas": 3, "vazias_seguidas": 3, "aplicadas": 0, "pausado_ate": None}}}, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF
python3 "$SAUDE" pre "$TMP_STATE" >/dev/null 2>&1   # rodizio.proximo comeca em "indeed"
OUT2="$(python3 "$SAUDE" pos "$TMP_STATE" 2>&1)"
if echo "$OUT2" | grep -q "indeed pausado"; then
  relata 0 "site pausado apos 4 rodadas seguidas sem candidatura"
else
  echo "$OUT2"
  relata 1 "site pausado apos 4 rodadas seguidas sem candidatura"
fi

# 3 — rodizio_saude.json foi criado no MESMO diretorio do aplicadas.json (isolado por perfil)
# e marca indeed como pausado.
if python3 -c "
import json, sys
d = json.load(open('$TMPDIR_STATE/rodizio_saude.json', encoding='utf-8'))
sys.exit(0 if d.get('sites', {}).get('indeed', {}).get('pausado_ate') else 1)
"; then
  relata 0 "rodizio_saude.json marca indeed como pausado"
else
  relata 1 "rodizio_saude.json marca indeed como pausado"
fi

# 4 — pos com candidatura nova (enviada DURANTE a rodada) zera vazias_seguidas do site da vez.
# rodizio.proximo ja avancou para "linkedin" no teste 2; pre() marca o inicio da rodada de
# linkedin ANTES da candidatura ser gravada, exatamente como o loop real faz.
python3 "$SAUDE" pre "$TMP_STATE" >/dev/null 2>&1
python3 - "$TMP_STATE" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d.setdefault("aplicadas", []).append({"chave": "teste-rodizio", "empresa": "AcmeCorp", "vaga": "Dev Jr"})
json.dump(d, open(p, "w", encoding="utf-8"))
PYEOF
python3 "$SAUDE" pos "$TMP_STATE" >/dev/null 2>&1
VAZIAS_SEGUIDAS="$(python3 -c "
import json
d = json.load(open('$TMPDIR_STATE/rodizio_saude.json', encoding='utf-8'))
print(d.get('sites', {}).get('linkedin', {}).get('vazias_seguidas', 'sem-site'))
")"
if [ "$VAZIAS_SEGUIDAS" = "0" ]; then
  relata 0 "candidatura nova zera vazias_seguidas do site"
else
  echo "vazias_seguidas=$VAZIAS_SEGUIDAS"
  relata 1 "candidatura nova zera vazias_seguidas do site"
fi

# 5-6 — reordenar (rendimento): saida deterministica numa fixture; >=1 vaga por site; sem repeticao seguida.
OUT5="$(python3 - <<'PYEOF'
import importlib.util, os
spec = importlib.util.spec_from_file_location("rs", os.path.join("bot", "rodizio-saude.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ordem = ["gupy", "linkedin", "indeed", "gupy", "linkedin", "indeed", "remotar", "programathor", "infojobs", "geekhunter"]
sites = {"gupy": {"rodadas": 10, "aplicadas": 6}, "linkedin": {"rodadas": 10, "aplicadas": 3}, "indeed": {"rodadas": 10, "aplicadas": 0},
         "remotar": {"rodadas": 2, "aplicadas": 0}, "programathor": {"rodadas": 8, "aplicadas": 1}}
ap = [{"status": "entrevista", "como": "Gupy"}, {"status": "etapa_teste", "como": "linkedin easy apply"}, {"status": "em_analise", "como": "indeed"}]
nova, notas = m.reordenar(ordem, sites, ap)
nova2, _ = m.reordenar(ordem, sites, ap)
print(",".join(nova))
print("deterministico" if nova == nova2 else "instavel")
print("tamanho-ok" if len(nova) == len(ordem) else "tamanho-errado")
print("um-por-site" if set(nova) == set(ordem) else "site-sumiu")
print("sem-repeticao" if all(a != b for a, b in zip(nova, nova[1:])) else "repetiu")
print("nota-gupy=%.3f" % notas["gupy"])
PYEOF
)"
EXPECTED5="gupy,linkedin,infojobs,indeed,remotar,programathor,geekhunter,gupy,linkedin,infojobs"
if [ "$(echo "$OUT5" | sed -n 1p)" = "$EXPECTED5" ] && [ "$(echo "$OUT5" | sed -n 6p)" = "nota-gupy=0.692" ]; then
  relata 0 "reordenar: ordem e notas esperadas na fixture (gupy=0.692)"
else
  echo "$OUT5"
  relata 1 "reordenar: ordem e notas esperadas na fixture"
fi
if [ "$(echo "$OUT5" | sed -n '2,5p' | tr '\n' ' ')" = "deterministico tamanho-ok um-por-site sem-repeticao " ]; then
  relata 0 "reordenar: deterministico, mesmo tamanho, >=1 vaga por site, sem repeticao seguida"
else
  echo "$OUT5"
  relata 1 "reordenar: deterministico, mesmo tamanho, >=1 vaga por site, sem repeticao seguida"
fi

# 7 — pre recalcula 1x por dia (ordem_calculada_em) e mantem o proximo; segunda chamada no mesmo dia nao mexe.
DIR7="$(mktemp -d)"
python3 - "$DIR7" <<'PYEOF'
import json, os, sys
d = sys.argv[1]
json.dump({"rodizio": {"ordem": ["gupy", "indeed", "gupy", "indeed", "remotar", "linkedin"], "proximo": "indeed", "pos": 1}, "aplicadas": []},
          open(os.path.join(d, "aplicadas.json"), "w", encoding="utf-8"))
json.dump({"sites": {"gupy": {"rodadas": 10, "aplicadas": 8}, "indeed": {"rodadas": 10, "aplicadas": 0},
                      "remotar": {"rodadas": 5, "aplicadas": 0}, "linkedin": {"rodadas": 5, "aplicadas": 1}}},
          open(os.path.join(d, "rodizio_saude.json"), "w", encoding="utf-8"))
PYEOF
python3 "$SAUDE" pre "$DIR7/aplicadas.json" >/dev/null 2>&1
ORD_A="$(python3 -c "import json; r=json.load(open('$DIR7/aplicadas.json'))['rodizio']; print(','.join(r['ordem']), r['ordem_calculada_em'], r['proximo'], r['ordem'][r['pos']])")"
python3 "$SAUDE" pre "$DIR7/aplicadas.json" >/dev/null 2>&1
ORD_B="$(python3 -c "import json; r=json.load(open('$DIR7/aplicadas.json'))['rodizio']; print(','.join(r['ordem']), r['ordem_calculada_em'], r['proximo'], r['ordem'][r['pos']])")"
HOJE="$(date +%Y-%m-%d)"
if [ "$ORD_A" = "$ORD_B" ] && echo "$ORD_A" | grep -q " $HOJE indeed indeed$" && [ "$(echo "$ORD_A" | cut -d' ' -f1 | tr ',' '\n' | grep -c '^gupy$')" -ge 2 ]; then
  relata 0 "pre reordena 1x/dia (ordem_calculada_em), mantem o proximo e favorece o site que rende"
else
  echo "A=$ORD_A B=$ORD_B"
  relata 1 "pre reordena 1x/dia (ordem_calculada_em), mantem o proximo e favorece o site que rende"
fi

# 8 — OV_RODIZIO_REORDENAR=0 desliga a reordenacao.
python3 - "$DIR7" <<'PYEOF'
import json, os, sys
p = os.path.join(sys.argv[1], "aplicadas.json")
d = json.load(open(p, encoding="utf-8"))
d["rodizio"]["ordem"] = ["gupy", "indeed", "gupy", "indeed", "remotar", "linkedin"]
d["rodizio"].pop("ordem_calculada_em", None)
json.dump(d, open(p, "w", encoding="utf-8"))
PYEOF
OV_RODIZIO_REORDENAR=0 python3 "$SAUDE" pre "$DIR7/aplicadas.json" >/dev/null 2>&1
if [ "$(python3 -c "import json; print(','.join(json.load(open('$DIR7/aplicadas.json'))['rodizio']['ordem']))")" = "gupy,indeed,gupy,indeed,remotar,linkedin" ]; then
  relata 0 "OV_RODIZIO_REORDENAR=0 mantem a ordem"
else
  relata 1 "OV_RODIZIO_REORDENAR=0 mantem a ordem"
fi
rm -rf "$DIR7"

# 9 — seco = nenhuma chave nova (vaga bloqueada conta como site vivo); pausa 12h, depois 24h; nunca abaixo de MIN_ATIVOS.
python3 - "$ROOT" "$TMPDIR_STATE" <<'PYEOF'
import importlib.util, json, os, sys
from datetime import datetime
R, T = sys.argv[1], sys.argv[2]
os.environ["OV_RODIZIO_SAUDE"] = T + "/s9.json"; os.environ["NOTIFY"] = "true"
s = importlib.util.spec_from_file_location("r", R + "/bot/rodizio-saude.py"); r = importlib.util.module_from_spec(s); s.loader.exec_module(r)
ap = T + "/a9.json"
def estado(ordem): json.dump({"aplicadas": [], "bloqueados": {}, "rodizio": {"ordem": ordem, "proximo": ordem[0], "pos": 0, "ordem_calculada_em": datetime.now().strftime("%Y-%m-%d")}}, open(ap, "w"))
def rodada(bloquear=None):
    d = json.load(open(ap)); d["rodizio"]["proximo"] = "a"; d["rodizio"]["pos"] = 0; json.dump(d, open(ap, "w"))
    r.main("pre", ap)
    if bloquear:
        d = json.load(open(ap)); d["bloqueados"][bloquear] = {"motivo": "x"}; json.dump(d, open(ap, "w"))
    r.main("pos", ap)
estado(["a", "b", "c", "d"]); json.dump({"sites": {}}, open(os.environ["OV_RODIZIO_SAUDE"], "w"))
for i in range(4): rodada(bloquear=f"k{i}")
assert not json.load(open(os.environ["OV_RODIZIO_SAUDE"]))["sites"]["a"].get("pausado_ate"), "bloqueio novo = site vivo"
h = lambda: (datetime.fromisoformat(json.load(open(os.environ["OV_RODIZIO_SAUDE"]))["sites"]["a"]["pausado_ate"]) - datetime.now()).total_seconds() / 3600
for i in range(4): rodada()
assert 11 < h() < 12.1, h()
sd = json.load(open(os.environ["OV_RODIZIO_SAUDE"])); sd["sites"]["a"]["pausado_ate"] = None; json.dump(sd, open(os.environ["OV_RODIZIO_SAUDE"], "w"))
for i in range(4): rodada()
assert 23 < h() < 24.1, h()
estado(["a", "b"]); json.dump({"sites": {}}, open(os.environ["OV_RODIZIO_SAUDE"], "w"))
for i in range(4): rodada()
assert not json.load(open(os.environ["OV_RODIZIO_SAUDE"]))["sites"]["a"].get("pausado_ate"), "so 1 outro site ativo: nao pausa"
PYEOF
relata $? "seco = sem chave nova; pausa 12h -> 24h; nunca abaixo de MIN_ATIVOS"

# 10 — ordem do dia (OV_SITES_CONFIG com rodizio_produtivos): produtivos em dobro + 1 explorador nao pausado.
python3 - "$ROOT" "$TMPDIR_STATE" <<'PYEOF'
import importlib.util, json, os, sys
from datetime import datetime, timedelta
R, T = sys.argv[1], sys.argv[2]
s = importlib.util.spec_from_file_location("r", R + "/bot/rodizio-saude.py"); r = importlib.util.module_from_spec(s); s.loader.exec_module(r)
json.dump({"rodizio_produtivos": ["linkedin", "gupy"], "rodizio_exploracao": ["catho", "remotar"]}, open(T + "/sites.json", "w"))
os.environ["OV_SITES_CONFIG"] = T + "/sites.json"
assert r.config_rodizio() == (["linkedin", "gupy"], ["catho", "remotar"])
now = datetime(2026, 9, 30, 12, 0)
o, _ = r.ordem_do_dia(["linkedin", "gupy"], ["catho", "remotar"], {"catho": {"pausado_ate": (now + timedelta(hours=5)).isoformat()}}, [], now)
assert len(o) == 5 and o.count("linkedin") == 2 and o.count("remotar") == 1 and "catho" not in o, o
PYEOF
relata $? "ordem do dia: produtivos em dobro + 1 explorador nao pausado (OV_SITES_CONFIG)"

# 11 — 01/10: pos credita ao site da rodada SO o que saiu por ele. Uma rodada que varreu eu.dev.br e
# aplicou pela fila (gupy/inhire) nao pode inflar o rendimento de eu.dev.br — foi assim que ele chegou a
# "4 aplicadas" sem nenhuma candidatura registrada nele, alimentando a promocao D1 com um numero falso.
# pos-so-fila (item 12) tambem carimba ultima_aplicada, o que antes so acontecia no caminho pos.
python3 - "$ROOT" <<'PYEOF'
import importlib.util, json, os, sys, tempfile
from datetime import datetime
R = sys.argv[1]
s = importlib.util.spec_from_file_location("r", R + "/bot/rodizio-saude.py"); r = importlib.util.module_from_spec(s); s.loader.exec_module(r)
T = tempfile.mkdtemp()
os.environ["OV_RODIZIO_SAUDE"] = T + "/saude.json"; os.environ["NOTIFY"] = "true"
ap = T + "/ap.json"
saude = lambda: json.load(open(os.environ["OV_RODIZIO_SAUDE"]))["sites"]
def gravar(sites, prox):
    json.dump({"sites": sites}, open(os.environ["OV_RODIZIO_SAUDE"], "w"))
    json.dump({"aplicadas": [], "bloqueados": {}, "quase_la": {}, "aguardando_login": {},
               "rodizio": {"ordem": ["eu.dev.br", "linkedin"], "proximo": prox, "pos": 0,
                           "ordem_calculada_em": datetime.now().strftime("%Y-%m-%d")}}, open(ap, "w"))
# (a) pos: aplicacao pela fila durante a rodada de eu.dev.br -> eu.dev.br NAO ganha aplicada/ultima_aplicada
gravar({"eu.dev.br": {"rodadas": 1, "vazias_seguidas": 0, "aplicadas": 0, "pausado_ate": None}}, "eu.dev.br")
r.main("pre", ap)
d = json.load(open(ap)); d["aplicadas"].append({"chave": "k1", "empresa": "X", "vaga": "Dev",
                                               "como": "Gupy (conta via Google)"}); json.dump(d, open(ap, "w"))
r.main("pos", ap)
eu = saude()["eu.dev.br"]
assert eu["aplicadas"] == 0, f"fila nao pode virar rendimento do site: {eu}"
assert not eu.get("ultima_aplicada"), f"ultima_aplicada falsa no site errado: {eu}"
# (b) pos: aplicacao que saiu pelo proprio site -> credito normal
gravar({"eu.dev.br": {"rodadas": 1, "vazias_seguidas": 0, "aplicadas": 0, "pausado_ate": None}}, "eu.dev.br")
r.main("pre", ap)
d = json.load(open(ap)); d["aplicadas"].append({"chave": "k2", "empresa": "X", "vaga": "Dev",
                                               "como": "eu.dev.br (site da empresa)"}); json.dump(d, open(ap, "w"))
r.main("pos", ap)
eu = saude()["eu.dev.br"]
assert eu["aplicadas"] == 1 and eu.get("ultima_aplicada"), eu
# (c) pos-so-fila: carimba ultima_aplicada no site que o `como` nomeia (antes nunca carimbava)
gravar({"linkedin": {"rodadas": 0, "vazias_seguidas": 0, "aplicadas": 0, "pausado_ate": None}}, "linkedin")
r.main("pre", ap)
d = json.load(open(ap)); d["aplicadas"].append({"chave": "k3", "empresa": "Y", "vaga": "Dev",
                                               "como": "LinkedIn Candidatura Simplificada"}); json.dump(d, open(ap, "w"))
r.main("pos-so-fila", ap)
li = saude()["linkedin"]
assert li.get("ultima_aplicada"), f"pos-so-fila precisa carimba ultima_aplicada: {li}"
assert li["aplicadas"] == 1 and li["rodadas"] == 0, f"pos-so-fila nao mexe em streak: {li}"
# (d) de_site ignora substring acidental e respeita o prefixo antes do ponto
assert r.de_site({"como": "Gupy via Google"}, "eu.dev.br") is False
assert r.de_site({"como": "Remotar (via Inhire)"}, "remotar") is True
assert r.de_site({"como": "telegram: vaga colhida"}, "linkedin") is False
PYEOF
relata $? "pos credita so o que saiu pelo site; pos-so-fila carimba ultima_aplicada sem mexer no streak"

# 12 — de_site() e a regra unica: o que o contador conta e o que a nota usa.
python3 - "$ROOT" <<'PYEOF'
import importlib.util, sys
s = importlib.util.spec_from_file_location("r", sys.argv[1] + "/bot/rodizio-saude.py"); r = importlib.util.module_from_spec(s); s.loader.exec_module(r)
casos = [({"como": "Gupy (conta via Google)"}, "gupy", True),
         ({"como": "LinkedIn Candidatura Simplificada (easy-apply)"}, "linkedin", True),
         ({"como": "Indeed Candidatura Rapida (SmartApply), login Google"}, "indeed", True),
         ({"como": "eu.dev.br (vaga da empresa)"}, "eu.dev.br", True),
         ({"como": "e-mail x via Gmail"}, "gupy", False),
         ({"como": "vaga colhida no telegram"}, "linkedin", False),
         ({}, "linkedin", False),
         ({"como": None}, "linkedin", False),
         # rotulo curto ("eu") precisa cair em fronteira de palavra: "Queues" contem "eu"
         ({"como": "Queues engineer"}, "eu.dev.br", False),
         ({"como": "Engenheiro de software"}, "eu.dev.br", False)]
for rec, site, esp in casos:
    assert r.de_site(rec, site) is esp, (rec, site, esp)
# a nota usa exatamente a mesma regra (positivos contam 2x)
ap = [{"status": "entrevista", "como": "Gupy via Google"}, {"status": "em_analise", "como": "Gupy via Google"}]
assert r.nota_site("gupy", {"rodadas": 0, "aplicadas": 0}, ap) == (0 + 2 + 1) / 3
assert r.nota_site("linkedin", {"rodadas": 0, "aplicadas": 0}, ap) == (0 + 0 + 1) / 3
PYEOF
relata $? "de_site: regra unica de atribuicao (contador e nota concordam)"

if [ "$FAIL" -eq 0 ]; then
  echo "# verde: $N/$TOTAL"
  exit 0
else
  echo "# FALHAS: $FAIL/$TOTAL"
  exit 1
fi
