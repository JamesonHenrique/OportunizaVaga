#!/bin/bash
# tests/test_perfil_render.sh — suite TAP para bot/perfil_render.py (qualquer nivel/area)
# e para o pulo de sites fora da area no rodizio-saude.py.
# Uso: bash tests/test_perfil_render.sh   (exit 0 = tudo verde)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
RENDER="bot/perfil_render.py"

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

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT

# 1 — nenhum placeholder sobra em nenhum prompt, para nenhum perfil de exemplo.
SOBRA=0
for perfil in config/perfis/*.example.json; do
  for prompt in bot/prompt_loop.md bot/prompt_loop.en.md bot/prompt_triage.md; do
    lang=pt; case "$prompt" in *.en.md) lang=en ;; esac
    python3 "$RENDER" render "$perfil" "$prompt" "$TMPD/out.md" --lang "$lang" || SOBRA=1
    if grep -q '{{[A-Z_]*}}' "$TMPD/out.md"; then
      echo "# sobrou placeholder: $perfil $prompt"
      SOBRA=1
    fi
  done
done
relata "$SOBRA" "todos os placeholders preenchidos (perfis x prompts)"

# 2 — perfil legado so com nivel "junior" mantem o comportamento antigo (junior + trainee).
printf '{"nome_perfil":"legado","nivel":"junior","termos":["x"],"pular_tipos":[]}' > "$TMPD/legado.json"
python3 - "$TMPD/legado.json" <<'PYEOF'
import json, subprocess, sys
info = json.loads(subprocess.check_output([sys.executable, "bot/perfil_render.py", "info", sys.argv[1]]))
assert info["niveis"] == ["trainee", "junior"], info["niveis"]
assert info["area_tech"] is True and info["sites_pular"] == [], info
assert info["experiencia_max_anos"] == 3, info
PYEOF
relata $? "perfil legado (nivel junior) aceita trainee+junior, area tech, teto 3 anos"

# 3 — perfil senior/lider: niveis aceitos e recusados corretos, sem teto de experiencia.
python3 - <<'PYEOF'
import json, subprocess, sys
info = json.loads(subprocess.check_output([sys.executable, "bot/perfil_render.py", "info",
                                           "config/perfis/senior-techlead.example.json"]))
assert info["niveis"] == ["senior", "especialista", "lider"], info["niveis"]
assert "junior" in info["niveis_recusados"] and "senior" not in info["niveis_recusados"], info
assert info["experiencia_max_anos"] is None, info
PYEOF
relata $? "perfil senior/tech lead: aceita senior/especialista/lider, sem teto"

# 4 — area nao-tech pula os sites so-tech; sites_pular explicito sobrepoe.
python3 - "$TMPD" <<'PYEOF'
import json, subprocess, sys
from pathlib import Path
def info(p):
    return json.loads(subprocess.check_output([sys.executable, "bot/perfil_render.py", "info", p]))
assert sorted(info("config/perfis/estagio-direito.example.json")["sites_pular"]) == ["geekhunter", "programathor"]
p = Path(sys.argv[1]) / "override.json"
p.write_text(json.dumps({"nome_perfil": "o", "niveis": ["pleno"], "area": "marketing",
                         "termos": ["x"], "pular_tipos": [], "sites_pular": ["vagas"]}))
assert info(str(p))["sites_pular"] == ["vagas"]
PYEOF
relata $? "area nao-tech pula geekhunter/programathor; sites_pular sobrepoe"

# 5 — rodizio-saude pre --perfil: proximo cai em site so-tech -> pula para o seguinte.
cp examples/aplicadas.example.json "$TMPD/aplicadas.json"
python3 - "$TMPD/aplicadas.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["rodizio"]["proximo"] = "programathor"
json.dump(d, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
PYEOF
python3 bot/rodizio-saude.py pre "$TMPD/aplicadas.json" --perfil config/perfis/estagio-direito.example.json >/dev/null 2>&1
PROX="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['rodizio']['proximo'])" "$TMPD/aplicadas.json")"
[ "$PROX" = "trampardecasa" ]
relata $? "rodizio pre --perfil pula programathor para perfil juridico (foi: $PROX)"

# 6 — sem --perfil o rodizio continua igual (compatibilidade).
cp examples/aplicadas.example.json "$TMPD/aplicadas2.json"
python3 - "$TMPD/aplicadas2.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["rodizio"]["proximo"] = "programathor"
json.dump(d, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
PYEOF
rm -f "$TMPD/rodizio_saude.json"
python3 bot/rodizio-saude.py pre "$TMPD/aplicadas2.json" >/dev/null 2>&1
PROX2="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['rodizio']['proximo'])" "$TMPD/aplicadas2.json")"
[ "$PROX2" = "programathor" ]
relata $? "rodizio pre sem --perfil nao muda o site (foi: $PROX2)"

[ "$FAIL" -eq 0 ]
