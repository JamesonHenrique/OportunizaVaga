#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o CV em PDF sempre a partir de cv_base.md (currículo mestre).

Uso:
    python3 gerar_cv.py <cv_spec.json> <saida.pdf>

O spec (escrito pelo agente da rodada) só pode REORDENAR e REESCREVER o resumo.
Todo conteúdo factual vem de cv_base.md + dados_candidato.json; keywords fora do
perfil sao filtradas e reportadas no stdout.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE_MD = os.path.join(AQUI, "cv_base.md")
DADOS_JSON = os.path.join(AQUI, "dados_candidato.json")

COR_TITULO = colors.HexColor("#0b3d5c")
COR_TEXTO = colors.HexColor("#1c1c1c")
COR_CINZA = colors.HexColor("#555555")

STOPWORDS_KW = (
    "conhecimento em", "conhecimento de", "experiencia com", "experiência com",
    "dominio em", "dominio de", "familiaridade com", "desejavel:", "desejavel",
    "diferencial:", "diferencial", "bonus:", "obrigatorio:", "essencial:",
    "sólido em", "solido em", "notions de", "noções de", "básico em", "basico em",
)

GENERICOS_PERMITIDOS = [
    "remoto", "clt", "pj", "júnior", "junior", "trainee", "pleno", "fullstack",
    "full stack", "backend", "front end", "frontend", "api", "apis", "rest",
    "rest api", "api rest", "apis rest", "restful", "crud", "http", "ci/cd",
    "pipeline", "versionamento", "gitflow", "banco de dados",
    "integração de sistemas", "integrações", "automação", "automação de processos",
    "webhook", "webhooks", "testes automatizados", "boa comunicação",
    "trabalho em equipe", "proatividade",
]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().lower()


def esc(s):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


# ---------------------------------------------------------------- parser base
def parse_base(path):
    meta, sections = [], {}
    titulo, sub, atual = None, None, None
    em_comentario = False
    for bruta in open(path, encoding="utf-8"):
        linha = bruta.rstrip("\n")
        # comentarios HTML do proprio cv_base.md (ex.: exemplos/instrucoes) nunca vao p/ o PDF
        if em_comentario:
            if "-->" in linha:
                em_comentario = False
            continue
        if linha.strip().startswith("<!--"):
            if "-->" not in linha:
                em_comentario = True
            continue
        if linha.startswith("# "):
            titulo = linha[2:].strip()
            continue
        if linha.startswith("## "):
            sub, atual = None, linha[3:].strip()
            sections[atual] = []
            continue
        if linha.startswith("### "):
            sub = linha[4:].strip()
            sections[atual].append({"sub": sub, "lines": []})
            continue
        if not linha.strip():
            continue
        if atual is None:
            meta.append(linha.strip())
            continue
        if sections[atual] is None or not sections[atual]:
            sections[atual].append({"sub": sub, "lines": []})
        sections[atual][-1]["lines"].append(linha.strip())
    return titulo, meta, sections


def blocos_de(sections, nome):
    for bloco in sections.get(nome, []):
        yield bloco


# ------------------------------------------------------------- texto que nunca vai p/ o CV
# 09/10: 31 de 48 CVs enviados levaram notas internas ao recrutador ("disponivel para atuar, sem afirmar dominio",
# "Termos do anuncio correspondidos neste perfil: React JR (similar ...)"). A frase de transferencia e para
# FORMULARIO (estado.py dado respostas_padrao_gupy); no CV a skill similar aparece so na secao "Stacks adjacentes".
PROIBIDO_NO_CV = re.compile(r"sem afirmar|similar|termos do an[uú]ncio|dispon[ií]vel para atuar,|transfer[ií]vel para",
                            re.I)


def limpar_rotulo(p):
    """'React JR (similar Angular/TypeScript — ...)' -> 'React' (the label is for the model, the name for the CV)."""
    p = re.sub(r"\s*\(.*$", "", str(p)).strip()
    return re.sub(r"\s+(JR|b[aá]sico)$", "", p, flags=re.I).strip() or str(p)


# Titulo-alvo (linha logo abaixo do nome): espelha o cargo da vaga, o fator que o ATS mais pesa. So entra se for um
# cargo que o candidato de fato exerce/pleiteia; nivel so Junior/Trainee/Estagio (regra 3 do prompt).
CARGO_OK = re.compile(r"^(pessoa )?(desenvolvedor[a]?|developer|engenheir[oa] de software|software engineer|analista de "
                      r"(sistemas|desenvolvimento|automa[cç][aã]o|integra[cç][aã]o)|programador[a]?)\b", re.I)
NIVEL_OK = re.compile(r"\b(j[uú]nior|jr\.?|trainee|est[aá]gi[oa]|estagi[aá]ri[oa])\b", re.I)
NIVEL_FORA = re.compile(r"\b(pleno|s[eê]nior|sr\.?|senior|staff|especialista|l[ií]der|lead|ii|iii)\b", re.I)


def titulo_valido(t):
    t = re.sub(r"\s+", " ", str(t or "")).strip(" -|·")
    if not t or len(t) > 90 or not CARGO_OK.search(t) or NIVEL_FORA.search(t) or PROIBIDO_NO_CV.search(t):
        return None
    return t


# ------------------------------------------------------------- allowlist kw
def _partes_kw(txt):
    txt = txt[2:] if txt.startswith(("- ", "* ")) else txt
    txt = re.sub(r"^Tecnologias:\s*", "", txt)
    return [p.strip(" .") for p in re.split(r"\s*[|;·]\s*", txt) if len(norm(p)) >= 3]


def carregar_allowlist(dados, sections=None):
    partes = list(dados.get("experiencia", {}).get("tecnologias", []))
    partes += list(dados.get("experiencia", {}).get("stacks_similares_jr", []) or [])
    partes += list(dados.get("experiencia", {}).get("stacks_similares", []) or [])
    partes += [p for p in str(dados.get("palavras_chave_ats", "")).split(",") if p.strip()]
    partes += GENERICOS_PERMITIDOS
    # skills declaradas no proprio cv_base.md tambem sao veredictas (fonte do candidato)
    for nome, blocos in (sections or {}).items():
        for b in blocos:
            for ln in b["lines"]:
                if norm(nome) in ("habilidades tecnicas", "competencias") or \
                        ln.startswith("Tecnologias:"):
                    partes += _partes_kw(ln)
    allow = {}
    for p in partes:
        p = p.strip()
        if not p:
            continue
        allow.setdefault(norm(p), limpar_rotulo(p))
        for pedaco in re.split(r"[/,;(]| \+ ", p):
            pedaco = pedaco.strip(" .")
            if len(norm(pedaco)) >= 3:
                allow.setdefault(norm(pedaco), pedaco.strip())
    return allow


# Skills-column budget: the Habilidades section only fits 14 lines even at the 4th font size (estilos
# falls back 10.0 -> 9.5 -> 9.0 -> 8.8). Not a data limit; a page limit.
MAX_KW = 14


def filtrar_kw(brutas, allow):
    mantidas, descartadas = [], []
    for kw in (brutas or []):
        k = str(kw).strip(" .;,-")
        if len(k) < 2:
            continue
        n = norm(k)
        for stop in STOPWORDS_KW:
            if n.startswith(stop):
                n = n[len(stop):].strip(" :-")
        if not n:
            continue
        alvo = allow.get(n)
        if not alvo:
            for chave in sorted(allow, key=len, reverse=True):
                if len(chave) >= 4 and (chave in n or (len(n) >= 4 and n in chave)):
                    alvo = allow[chave]
                    break
        if alvo and norm(alvo) not in [norm(m) for m in mantidas]:
            mantidas.append(alvo)
        else:
            descartadas.append(kw)
    # 04/10 (cap 121 E2): the 14 was a magic number and the truncation was SILENT — a real spec asked for
    # 18, got 14, and nobody could tell that 4 keywords never made it into the CV. It is a page-fit
    # budget (the skills column only fits 14 lines even at the smallest font, see the loop in estilos()),
    # so the cap stays; what changes is that it is named and that the cut is reported to stderr, which
    # is where the model and the human both look when a CV comes out "missing something".
    if len(mantidas) > MAX_KW:
        print(f"gerar_cv: {len(mantidas) - MAX_KW} keyword(s) fora do orcamento de {MAX_KW} "
              f"e NAO entraram no CV: {', '.join(mantidas[MAX_KW:])}", file=sys.stderr)
    return mantidas[:MAX_KW], descartadas


# ------------------------------------------------------------------ estilos
def estilos(corpo_pt=10.0):
    return {
        "nome": ParagraphStyle("nome", fontName="Helvetica-Bold", fontSize=16,
                               leading=18, textColor=COR_TEXTO, spaceAfter=0),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5,
                               leading=10.5, textColor=COR_CINZA, spaceAfter=0.5),
        "cargo": ParagraphStyle("cargo", fontName="Helvetica-Bold", fontSize=10,
                                leading=12, textColor=COR_TITULO, spaceBefore=2,
                                spaceAfter=1),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5,
                             leading=11.5, textColor=COR_TITULO, spaceBefore=3,
                             spaceAfter=1),
        "corpo": ParagraphStyle("corpo", fontName="Helvetica", fontSize=corpo_pt,
                                leading=corpo_pt + 2, textColor=COR_TEXTO, spaceAfter=1.2),
        "item": ParagraphStyle("item", fontName="Helvetica", fontSize=corpo_pt,
                               leading=corpo_pt + 2, textColor=COR_TEXTO, leftIndent=10,
                               bulletIndent=1, spaceAfter=1.2),
        "sub": ParagraphStyle("sub", fontName="Helvetica-Bold", fontSize=9,
                              leading=11.5, textColor=COR_TEXTO, spaceBefore=1,
                              spaceAfter=0.5),
        "nota": ParagraphStyle("nota", fontName="Helvetica-Oblique", fontSize=8.8,
                               leading=11.5, textColor=COR_CINZA, spaceAfter=1.5),
        "kw": ParagraphStyle("kw", fontName="Helvetica", fontSize=8.5,
                             leading=10.8, textColor=COR_TEXTO, backColor=colors.HexColor("#eef3f7"),
                             borderPadding=3, spaceAfter=2),
    }


def h2(titulo, S, flow):
    flow.append(Paragraph(esc(titulo), S["h2"]))
    flow.append(HRFlowable(width="100%", thickness=0.7, color=COR_TITULO,
                           spaceBefore=0, spaceAfter=2.5))


def linha_secao(bloco, S, flow, kwset=None, com_sub=True):
    if com_sub and bloco.get("sub"):
        flow.append(Paragraph(esc(bloco["sub"]), S["sub"]))
    for ln in bloco["lines"]:
        if ln.startswith(("- ", "* ")) and not (ln.startswith("*") and ln.endswith("*") and not ln.startswith("* ")):
            flow.append(Paragraph(esc(ln[2:]), S["item"], bulletText="•"))
        elif ln.startswith("*") and ln.endswith("*") and len(ln) > 2:
            flow.append(Paragraph(esc(ln.strip("*")), S["nota"]))
        else:
            flow.append(Paragraph(esc(ln), S["corpo"]))


def render_competencias(bloco, S, flow, ordem, kwset):
    nome = bloco.get("sub") or ""
    destaque = kwset or set()
    for ln in bloco["lines"]:
        txt = ln[2:] if ln.startswith(("- ", "* ")) else ln
        partes = [p.strip() for p in re.split(r"\s*\|\s*", txt) if p.strip()]
        out = []
        for p in partes:
            base = re.sub(r"^Disponível para atuar em nível júnior:\s*", "", p)
            if norm(base) in destaque or any(norm(base) in k or k in norm(base)
                                             for k in destaque if len(k) >= 4):
                out.append("<b>%s</b>" % esc(p))
            else:
                out.append(esc(p))
        sep = " &nbsp;|&nbsp; " if len(partes) > 1 else ""
        flow.append(Paragraph(sep.join(out) if len(partes) > 1 else out[0], S["corpo"]))


def _pdf_paginas(path):
    """Numero de paginas via pdfinfo; fallback pypdf; None se nada funcionar."""
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True,
                             timeout=30)
        m = re.search(r"^Pages:\s+(\d+)", out.stdout, re.M)
        if m:
            return int(m.group(1))
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        from pypdf import PdfReader
        return len(PdfReader(path).pages)
    except Exception:
        return None


def _extrair_texto(path):
    """Texto do PDF: pdftotext; fallback pypdf. None se nada funcionar."""
    try:
        out = subprocess.run(["pdftotext", path, "-"], capture_output=True,
                             text=True, timeout=30)
        if out.stdout.strip():
            return out.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    except Exception:
        return None


def _checar_texto(path, titulo, sections):
    """Extrai o texto do PDF e confere nome + secoes na ordem. Devolve problemas."""
    txt = _extrair_texto(path)
    if not txt:
        print("aviso: sem extrator de texto (pdftotext/pypdf); auto-checagem pulada")
        return []
    probs = []
    m = PROIBIDO_NO_CV.search(txt)
    if m:
        probs.append("nota interna no texto do CV: '%s'" % m.group(0))
    linhas = [norm(l) for l in txt.splitlines() if norm(l)]
    primeiro = norm(titulo).split(" ")[0]
    if not any(primeiro in l for l in linhas[:3]):
        probs.append("nome nao encontrado no texto extraido do PDF")
    idx = -1
    for nome in sections:
        alvo = norm(nome)
        # headings sao linhas proprias no texto extraido (evita falso positivo
        # de "Experiencia" dentro do resumo)
        i = next((j for j, l in enumerate(linhas) if l == alvo), None)
        if i is None:
            probs.append("secao ausente no texto: %s" % nome)
        elif i < idx:
            probs.append("secao fora de ordem: %s" % nome)
        else:
            idx = i
    return probs


def gerar(spec_path, saida):
    spec = json.load(open(spec_path, encoding="utf-8"))
    dados = json.load(open(DADOS_JSON, encoding="utf-8"))
    titulo, meta, sections = parse_base(BASE_MD)

    allow = carregar_allowlist(dados, sections)
    kw_ok, kw_caiu = filtrar_kw(spec.get("palavras_chave_vaga"), allow)
    kwset = {norm(k) for k in kw_ok}

    # 09/10: frase de transferencia NAO entra no CV (era nota interna impressa p/ o recrutador; ver PROIBIDO_NO_CV)
    alvo = titulo_valido(spec.get("titulo_alvo"))
    if spec.get("titulo_alvo") and not alvo:
        print("aviso: titulo_alvo recusado (cargo/nivel fora do perfil): %s — mantido o titulo do cv_base"
              % spec.get("titulo_alvo"), file=sys.stderr)

    resumo = (spec.get("resumo_custom") or "").strip()
    if PROIBIDO_NO_CV.search(resumo):
        print("ERRO: resumo_custom tem nota interna (%s): o CV vai ao recrutador. Reescreva so com fatos do perfil."
              % PROIBIDO_NO_CV.search(resumo).group(0), file=sys.stderr)
        sys.exit(2)
    if len(resumo) > 800:
        resumo = resumo[:800].rsplit(" ", 1)[0] + "…"
    if not resumo:
        chave_resumo = next((n for n in sections if norm(n) == "resumo"), None)
        resumo = " ".join(b["lines"][0] for b in sections.get(chave_resumo, []) if b["lines"])

    # so_categorias: OBRIGATORIO — mostra SOMENTE as subsecoes listadas (3-7),
    # mantendo o corpo em 10pt legivel em vez de um muro de skills irrelevantes.
    so_raw = [str(o) for o in (spec.get("so_categorias") or []) if str(o).strip()]
    if not so_raw:
        print("ERRO: spec sem \"so_categorias\" — informe 3-7 subsecoes de "
              "\"Habilidades tecnicas\" para mostrar (as demais ficam ocultas).",
              file=sys.stderr)
        sys.exit(2)
    key_hab = next((n for n in sections if norm(n) == "habilidades tecnicas"), None)
    blocos_hab = sections.get(key_hab, []) if key_hab else []
    subs_conhecidas = {norm(b.get("sub") or "") for b in blocos_hab}
    so = [norm(o) for o in so_raw]
    desconhecidas = [o for o, n in zip(so_raw, so) if n not in subs_conhecidas]
    if desconhecidas:
        print("aviso: so_categorias com nome(s) nao existente(s): "
              + ", ".join(desconhecidas), file=sys.stderr)
    if not any(n in subs_conhecidas for n in so):
        print("ERRO: nenhuma so_categorias bate com as subsecoes de "
              "cv_base.md. Validas: " + ", ".join(
                  b.get("sub") or "" for b in blocos_hab),
              file=sys.stderr)
        sys.exit(2)
    ordem = [norm(o) for o in
             (spec.get("categorias_ordem") or spec.get("so_categorias") or [])]

    nome_resumo = next((n for n in sections if norm(n) == "resumo"), "Resumo")

    def montar(corpo_pt):
        S = estilos(corpo_pt)
        flow = []
        flow.append(Paragraph(esc(titulo), S["nome"]))
        for i, m in enumerate(meta):
            if i == 0 and alvo:   # headline: target title + the base stack line after the "|"
                m = alvo + (" | " + m.split("|", 1)[1].strip() if "|" in m else "")
            flow.append(Paragraph(esc(m), S["cargo"] if i == 0 else S["meta"]))
        flow.append(HRFlowable(width="100%", thickness=1.1, color=COR_TITULO,
                               spaceBefore=4, spaceAfter=6))

        h2(nome_resumo, S, flow)   # 09/10: ATS finds the summary by its heading; it had none
        flow.append(Paragraph(esc(resumo), S["corpo"]))

        pos = {n: i for i, n in enumerate(ordem)}
        for nome, blocos in sections.items():
            if norm(nome) == "resumo":
                continue
            h2(nome, S, flow)
            if norm(nome) in ("habilidades tecnicas", "competencias"):
                classificados = [(i, norm(b.get("sub") or ""), b)
                                 for i, b in enumerate(blocos)]
                if so:
                    classificados = [t for t in classificados if t[1] in so]
                classificados.sort(key=lambda t: (pos.get(t[1], 1000), t[0]))
                for _, _, b in classificados:
                    if b.get("sub"):
                        flow.append(Paragraph(esc(b["sub"]), S["sub"]))
                    render_competencias(b, S, flow, ordem, kwset)
            else:
                for b in blocos:
                    linha_secao(b, S, flow, kwset)
        return flow

    # 10pt (faixa legivel p/ ATS/leitor humano); se estourar 1 pagina, cai ate
    # 8.8pt; se mesmo assim estourar, falha alto pedindo so_categorias.
    for tam in (10.0, 9.5, 9.0, 8.8):
        doc = SimpleDocTemplate(saida, pagesize=A4, leftMargin=1.5 * cm,
                                rightMargin=1.5 * cm, topMargin=1.1 * cm,
                                bottomMargin=1.0 * cm, title=titulo, author=titulo,
                                subject=alvo or (meta[0] if meta else ""), keywords=", ".join(kw_ok))
        doc.build(montar(tam))
        pag = _pdf_paginas(saida)
        if pag is None:
            print("aviso: pdfinfo indisponivel; nao foi possivel confirmar 1 pagina")
            break
        if pag == 1:
            print("1 pagina (corpo %.0fpt)" % tam)
            break
    else:
        print("ERRO: PDF ficou com mais de 1 pagina mesmo em 8.8pt. Reduza para "
              "3-5 subsecoes usando o campo so_categorias do spec e rode de novo.",
              file=sys.stderr)
        sys.exit(1)

    probs = _checar_texto(saida, titulo, sections)
    if probs:
        print("ERRO: auto-checagem do PDF reprovou: " + "; ".join(probs),
              file=sys.stderr)
        sys.exit(1)

    print("gerado %s" % saida)
    if kw_ok:
        print("kw no CV: " + ", ".join(kw_ok))
    if kw_caiu:
        print("kw DESCARTADAS (fora do perfil): " + ", ".join(map(str, kw_caiu)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    gerar(sys.argv[1], sys.argv[2])
