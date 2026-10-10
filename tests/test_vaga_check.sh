#!/bin/bash
# tests/test_vaga_check.sh — triagem deterministica pela descricao (bot/vaga_check.py) e seu uso
# em bot/descobrir.py (linkedin_detalhe, Gupy, fail-open, tag "[descricao ok]"). Offline, fixtures sinteticas.
# Uso: bash tests/test_vaga_check.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"

TOTAL=9
N=0
FAIL=0
echo "1..$TOTAL"
relata() { N=$((N + 1)); if [ "$1" -eq 0 ]; then echo "ok $N - $2"; else echo "not ok $N - $2"; FAIL=$((FAIL + 1)); fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp tests/fixtures/aplicadas.descobrir.json "$TMP/aplicadas.json"
export BOT_PERFIL="$ROOT/config/perfis/junior-backend.example.json"
export STATE_DIR="$TMP" APLICADAS_FILE="$TMP/aplicadas.json" OV_DESCOBERTA_CONFIG="$ROOT/config/descoberta.example.json"
export ROOT NOTIFY=true   # coletar may alert; never reach the real notifier

# 1 — os 10 casos de referencia (perfil junior-backend + descoberta.example.json).
"$PY" - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import vaga_check as v
casos = [
  (("Vaga 100% remota. Requisitos: Java, Spring, SQL. 1 ano de experiencia.", "Desenvolvedor Junior", None), True),
  (("Remoto. Java e Spring.", "Junior Java Developer", "Pleno-sênior"), False),        # official level wins over the title
  (("Remoto. Node.", "Desenvolvedor Backend", "Não aplicável"), False),                # no JR in title, official not junior
  (("Remoto. Node.", "Desenvolvedor Junior Node", "Não aplicável"), True),             # JR title passes
  (("Requirements: 4+ years of full-stack experience, remote.", "Full-stack Engineer", "Júnior"), False),  # English + hyphen
  (("Somos uma empresa com 20 anos de experiencia no mercado. Remoto, Java.", "Dev Junior", None), True),  # company age
  (("Stack: PHP, Laravel e .NET. Remoto.", "Dev Junior", None), False),                # foreign stack, nothing of the profile
  (("Stack: Java e .NET (desejavel). Remoto.", "Dev Junior", None), True),             # has profile stack
  (("Modelo de trabalho: presencial em SP. Java.", "Dev Junior", None), False),
  (("Modelo de trabalho: hibrido ou remoto. Java.", "Dev Junior", None), True),        # mentions remote -> doubt passes
]
for (texto, titulo, of), esperado in casos:
    ok, motivo = v.avaliar(texto, titulo, of)
    assert ok == esperado, (titulo, of, texto[:40], motivo)
PYEOF
relata $? "10 casos de referencia (nivel oficial, anos EN/hifen, idade da empresa, stack, modelo)"

# 2 — depende do perfil: perfil pleno aceita "Pleno-senior" e nao rejeita "pleno" no papel; sem stack configurada a regra some.
"$PY" - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import perfil_render as pr, vaga_check as v
info = pr.resolver({"niveis": ["pleno", "senior"], "modelos": ["remoto", "hibrido"]})
c = v.configurar(info, {})
assert v.avaliar("Remoto. Desenvolvedor senior. 5 anos de experiencia.", "Dev", "Pleno-sênior", c)[0]
assert not v.avaliar("Vaga para desenvolvedor junior. Remoto.", "Dev", None, c)[0]          # junior refused for this profile
assert not v.avaliar("Vaga para diretor.", "Dev", "Diretor", c)[0]
assert v.avaliar("Modelo de trabalho: hibrido. PHP e .NET.", "Dev", None, c)[0]             # hybrid accepted, stack rule off
assert v.avaliar("Trabalho remoto.", "Analista", "Não aplicável", c)[0]                     # non entry-level: title needs no level word
info2 = pr.resolver({"niveis": ["junior"], "experiencia_max_anos": None})
assert v.avaliar("10 anos ok. 8 anos de experiencia. remoto", "Dev Jr", None, v.configurar(info2, {}))[0]   # null = no ceiling
PYEOF
relata $? "regras seguem o perfil (niveis, modelos, teto de anos nulo, stack vazia)"

# 3 — CLI: COMPATIVEL / INCOMPATIVEL com saida e exit code.
printf 'Remoto. Requisitos: Python, 6 anos de experiencia.\n' > "$TMP/an.txt"
OUT="$("$PY" bot/vaga_check.py checar "$TMP/an.txt" "Dev Junior" 2>&1)"; RC=$?
[ "$RC" -eq 1 ] && echo "$OUT" | grep -q '^INCOMPATIVEL: experiencia'
relata $? "CLI checar: INCOMPATIVEL (exit 1) por anos exigidos"
printf 'Remoto. Python e FastAPI. 1 ano de experiencia.\n' > "$TMP/an2.txt"
"$PY" bot/vaga_check.py checar "$TMP/an2.txt" "Dev Junior" | grep -q '^COMPATIVEL$'
relata $? "CLI checar: COMPATIVEL"

# 4 — descobrir: linkedin_detalhe le descricao + nivel oficial da pagina publica (fixture sintetica).
"$PY" - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import descobrir as d
F = os.path.join(os.environ["ROOT"], "tests", "fixtures")
d.get = lambda url, timeout=20: open(os.path.join(F, "linkedin_vaga.html"), encoding="utf-8").read()
texto, nivel = d.linkedin_detalhe("1234567890")
assert "FastAPI" in texto and "<" not in texto and nivel == "Júnior", (texto[:80], nivel)
ctx = d.Ctx()
v = {"id": "li:1234567890", "fonte": "linkedin", "titulo": "Desenvolvedor Backend Junior"}
assert d.motivo_descricao(ctx, v) is None and v["desc_checada"] and v["nivel_oficial"] == "Júnior"
PYEOF
relata $? "linkedin_detalhe extrai descricao e nivel oficial; vaga compativel passa marcada"

# 5 — descobrir.coletar: Gupy filtra pela descricao da lista; LinkedIn com nivel oficial fora; falha de rede = fail-open.
"$PY" - <<'PYEOF'
import io, contextlib, json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import descobrir as d
F = os.path.join(os.environ["ROOT"], "tests", "fixtures")
rd = lambda n: open(os.path.join(F, n), encoding="utf-8").read()
d.agora = lambda: datetime.fromisoformat("2026-09-29T12:00:00-03:00")
d.time.sleep = lambda s: None
os.environ["OV_DESCOBERTA_CONFIG"] = os.path.join(os.environ["STATE_DIR"], "desc.json")
json.dump({"fontes": ["gupy"], "intervalo_min": 0, "stack_evitar": ["php", ".net"], "stack_preferida": ["python"]},
          open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
d.get = lambda url, timeout=20: rd("gupy_busca_desc.html")
ctx = d.Ctx()
with contextlib.redirect_stdout(io.StringIO()):
    d.coletar(ctx, force=True)
fila = json.load(open(ctx.fila_path, encoding="utf-8"))["vagas"]
assert fila["gupy:9100001"]["status"] == "nova" and fila["gupy:9100001"]["desc_checada"] is True, fila
assert fila["gupy:9100002"]["status"] == "filtrada" and fila["gupy:9100002"]["motivo"].startswith("desc:stack"), fila
assert "_descricao" not in fila["gupy:9100001"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    d.prompt(ctx, 5)
assert "[descrição ok]" in buf.getvalue(), buf.getvalue()
# fail-open: LinkedIn detail fetch raises -> job stays in the queue, untagged
def boom(url, timeout=20):
    raise OSError("rede fora")
d.get = boom
v = {"id": "li:1", "fonte": "linkedin", "titulo": "Dev Junior"}
assert d.motivo_descricao(ctx, v) is None and "desc_checada" not in v
PYEOF
relata $? "coletar: Gupy filtra pela descricao, tag [descricao ok] no prompt, falha de rede = fail-open"

# 7 — max_descricoes limita as paginas de vaga do LinkedIn baixadas por coleta.
"$PY" - <<'PYEOF'
import io, contextlib, json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import descobrir as d
F = os.path.join(os.environ["ROOT"], "tests", "fixtures")
rd = lambda n: open(os.path.join(F, n), encoding="utf-8").read()
d.agora = lambda: datetime.fromisoformat("2026-09-29T12:00:00-03:00")
d.time.sleep = lambda s: None
chamadas = []
def fake(url, timeout=20):
    if "jobPosting" in url:
        chamadas.append(url)
        return rd("linkedin_vaga.html")
    return rd("linkedin_search.html")
d.get = fake
os.environ["OV_DESCOBERTA_CONFIG"] = os.path.join(os.environ["STATE_DIR"], "desc2.json")
json.dump({"fontes": ["linkedin"], "intervalo_min": 0, "max_descricoes": 1}, open(os.environ["OV_DESCOBERTA_CONFIG"], "w"))
ctx = d.Ctx()
with contextlib.redirect_stdout(io.StringIO()):
    d.coletar(ctx, force=True)
assert len(chamadas) == 1, len(chamadas)   # cap is per collection (2 jobs pass the title filters)
PYEOF
relata $? "max_descricoes limita as paginas de vaga baixadas por busca"

# 8 — 10/10: requisitos de anos fora do padrao "N anos de experiencia" (minimo/pelo menos/at least/atuando com).
ROOT="$ROOT" "$PY" - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT"], "bot"))
import perfil_render as pr, vaga_check as v
c = v.configurar(pr.resolver({"niveis": ["junior"], "experiencia_max_anos": 2}), {})
assert not v.avaliar("Remoto. Mínimo 5 anos em Java.", "Dev Junior", None, c)[0]
assert not v.avaliar("Remoto. Pelo menos 4 anos com Python.", "Dev Junior", None, c)[0]
assert not v.avaliar("Remote. At least 3 years with Go.", "Dev Junior", None, c)[0]
assert not v.avaliar("Remoto. 6 anos atuando com Java.", "Dev Junior", None, c)[0]
assert v.avaliar("Remoto. Empresa com 8 anos no mercado. Java.", "Dev Junior", None, c)[0]   # company age, not a requirement
assert v.avaliar("Remoto. Minimo 1 ano com Java.", "Dev Junior", None, c)[0]
PYEOF
relata $? "anos exigidos: minimo/pelo menos/at least/atuando com respeitam o teto"

# 9 — 10/10: perfil que existe mas nao e JSON valido para (antes virava junior/remoto em silencio).
printf '{"niveis": ["pleno"' > "$TMP/perfil-quebrado.json"
SAIDA="$(BOT_PERFIL="$TMP/perfil-quebrado.json" STATE_DIR="$TMP" "$PY" -c 'import sys; sys.path.insert(0, "bot"); import vagas_filtros as vf; vf.perfil_resolvido(vf.resolve_paths()["perfil_file"])' 2>&1)"
RC=$?
[ "$RC" -ne 0 ] && grep -q "perfil inválido" <<<"$SAIDA"
relata $? "perfil corrompido interrompe com mensagem clara (sem cair nos padroes)"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
