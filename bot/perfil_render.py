#!/usr/bin/env python3
"""Profile-driven placeholders for the agent prompts (any seniority, any area).

The prompts (bot/prompt_loop*.md, bot/prompt_triage.md) no longer hardcode "junior + tech":
they carry {{PLACEHOLDERS}} that are filled from the active profile (perfil.json).
Deterministic, stdlib only, no LLM.

  perfil_render.py render  PERFIL IN OUT [--lang pt|en]   fill placeholders of IN into OUT
  perfil_render.py info    PERFIL                         print the resolved profile as JSON
  perfil_render.py pular-sites PERFIL                     print rotation site ids to skip (one per line)

Profile fields (see config/perfil.schema.json):
  niveis               list of accepted levels (preferred); legacy "nivel" (string) still works
  area                 free text ("tecnologia", "jurídico", "marketing"...); default "tecnologia"
  termos               search terms
  pular_tipos          job types to skip on the listing
  experiencia_max_anos max years a posting may require (null = no ceiling); default by level
  sites_pular          rotation site ids to skip (overrides the automatic area filter)
"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES_FILE = ROOT / "config" / "sites_permitidos.json"

# Canonical order = seniority ladder. Labels include the synonyms seen on job titles.
NIVEIS = {
    "estagio": {"pt": "estágio/estagiário", "en": "internship/intern"},
    "trainee": {"pt": "trainee", "en": "trainee"},
    "junior": {"pt": "júnior/JR/entry-level", "en": "junior/JR/entry-level"},
    "pleno": {"pt": "pleno/PL/mid-level", "en": "mid-level/pleno/PL"},
    "senior": {"pt": "sênior/SR", "en": "senior/SR"},
    "especialista": {"pt": "especialista/staff/principal/arquiteto", "en": "specialist/staff/principal/architect"},
    "lider": {"pt": "tech lead/líder/coordenador/supervisor", "en": "tech lead/lead/coordinator/supervisor"},
    "gestor": {"pt": "gerente/head/manager", "en": "manager/head"},
    "diretor": {"pt": "diretor/VP/C-level", "en": "director/VP/C-level"},
}
ORDEM = list(NIVEIS)
ALIASES = {
    "estágio": "estagio", "estagiario": "estagio", "estagiário": "estagio", "intern": "estagio",
    "júnior": "junior", "jr": "junior", "entry-level": "junior",
    "mid": "pleno", "mid-level": "pleno", "pl": "pleno",
    "sênior": "senior", "sr": "senior",
    "staff": "especialista", "principal": "especialista", "arquiteto": "especialista",
    "tech lead": "lider", "tech-lead": "lider", "líder": "lider", "lead": "lider", "coordenador": "lider",
    "gerente": "gestor", "manager": "gestor", "head": "gestor",
    "vp": "diretor", "c-level": "diretor",
}
# Default ceiling of required experience, by the HIGHEST accepted level (None = no ceiling).
EXPERIENCIA_PADRAO = {"estagio": 1, "trainee": 1, "junior": 3, "pleno": 6}
TECH_HINTS = ("tech", "tecnolog", "ti", "t.i", "it", "software", "desenvolv", "dev", "programa",
              "dados", "data", "qa", "infra", "devops", "seguranca da informacao", "rpa")


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def nivel_canonico(valor):
    v = str(valor).strip().lower()
    if v in NIVEIS:
        return v
    if v in ALIASES:
        return ALIASES[v]
    v = _norm(v)
    if v in NIVEIS:
        return v
    return ALIASES.get(v)


def niveis_do_perfil(perfil):
    brutos = perfil.get("niveis")
    if not brutos:
        legado = perfil.get("nivel")
        brutos = [legado] if legado else ["junior"]
        # Legacy behavior: a "junior" profile also accepted trainee.
        if nivel_canonico(legado or "junior") == "junior":
            brutos.append("trainee")
    if isinstance(brutos, str):
        brutos = [brutos]
    vistos = {n for n in (nivel_canonico(b) for b in brutos) if n}
    return [n for n in ORDEM if n in vistos] or ["junior", "trainee"]


def area_do_perfil(perfil):
    return str(perfil.get("area") or "tecnologia").strip()


def area_eh_tech(area):
    a = _norm(area)
    palavras = set(a.replace("/", " ").replace(",", " ").split())
    return any(h in palavras or (len(h) > 3 and h in a) for h in TECH_HINTS)


def experiencia_max(perfil, niveis):
    if "experiencia_max_anos" in perfil:
        v = perfil["experiencia_max_anos"]
        return int(v) if isinstance(v, (int, float)) and v >= 0 else None
    return EXPERIENCIA_PADRAO.get(niveis[-1])


def sites_restritos():
    """Rotation site id -> required area, from config/sites_permitidos.json (key "restrito_a_area")."""
    try:
        doc = json.loads(SITES_FILE.read_text(encoding="utf-8"))
        return {k: v for k, v in doc.get("restrito_a_area", {}).items() if not k.startswith("_")}
    except Exception:
        return {}


def pular_sites(perfil):
    if isinstance(perfil.get("sites_pular"), list):
        return [str(s) for s in perfil["sites_pular"]]
    tech = area_eh_tech(area_do_perfil(perfil))
    return [site for site, area in sites_restritos().items() if area == "tech" and not tech]


def resolver(perfil):
    niveis = niveis_do_perfil(perfil)
    return {
        "nome_perfil": perfil.get("nome_perfil", "default"),
        "niveis": niveis,
        "niveis_recusados": [n for n in ORDEM if n not in niveis],
        "area": area_do_perfil(perfil),
        "area_tech": area_eh_tech(area_do_perfil(perfil)),
        "termos": [t for t in perfil.get("termos", []) if isinstance(t, str) and t.strip()],
        "pular_tipos": [t for t in perfil.get("pular_tipos", []) if isinstance(t, str) and t.strip()],
        "experiencia_max_anos": experiencia_max(perfil, niveis),
        "sites_pular": pular_sites(perfil),
    }


def _lista(itens, vazio):
    return ", ".join(itens) if itens else vazio


def placeholders(info, lang="pt"):
    en = lang == "en"
    rotulo = lambda n: NIVEIS[n]["en" if en else "pt"]
    exp = info["experiencia_max_anos"]
    if exp is None:
        regra_exp = ("no ceiling on required years: apply whenever skills and level match"
                     if en else "sem teto de anos pedidos: aplique sempre que competências e nível casarem")
    else:
        regra_exp = (f"up to {exp} year(s) required → APPLY; {exp + 1}+ years → DISCARD"
                     if en else f"vaga que pede no MÁXIMO {exp} ano(s) → APLIQUE; {exp + 1}+ anos → DESCARTE")
    nenhum = "(none)" if en else "(nenhum)"
    return {
        "{{NIVEIS}}": " | ".join(rotulo(n) for n in info["niveis"]),
        "{{NIVEIS_RECUSADOS}}": _lista([rotulo(n) for n in info["niveis_recusados"]], nenhum),
        "{{AREA}}": info["area"],
        "{{TERMOS}}": _lista([f'"{t}"' for t in info["termos"]], nenhum),
        "{{TERMO_PRINCIPAL}}": info["termos"][0] if info["termos"] else "",
        "{{PULAR_TIPOS}}": _lista(info["pular_tipos"], nenhum),
        "{{REGRA_EXPERIENCIA}}": regra_exp,
        "{{SITES_PULAR}}": _lista(info["sites_pular"], nenhum),
    }


def render(texto, perfil, lang="pt"):
    for chave, valor in placeholders(resolver(perfil), lang).items():
        texto = texto.replace(chave, valor)
    return texto


def carregar(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception:
        return {}


def main(argv):
    if len(argv) >= 2 and argv[0] == "info":
        print(json.dumps(resolver(carregar(argv[1])), ensure_ascii=False))
        return 0
    if len(argv) >= 2 and argv[0] == "pular-sites":
        print("\n".join(resolver(carregar(argv[1]))["sites_pular"]))
        return 0
    if len(argv) >= 4 and argv[0] == "render":
        lang = argv[argv.index("--lang") + 1] if "--lang" in argv else "pt"
        texto = Path(argv[2]).read_text(encoding="utf-8")
        Path(argv[3]).write_text(render(texto, carregar(argv[1]), lang), encoding="utf-8")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
