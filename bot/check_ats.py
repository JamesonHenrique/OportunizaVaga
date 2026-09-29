#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede a cobertura do CV pelos termos tecnicos do anuncio (sanidade ATS).

Uso:
    python3 check_ats.py <anuncio.txt> <cv.pdf>

- Extrai o texto do PDF com pdftotext (mesma visao de um ATS que faz parsing).
- Extrai os termos tecnicos do anuncio (fora da lista de palavras genericas).
- Imprime % de cobertura e o que FALTA, separando:
    * no perfil    -> da pra colocar no CV (acao do agente)
    * fora do perfil -> nao da pra inventar (sinal de desalinhamento da vaga)
- Exit 0 se a cobertura dos termos do perfil for >= 75%; senao exit 1 (acao).

NUNCA use texto invisivel/branco para "encher" keyword — ATS moderno (Workday,
Greenhouse) detecta e sinaliza fraude.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS_JSON = os.path.join(AQUI, "dados_candidato.json")

COBERTURA_MINIMA = 75

STOPWORDS = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por para pelo pela
com sem sobre entre ate apos ante contra desde perante e ou mas que se como
quando onde qual quais quem cujo porque pois mais menos muito muitos muitas
pouco poucas todo toda todos todas outro outra outros outras mesmo mesma
este esta estes estas esse essa esses essas aquele aquela isto isso aquilo
ser estar ter haver fazer ficar poder dever precisar querer dizer terem
vaga vagas candidato candidatos empresa empresas grupo area areas cargo cargos
requisito requisitos obrigatorio obrigatoria obrigatorios obrigatorias
desejavel diferencial diferenciais bonus plus excelente otima otimo boa bom
experiencia experiencia anos ano vez dia dias mes meses equipe time trabalhar
trabalho atuar atuacao atuacao desenvolvimento desenvolvedor dev analista
programador estagio trainee júnior junior pleno senior senioridade
remoto remota hibrido presencial modelo modalidade beneficios beneficio
salario remuneracao contratacao processo seletivo selecionar candidatura
inscricao prazo adicionais desejamos buscamos procuramos precisamos
nivel níveis niveis conhecimento conhecimentos habilidade habilidades
ingles espanhol portugues idioma idiomas formacao formado formada curso
superior tecnologico faculdade universidade
conhecimento familiaridade dominio dominio nocoes noções basico básico
diferencial obrigatorio: desejavel: diferencial: bonus: essencial:
vamos nosso nossa seus suas ele ela eles elas
day force transmission nubank picpay ifood totvs ciandt
oferecemos oportunidade posicao posicoes descricao descricaoismo
""".split())

# vocabulario tecnico comum (mesmo fora do perfil) p/ sinalizar desalinhamento
TECH_VOCAB = set("""
python java javascript typescript angular react vue next nuxt nodejs node
spring springboot boot security mvc rest soap graphql grpc websocket
kafka rabbitmq activemq redis memcached mongodb postgres postgresql mysql
sqlite oracle sqlserver dynamodb elasticsearch opensearch
docker kubernetes openshift terraform ansible jenkins github gitlab bitbucket
aws azure gcp cloudflare linux windows unix bash powershell
php ruby rails go golang rust kotlin swift scala dart
html css sass tailwind bootstrap material angularjs jquery
jwt oauth2 sso saml keycloak okta
unittest junit mockito pytest jest cypress selenium
agile scrum kanban jira notion
rpa uipath automation anywhere blueprism power automate zapier make n8n
gemini openai gpt llm ia inteligencia
microservicos microsservicos mensageria eventdriven soa mvc etl elt
ci/cd devops sre
""".split())


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().lower()


def _allowlist_perfil():
    try:
        dados = json.load(open(DADOS_JSON, encoding="utf-8"))
    except OSError:
        return {}
    partes = list(dados.get("experiencia", {}).get("tecnologias", []))
    partes += list(dados.get("experiencia", {}).get("stacks_similares_jr", []) or [])
    partes += list(dados.get("experiencia", {}).get("stacks_similares", []) or [])
    partes += [p for p in str(dados.get("palavras_chave_ats", "")).split(",") if p.strip()]
    allow = set()
    for p in partes:
        p = p.strip()
        if not p:
            continue
        allow.add(norm(p))
        for pedaco in re.split(r"[/,;(]| \+ ", p):
            if len(norm(pedaco)) >= 3:
                allow.add(norm(pedaco))
    return allow


def _texto_pdf(path):
    txt = None
    try:
        out = subprocess.run(["pdftotext", path, "-"], capture_output=True,
                             text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            txt = out.stdout
    except (OSError, subprocess.TimeoutExpired):
        txt = None
    if not txt:  # fallback pypdf (mesma base instalada p/ gerar_cv)
        try:
            from pypdf import PdfReader
            txt = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
        except Exception:
            sys.exit("ERRO: sem extrator de texto (pdftotext/pypdf) — "
                     "nao da para avaliar o CV.")
    if not txt.strip():
        sys.exit("ERRO: nao extraiu texto de %s (PDF invalido?)." % path)
    return txt


def termos_tecnicos(texto, allow):
    """Tokens tecnicos do anuncio: no perfil, no vocabulario tecnico, ou
    claramente tecnico (digito/simbolo/caixa mista). Genericos caem fora."""
    vistos, ordem = set(), []
    for m in re.finditer(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9+#./_-]*", texto):
        orig = m.group(0).strip("._-")
        if len(orig) < 3:
            continue
        n = norm(orig)
        if n in STOPWORDS or n in vistos:
            continue
        tecnico = (n in allow or n in TECH_VOCAB
                   or re.search(r"[0-9+#./]", orig)
                   or any(c.isupper() for c in orig[1:]))
        if not tecnico:
            continue
        vistos.add(n)
        ordem.append((n, orig))
    return ordem


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    anuncio_path, cv_path = argv[1], argv[2]
    for p in (anuncio_path, cv_path):
        if not os.path.exists(p):
            sys.exit("ERRO: arquivo nao encontrado: %s" % p)

    allow = _allowlist_perfil()
    texto_cv = norm(_texto_pdf(cv_path))
    texto_an = open(anuncio_path, encoding="utf-8", errors="replace").read()

    termos = termos_tecnicos(texto_an, allow)
    if not termos:
        print("Nenhum termo tecnico encontrado no anuncio — confira o arquivo.")
        return 1

    no_perfil, fora_perfil = [], []
    for n, orig in termos:
        (no_perfil if n in allow else fora_perfil).append((n, orig))

    presentes = [(n, o) for n, o in termos if n in texto_cv]
    faltando_perfil = [(n, o) for n, o in no_perfil if n not in texto_cv]
    faltando_fora = [(n, o) for n, o in fora_perfil if n not in texto_cv]

    cob_geral = round(100.0 * len(presentes) / len(termos))
    cob_perfil = (round(100.0 * (len(no_perfil) - len(faltando_perfil))
                        / len(no_perfil)) if no_perfil else None)

    print("termos tecnicos no anuncio: %d (perfil: %d | fora do perfil: %d)"
          % (len(termos), len(no_perfil), len(fora_perfil)))
    print("cobertura geral do CV: %d%%" % cob_geral)
    if cob_perfil is not None:
        print("cobertura dos termos DO PERFIL: %d%%" % cob_perfil)
    if faltando_perfil:
        print("FALTA no CV (exista no perfil — coloque no resumo/kw do spec): "
              + ", ".join(o for _, o in faltando_perfil))
    if faltando_fora:
        print("fora do perfil (NAO invente; sinal de desalinhamento da vaga): "
              + ", ".join(o for _, o in faltando_fora))

    if cob_perfil is not None and cob_perfil < COBERTURA_MINIMA:
        print("REPROVADO: cobertura do perfil < %d%% — ajuste o spec e gere de novo."
              % COBERTURA_MINIMA)
        return 1
    print("OK: cobertura suficiente para anexar.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
