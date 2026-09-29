#!/usr/bin/env python3
"""Deterministic job-description triage: level / experience / work model / stack, from the
DESCRIPTION text and the LinkedIn official "Nivel de experiencia", before any model reasoning.
In the maintainer's private run 58% of the blocks (90 of 158) were "stack outside the profile",
found only AFTER the model opened and read the posting. This decides the obvious ones by script.

  vaga_check.py checar ARQUIVO [TITULO] [NIVEL_OFICIAL]  -> "COMPATIVEL" or "INCOMPATIVEL: motivo (evidencia)"
  (used by descobrir.py on every queue job, and by the model on the saved posting, prompt step c0)

CONSERVATIVE by design: it only rejects on clear evidence. Doubt -> COMPATIVEL (the model judges).

Everything is driven by the active profile (perfil.json) and the optional descoberta.json:
  niveis / niveis_recusados   accepted / refused levels (level words come from vagas_filtros)
  experiencia_max_anos        years ceiling; a posting whose lowest requirement is above it is out
                              (null = no ceiling). Years >= 10 are company age, never a requirement.
  modelos                     accepted work models (remoto / hibrido / presencial)
  stack_evitar                foreign-stack words: 2+ of them and NONE of stack_preferida = out
  stack_preferida             the profile stack; empty = the stack rule is off
See config/descoberta.example.json for a filled example.
"""
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vagas_filtros as vf  # noqa: E402


def _n(t):
    """Lowercase, accent-free (punctuation kept: '100%', 'c#', '.net' matter here)."""
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# Seniority stated AS the role ("desenvolvedor senior", "nivel pleno", "vaga para pleno"); only the
# unambiguous words of each refused level (the title matcher of vagas_filtros also has "ii", "iv"...).
PAPEL = r"(desenvolvedor\w*|engenheir\w*|analista|programador\w*|developer|engineer|nivel|vaga)"
PALAVRAS_PAPEL = {
    "estagio": r"estagiari[oa]|intern",
    "trainee": r"trainee",
    "junior": r"junior|jr",
    "pleno": r"pleno|pl|mid[- ]?level",
    "senior": r"senior|sr",
    "especialista": r"especialista|staff",
    "lider": r"lead",
}
# LinkedIn "Nivel de experiencia" (job criteria, pt-BR and en) -> canonical levels it may mean.
OFICIAL = {
    "estagio": {"estagio"}, "internship": {"estagio"},
    "assistente": {"junior"}, "junior": {"junior"}, "entry level": {"junior"}, "associate": {"junior"},
    "pleno-senior": {"pleno", "senior"}, "mid-senior level": {"pleno", "senior"},
    "diretor": {"diretor"}, "director": {"diretor"}, "executivo": {"diretor"}, "executive": {"diretor"},
}
ANOS = re.compile(r"(\d{1,2})\s*\+?\s*(?:anos?|years?)\s+(?:de\s+experiencia|of\s+(?:[\w-]+\s+){0,3}experience|experience|full[- ]stack|in\b)"
                  r"|experiencia\s+(?:minima\s+)?de\s+(\d{1,2})\s*\+?\s*anos?")
PRESENCIAL = re.compile(r"\b(100%\s+(presencial|on-?site)|trabalho\s+presencial|modelo\s+(de\s+trabalho\s*)?:?\s*presencial|"
                        r"regime\s+presencial|atuacao\s+presencial|work\s+model:?\s*on-?site)")
HIBRIDO = re.compile(r"\b(modelo\s+(de\s+trabalho\s*)?:?\s*hibrido|regime\s+hibrido|atuacao\s+hibrida|hibrido\s*\(\d|"
                     r"work\s+model:?\s*hybrid)")
REMOTO = re.compile(r"\b(100%\s+remot\w*|remot[oa]|remote|home\s*office|anywhere)\b")


def _lista(palavras):
    ps = [re.escape(_n(p).strip()) for p in palavras or [] if _n(p).strip()]
    return re.compile(r"(?<![a-z0-9])(" + "|".join(sorted(ps)) + r")(?![a-z0-9])") if ps else None


def configurar(info, cfg=None):
    """Compile the profile (perfil_render.resolver output) + descoberta.json tuning."""
    cfg = cfg or {}
    aceitos = list(info["niveis"])
    baixos = {"estagio", "trainee", "junior"}
    bom = [vf.NIVEL_PALAVRAS[n] for n in aceitos]
    if "junior" in aceitos:
        bom.append(r"entry[- ]level")
    fora_palavras = [PALAVRAS_PAPEL[n] for n in info["niveis_recusados"] if n in PALAVRAS_PAPEL]
    return {
        "aceitos_oficial": set(aceitos) | ({"estagio"} if baixos & set(aceitos) else set()),
        "bom": re.compile(r"\b(" + "|".join(bom) + r")\b"),
        "papel_fora": re.compile(r"\b" + PAPEL + r"(\(a\))?\s+(de\s+\w+\s+)?(" + "|".join(fora_palavras) + r")\b")
                      if fora_palavras else None,
        "estrito": set(aceitos) <= baixos,   # title without an accepted level word is a signal only for entry-level profiles
        "max_anos": info.get("experiencia_max_anos"),
        "modelos": info["modelos"],
        "stack_fora": _lista(cfg.get("stack_evitar")),
        "stack_boa": _lista(cfg.get("stack_preferida")),
    }


def avaliar(texto, titulo="", nivel_oficial=None, conf=None):
    """(True, "") when compatible or doubtful; (False, 'motivo (evidencia)') on clear evidence.
    nivel_oficial = LinkedIn "Nivel de experiencia" when known (e.g. "Pleno-senior", "Junior").
    conf = configurar(...) result; default = the active profile."""
    conf = conf or carregar_conf()
    t, ti = _n(texto), _n(titulo)
    of = _n(nivel_oficial).strip() if nivel_oficial else ""
    titulo_bom = bool(conf["bom"].search(ti))
    # The OFFICIAL level beats the title ("Junior Java Developer" listed as Pleno-senior is out), and
    # for entry-level profiles a title without a level word needs a compatible official level.
    canon = OFICIAL.get(of)
    if of and canon is not None and not (canon & conf["aceitos_oficial"]):
        return False, f"nivel oficial LinkedIn: {nivel_oficial}"
    if of and canon is None and conf["estrito"] and not titulo_bom:
        return False, f"titulo sem nivel aceito e nivel oficial '{nivel_oficial}'"
    aceito = titulo_bom or bool(canon and canon & conf["aceitos_oficial"]) or bool(conf["bom"].search(t[:600]))
    m = conf["papel_fora"].search(t) if conf["papel_fora"] else None
    if m and not aceito:
        return False, f"nivel ({m.group(0)[:40]})"
    teto = conf["max_anos"]
    anos = [n for n in (int(x.group(1) or x.group(2)) for x in ANOS.finditer(t) if (x.group(1) or x.group(2))) if n < 10]   # >=10 is company age
    if teto is not None and anos and min(anos) > teto:
        return False, f"experiencia ({min(anos)}+ anos exigidos, teto do perfil {teto})"
    modelos = conf["modelos"]
    escape = "remoto" in modelos and REMOTO.search(t)
    for nome, rx in (("presencial", PRESENCIAL), ("hibrido", HIBRIDO)):
        m = rx.search(t)
        if m and nome not in modelos and not escape:
            return False, f"modelo ({m.group(0)[:40]})"
    if conf["stack_fora"] and conf["stack_boa"]:   # both lists empty/one empty = rule off
        fora = {x.group(0) for x in conf["stack_fora"].finditer(t)}
        boa = {x.group(0) for x in conf["stack_boa"].finditer(t)}
        if len(fora) >= 2 and not boa:
            return False, f"stack ({', '.join(sorted(fora))[:60]}; nada do perfil)"
    return True, ""


def carregar_conf():
    """Active profile + descoberta.json, the same lookup as descobrir.py."""
    paths = vf.resolve_paths()
    return configurar(vf.perfil_resolvido(paths["perfil_file"]), vf.descoberta_config(paths))


def main(argv):
    if len(argv) >= 2 and argv[0] == "checar":
        try:
            with open(argv[1], encoding="utf-8", errors="ignore") as fh:
                texto = fh.read()
        except OSError as e:
            print(f"erro: {e}")
            return 2
        ok, motivo = avaliar(texto, argv[2] if len(argv) > 2 else "", argv[3] if len(argv) > 3 else None)
        print("COMPATIVEL" if ok else f"INCOMPATIVEL: {motivo}")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
