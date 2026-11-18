#!/usr/bin/env python3
"""Cross-portal job dedup: one identity (company + title) per posting, whatever board it came from.

Pure functions, no I/O. Level words are KEPT in the title key by default (descobrir.py measured that merging
"Java Junior" with "Java Pleno" of one company drops a real job); pass manter_nivel=False to drop them.
`local` is NOT part of the key used by deduplicar_vagas: portals format it too differently.
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vagas_filtros as vf  # noqa: E402

PRIORIDADE_FONTE = {"gupy": 3, "remotar": 2, "linkedin": 1}   # unknown = 0; ties keep the first seen

_STOP_TITULO = {
    "a", "o", "as", "os", "e", "de", "da", "do", "das", "dos", "em", "na", "no", "para", "com", "por",
    "ou", "the", "of", "and", "for", "in", "to", "vaga", "vagas", "pessoa", "desenvolvedor",
    "desenvolvedora", "developer", "dev", "remoto", "remota", "remote", "home", "office", "hibrido",
    "hibrida", "presencial", "100", "nivel", "level", "oportunidade", "afirmativa"
}
_NIVEL = {
    "junior": "junior", "jr": "junior", "pleno": "pleno", "pl": "pleno", "senior": "senior", "sr": "senior",
    "estagio": "estagio", "estagiario": "estagio", "estagiaria": "estagio", "intern": "estagio",
    "internship": "estagio", "trainee": "trainee", "aprendiz": "trainee"
}
_JUNTAR = [(re.compile(rf"\b{a}\s+{b}\b"), a + b) for a, b in (("back", "end"), ("front", "end"), ("full", "stack"))]
_SUFIXO_EMPRESA = re.compile(r"(?:\s+(?:ltda|sa|s a|eireli|me|epp|inc|llc|ltd|corp|co))+$")   # only at the END


def normalizar_titulo(titulo: str, manter_nivel: bool = True) -> str:
    t = vf.norm(titulo).replace("-", " ")
    for rx, junto in _JUNTAR:
        t = rx.sub(junto, t)
    tokens = set()
    for tok in t.split():
        tok = tok.strip(".")   # "Jr." -> "jr"; "node.js", "c#", "c++" survive
        if not tok or tok in _STOP_TITULO:
            continue
        if tok in _NIVEL:
            if not manter_nivel:
                continue
            tok = _NIVEL[tok]
        tokens.add(tok)
    return " ".join(sorted(tokens))   # order-insensitive across portals


def normalizar_empresa(empresa: str) -> str:
    e = re.sub(r"\s+", " ", vf.norm(empresa).replace(".", "")).strip()
    return _SUFIXO_EMPRESA.sub("", e).strip()


def _hash_chave(emp_norm: str, tit_norm: str, local_norm: str = "") -> str:
    chave = f"{emp_norm}|{tit_norm}|{local_norm}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:12]


def gerar_hash_vaga(empresa: str, titulo: str, local: str = "") -> str:
    return _hash_chave(normalizar_empresa(empresa), normalizar_titulo(titulo), vf.norm(local))


def _prioridade(v):
    return PRIORIDADE_FONTE.get(str(v.get("fonte") or "").lower(), 0)


def deduplicar_vagas(vagas: list[dict]) -> list[dict]:
    """Best source wins (gupy > remotar > linkedin > others; ties: first seen), shallow-copied, with
    fontes_alternativas=[{fonte,id,url}]. No company / empty title -> never merged. Input not mutated."""
    grupos, saida = {}, []
    for v in vagas:
        emp, tit = normalizar_empresa(v.get("empresa")), normalizar_titulo(v.get("titulo"))
        if not emp or not tit:
            saida.append(("solo", v))
            continue
        k = _hash_chave(emp, tit)
        if k not in grupos:
            grupos[k] = []
            saida.append(("grupo", k))
        grupos[k].append(v)
    out = []
    for tipo, x in saida:
        if tipo == "solo" or len(grupos[x]) == 1:
            out.append(x if tipo == "solo" else grupos[x][0])
            continue
        melhor = max(grupos[x], key=_prioridade)   # max keeps the first on ties
        alt = list(melhor.get("fontes_alternativas") or [])
        for m in grupos[x]:
            if m is not melhor:
                alt.append({"fonte": m.get("fonte"), "id": m.get("id"), "url": m.get("url")})
                alt.extend(m.get("fontes_alternativas") or [])
        out.append({**melhor, "fontes_alternativas": alt})
    return out
