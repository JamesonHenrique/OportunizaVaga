"""Facts in the free-text CV summary (resumo_custom) must exist in the candidate's own sources.

gerar_cv.py already filters keywords through an allowlist and refuses internal notes, but resumo_custom was free
text: the model could write "5 anos de experiência", "reduzi 40% do tempo" or "Kubernetes" with no trace of it in
cv_base.md / dados_candidato.json, and the PDF went to the recruiter with an invented claim (10/10).

nao_comprovados(resumo, fontes, allow) -> list of claims to remove. Two deterministic checks, no model:
- numbers: every number written in the summary (years, %, counts) must appear as a number in the sources;
- technologies: every term of the technical vocabulary must be in the allowlist or in the sources.
It cannot tell a true sentence from a false one built only from real words — that stays the prompt's job.
"""
import re
import unicodedata

from check_ats import TECH_VOCAB

# "2 anos", "+3 anos", "40%", "10 mil", "3x": a number next to a unit is a factual claim
_NUMERO = re.compile(r"(?<![\w.,])\+?(\d+(?:[.,]\d+)?)\s*(%|x\b|anos?\b|years?\b|meses\b|months?\b|mil\b|k\b|"
                     r"pessoas\b|clientes\b|usuarios\b|users\b|projetos\b|projects\b)?", re.I)
# Ordinals/levels that are not claims ("Java 17", "Python 3") are accepted when the version is in the sources too.


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().lower()


def _numeros(texto):
    return {m.group(1).replace(",", ".") for m in _NUMERO.finditer(texto)}


def nao_comprovados(resumo, fontes, allow=()):
    """Claims of `resumo` with no support in `fontes` (cv_base.md + dados_candidato.json as text)."""
    r, f = _norm(resumo), _norm(fontes)
    faltam = []
    base_nums = _numeros(f)
    for m in _NUMERO.finditer(r):
        n = m.group(1).replace(",", ".")
        if n not in base_nums:
            faltam.append(m.group(0).strip())
    permitidos = {_norm(a) for a in allow}
    palavras_fonte = set(re.findall(r"[a-z0-9+#./-]+", f))
    for termo in sorted(TECH_VOCAB):
        if re.search(r"(?<![a-z0-9+#])" + re.escape(termo) + r"(?![a-z0-9+#])", r) \
                and termo not in permitidos and termo not in palavras_fonte:
            faltam.append(termo)
    vistos = []
    for x in faltam:
        if x not in vistos:
            vistos.append(x)
    return vistos
