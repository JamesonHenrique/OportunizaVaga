"""HTTP-only (no browser) job-listing collectors for Brazilian job boards.

Why this exists: the application robot used to have an LLM browse these boards in Chrome, which burned most of
its tokens on navigation. These collectors read the same public listings with plain HTTP so the LLM only has
to apply. Same contract as descobrir.py: every parser returns dicts
  {"id": "<fonte>:<stable id>", "fonte", "url" (absolute), "titulo", "empresa", "local" ("remoto" or the
   location text), "publicada" ("YYYY-MM-DD" or None), "_descricao" (optional, free text for scoring)}.

Layout: for each board a pure `parse_<name>(text)` (unit-tested offline against tests/fixtures/boards) and a
`fetch_<name>(termo, get)` that builds the URL(s) and calls the injected `get(url) -> str` (at most 3 requests
per call, so it stays polite). `termo` is ignored by boards without a search that works over HTTP.

Boards that need a browser are NOT in BOARDS (checked 2026-10-05; trabalhabrasil's old SSL error is gone, it
now works with a browser-like User-Agent and is included):
  - netvagas: every page ships its body encrypted/compressed inside an anti-bot script that only a JS engine
    decodes; plain HTTP returns an empty shell.
  - abler: client-side Nuxt app; its JSON API (hulk-smash.abler.com.br) answers 403 ORIGIN_NOT_ALLOWED unless
    the call comes from the candidates portal. Not spoofing that.
"""
import html
import json
import re
import unicodedata
import urllib.parse
from datetime import date, datetime, timezone

# Strips tags even when an attribute value contains ">" (InfoJobs tooltips do).
_TAG = re.compile(r"<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")
_MESES = {m: i + 1 for i, m in enumerate("jan fev mar abr mai jun jul ago set out nov dez".split())}


def _text(fragment):
    """HTML fragment -> single-line plain text."""
    fragment = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", fragment or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def _slug(term):
    """'Desenvolvedor Júnior' -> 'desenvolvedor-junior'."""
    s = unicodedata.normalize("NFKD", term or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _item(fonte, jid, url, titulo, empresa="", local="", publicada=None, descricao=""):
    out = {"id": f"{fonte}:{jid}", "fonte": fonte, "url": url, "titulo": titulo.strip(),
           "empresa": (empresa or "").strip(), "local": (local or "").strip(), "publicada": publicada}
    if descricao and descricao.strip():
        out["_descricao"] = descricao.strip()
    return out


def _rsc_text(page):
    """Concatenated Next.js flight payload (self.__next_f.push strings) of a server-rendered page."""
    parts = []
    for raw in re.findall(r'self\.__next_f\.push\(\[1,(".*?")\]\)</script>', page, re.S):
        try:
            parts.append(json.loads(raw))
        except ValueError:
            continue
    return "".join(parts)


def _flight_ref(flight, value):
    """Long strings in a flight payload are sent as a reference ("$1e") to a later row "1e:T<hexlen>,<text>"
    (hexlen counts UTF-8 bytes). Returns the referenced text, or `value` unchanged when it is not a reference."""
    m = re.fullmatch(r"\$([0-9a-f]+)", value or "")
    if not m:
        return value
    row = re.search(r"(?m)^" + m.group(1) + r":T([0-9a-f]+),", flight)
    if not row:
        return ""
    return flight[row.end():].encode("utf-8")[: int(row.group(1), 16)].decode("utf-8", "ignore")


def _objects_after(text, marker):
    """Yield every JSON object that starts at `marker` (a prefix like '{"__typename":"PublicJob"')."""
    dec, pos = json.JSONDecoder(), 0
    while True:
        i = text.find(marker, pos)
        if i < 0:
            return
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            pos = i + len(marker)
            continue
        yield obj
        pos = end


# ---------------------------------------------------------------- eu.dev.br

def parse_eudev(page):
    """The /vagas/ page is server-rendered with ~500 rows (<tr data-job-row ...>); modality, seniority and tech
    tags are data-* attributes, so no description fetch is needed to filter."""
    def attr(chunk, name):
        m = re.search(r'(?<![\w-])' + name + r'(?![\w-])(?:=("[^"]*"|[^\s>]*))?', chunk)
        return (m.group(1) or "").strip('"') if m else ""

    out = []
    for row in re.findall(r"<tr data-job-row\b(.*?)</tr>", page, re.S):
        slug = attr(row, "data-slug")
        m_href = re.search(r"href=(/vagas/[^\s>]+)", row)
        m_t = re.search(r"<td class=title-cell>.*?<a[^>]*>(.*?)(?:<span class=muted>|<span class=mobile-meta>|</a>)", row, re.S)
        if not (slug and m_href and m_t):
            continue
        m_c = re.search(r"<td class=company-cell>.*?<a[^>]*>(.*?)</a>", row, re.S)
        m_d = re.search(r'title="Postada em (\d{4}-\d{2}-\d{2})"', row)
        mod, loc = attr(row, "data-mod"), attr(row, "data-loc").replace(" ", ", ").replace("-", " ")
        local = "remoto" if mod == "remoto" else (f"{mod} - {loc}" if loc else mod)
        desc = f"nivel: {attr(row, 'data-sen')}; tech: {attr(row, 'data-tech')}; area: {attr(row, 'data-area')}"
        out.append(_item("eu.dev.br", slug, "https://eu.dev.br" + m_href.group(1), _text(m_t.group(1)),
                         _text(m_c.group(1)) if m_c else "", local, m_d.group(1) if m_d else None, desc))
    return out


def fetch_eudev(termo, get):
    """One request returns the whole board (no pagination); the site search is client-side, so `termo` is
    ignored and the caller filters (data-sen / tech tags are in _descricao)."""
    return parse_eudev(get("https://eu.dev.br/vagas/"))


# ---------------------------------------------------------------- InfoJobs

def _infojobs_date(label, today):
    m = re.match(r"(\d{1,2}) (\w{3})", label or "")
    if not (m and m.group(2) in _MESES):
        return None
    d = date(today.year, _MESES[m.group(2)], int(m.group(1)))
    return (d.replace(year=d.year - 1) if d > today else d).isoformat()


def parse_infojobs(page, today=None):
    """Server-rendered cards (<div id="vacancyNNN">): title, company, location, modality and a description
    snippet are in the card. Date is the 'dd mmm' label, resolved against `today`."""
    today = today or date.today()
    out = []
    for card in re.split(r'(?=<div id="vacancy\d+")', page)[1:]:
        m_id = re.match(r'<div id="vacancy(\d+)"', card)
        m_href = re.search(r'href="(/vaga-[^"]+\.aspx)"', card)
        m_t = re.search(r'js_vacancyTitle">(.*?)</h2>', card, re.S)
        if not (m_id and m_href and m_t):
            continue
        m_c = re.search(r'<div class="text-body">(.*?)<div class="mb-8">', card, re.S)
        company = re.sub(r"^Empresa\s*", "", _text(m_c.group(1))) if m_c else ""
        company = re.sub(r"\s*Saiba o que isso significa.*$", "", company)
        m_l = re.search(r'<div class="mb-8">\s*([^<]+)', card)
        m_dt = re.search(r'</h2>.*?<div class="text-medium small text-nowrap">\s*([^<]+)', card, re.S)
        m_desc = re.search(r'<div class="text-medium">\s*([^<]{20,})', card)
        # modality lives in the chips row (salary / experience / education / modality), not in the description
        m_chips = re.search(r'<div class="d-inline-flex flex-wrap.*?</div>\s*</div>', card, re.S)
        remote = re.search(r"\b(Remoto|Home Office)\b", _text(m_chips.group(0)) if m_chips else "", re.I)
        local = "remoto" if remote else html.unescape(m_l.group(1)).strip() if m_l else ""
        out.append(_item("infojobs", m_id.group(1), "https://www.infojobs.com.br" + m_href.group(1), _text(m_t.group(1)),
                         company, local, _infojobs_date(m_dt.group(1).strip(), today) if m_dt else None,
                         html.unescape(m_desc.group(1)) if m_desc else ""))
    return out


def fetch_infojobs(termo, get):
    """Search page, 1 request (~16 cards). Pagination/remote filter params were not found over plain HTTP
    (page=N returned the same cards), so only the term is applied."""
    return parse_infojobs(get("https://www.infojobs.com.br/empregos.aspx?palabra=" + urllib.parse.quote_plus(termo)))


# ---------------------------------------------------------------- GeekHunter

def parse_geekhunter(page):
    """Next.js flight payload carries the Apollo cache: one PublicJob object per card (slug, title, publish
    time in ms, company slug, work modality, cities, description snippet). URL comes from the JSON-LD ItemList
    when present, else is rebuilt from company slug + job slug (same format)."""
    flight = _rsc_text(page)
    urls = {}
    for m in re.finditer(r'"url":"(https://www\.geekhunter\.com/pt/[^"/]+/jobs/([^"]+))"', page + flight):
        urls[m.group(2)] = m.group(1)
    out, seen = [], set()
    for job in _objects_after(flight, '{"__typename":"PublicJob"'):
        aj = job.get("atsJob") if isinstance(job.get("atsJob"), dict) else {}
        det = aj.get("atsJobDetail") if isinstance(aj.get("atsJobDetail"), dict) else {}
        slug = aj.get("jobSlug")
        if not (slug and det.get("title")) or slug in seen:
            continue
        seen.add(slug)
        comp = (aj.get("company") or {}).get("slug") or "" if isinstance(aj.get("company"), dict) else ""
        url = urls.get(slug) or f"https://www.geekhunter.com/pt/{comp or 'confidential'}/jobs/{slug}"
        cities = [(c.get("city") or {}).get("name") or c.get("name") for c in det.get("atsJobCities") or []]
        modality = det.get("workModality")
        local = "remoto" if modality == "remote" else ", ".join(c for c in cities if c)
        try:
            pub = datetime.fromtimestamp(int(aj["publishedAt"]) / 1000, timezone.utc).strftime("%Y-%m-%d")
        except (KeyError, TypeError, ValueError):
            pub = None
        skills = [((s.get("atsSkill") or {}).get("name") or "") for s in det.get("atsJobSkills") or []]
        desc = f"{det.get('description') or ''} nivel: {det.get('experienceLevel')}; modalidade: {modality}; skills: {', '.join(skills)}"
        out.append(_item("geekhunter", slug, url, det["title"],
                         "" if comp == "confidential" else comp.replace("-", " "), local, pub, desc))
    return out


def fetch_geekhunter(termo, get):
    """Search page (SearchAction in the page's JSON-LD documents searchTerm/experienceLevel/workModality), 25 jobs
    per page. Try 1: term + remote + entry level. The search is a strict match (2 words + entry gave 0 live), so
    when that returns fewer than 5 jobs, try 2: first word of the term + remote only (level stays in
    _descricao). Company is only the URL slug."""
    q = {"searchTerm": termo, "experienceLevel": "entry", "workModality": "remote"}
    out = parse_geekhunter(get("https://www.geekhunter.com/pt/vagas?" + urllib.parse.urlencode(q)))
    if len(out) < 5 and termo.split():
        q = {"searchTerm": termo.split()[0], "workModality": "remote"}
        seen = {i["id"] for i in out}
        out += [i for i in parse_geekhunter(get("https://www.geekhunter.com/pt/vagas?" + urllib.parse.urlencode(q)))
                if i["id"] not in seen]
    return out


# ---------------------------------------------------------------- Remotar

def parse_remotar(text):
    """JSON from api.remotar.com.br/jobs (the endpoint the site's own search uses, no auth): description is
    full HTML, so it is returned as _descricao. Public page is /job/<id>."""
    out = []
    for j in (json.loads(text).get("data") or []):
        if not j.get("id") or not j.get("title") or j.get("expired") or j.get("active") is False:
            continue
        place = ", ".join(x for x in (j.get("city"), j.get("state")) if isinstance(x, str) and x)
        local = "remoto" if j.get("type") == "remote" else (place or j.get("type") or "")
        desc = (j.get("subtitle") or "") + " " + _text(j.get("description"))
        out.append(_item("remotar", j["id"], f"https://remotar.com.br/job/{j['id']}", j["title"],
                         (j.get("company") or {}).get("name") or j.get("companyDisplayName") or "", local,
                         (j.get("createdAt") or "")[:10] or None, desc[:6000]))
    return out


def fetch_remotar(termo, get):
    """JSON API, newest first, type=remote filter + free-text search; 2 pages x 50 = up to 100 jobs."""
    out = []
    for page in (1, 2):
        q = urllib.parse.urlencode({"limit": 50, "page": page, "type": "remote", "search": termo})
        items = parse_remotar(get("https://api.remotar.com.br/jobs?" + q))
        out += items
        if len(items) < 50:
            break
    return out


# ---------------------------------------------------------------- ProgramaThor

def parse_programathor(page):
    """Server-rendered cards (<div class="cell-list">): company, location(+modality), level, contract and tech
    tags; no date on the card."""
    out = []
    # (?=[ "]) keeps "cell-list-content" / "cell-list-content-icon" from splitting a card in pieces
    for card in re.split(r'<div class="cell-list(?=[ "])', page)[1:]:
        m = re.search(r'href="(/jobs/(\d+)-[^"]*)"', card)
        m_t = re.search(r"<h3[^>]*>(.*?)</h3>", card, re.S)
        if not (m and m_t) or re.search(r">\s*Vencida\s*<", m_t.group(1)):   # "Vencida" badge = expired
            continue
        # spans are keyed by their icon: optional ones (salary, size, relocation) come and go between cards
        by_icon = {ic: _text(v) for ic, v in re.findall(r"<span><i class='[^']*?(fa-[\w-]+)'></i>(.*?)</span>", card, re.S)}
        company, loc = by_icon.get("fa-briefcase", ""), by_icon.get("fa-map-marker-alt", "")
        level, contract = by_icon.get("fa-chart-bar", ""), by_icon.get("fa-file-alt", "")
        tags = [_text(t) for t in re.findall(r"<span class='tag-list[^']*'>(.*?)</span>", card, re.S)]
        local = "remoto" if re.search(r"\bremot[oa]\b", loc, re.I) else loc
        out.append(_item("programathor", m.group(2), "https://programathor.com.br" + m.group(1), _text(m_t.group(1)),
                         company, local, None, f"nivel: {level}; contrato: {contract}; tech: {', '.join(tags)}"))
    return out


def fetch_programathor(termo, get):
    """/jobs?remoto=true, 1 request (15 cards, ~12 live). Only page 1 is worth fetching: from page 2 on the list
    is all "Vencida" (expired), and the expertise=Júnior filter is mostly expired too (1 live of 15), so level
    is left in _descricao for the caller. The site has no free-text search, so `termo` is ignored."""
    return parse_programathor(get("https://programathor.com.br/jobs?remoto=true"))


# ---------------------------------------------------------------- Sólides

def parse_solides(page):
    """Server-rendered Next.js page: the job array sits in the flight payload right after '"count":N,"data":'.
    redirectLink is malformed (empty subdomain), so the public URL is rebuilt as /vaga/<id> (verified 200)."""
    flight = _rsc_text(page)
    m = re.search(r'"count":\d+,"data":', flight)
    if not m:
        return []
    jobs, _ = json.JSONDecoder().raw_decode(flight, m.end())
    out = []
    for j in jobs:
        j["description"] = _flight_ref(flight, j.get("description"))
        # non-numeric ids are "externa" jobs hosted on the company's own career site; their public URL could
        # not be verified (every guessed form returned 404), so they are skipped rather than emitted broken.
        if not (str(j.get("id") or "").isdigit() and j.get("title")):
            continue
        loc = ", ".join(x for x in ((j.get("city") or {}).get("name"), (j.get("state") or {}).get("code")) if x)
        remote = j.get("homeOffice") or j.get("jobType") == "remoto"   # jobType seen: presencial/hibrido/remoto
        senior = ", ".join(s.get("name", "") for s in j.get("seniority") or [])
        desc = f"{_text(j.get('description'))} nivel: {senior}; modelo: {j.get('jobType')}"
        out.append(_item("solides", j["id"], f"https://vagas.solides.com.br/vaga/{j['id']}", j["title"],
                         j.get("companyName") or "", "remoto" if remote else (f"híbrido - {loc}" if j.get("jobType") == "hibrido" else loc), (j.get("createdAt") or "")[:10] or None,
                         desc[:6000]))
    return out


def fetch_solides(termo, get):
    """Search is a path slug (/vagas/desenvolvedor-junior; '?page=N' paginates), so the term is slugified. The
    portal has no remote filter in the URL except by putting 'remoto' in the slug, which is the caller's call.
    14 jobs/page, 2 pages."""
    base = "https://vagas.solides.com.br/vagas/" + (_slug(termo) or "todas")
    out = []
    for page in (1, 2):
        items = parse_solides(get(base + (f"?page={page}" if page > 1 else "")))
        out += items
        if len(items) < 10:
            break
    return out


# ---------------------------------------------------------------- Trabalha Brasil

def parse_trabalhabrasil(page):
    """Server-rendered cards (<article class="job-card" data-job-id>): title, company, city/UF, workplace
    (Home-Office / Presencial / Híbrido), salary and contract type. No date on the card."""
    out = []
    for card in re.split(r'(?=<article class="job-card")', page)[1:]:
        m_id = re.match(r'<article class="job-card" data-job-id="(\d+)"', card)
        m_href = re.search(r'href="(/vagas-de-emprego[^"]*/\d+)"', card)
        m_t = re.search(r'<h2[^>]*class="job-title"[^>]*>(.*?)</h2>', card, re.S)
        if not (m_id and m_href and m_t):
            continue
        def pick(cls):
            m = re.search(r'class="' + cls + r'"[^>]*>(.*?)</(?:p|span|li)>\s*(?:</p>)?', card, re.S)
            return _text(m.group(1)) if m else ""
        company = _text((re.search(r'class="job-company"[^>]*>(.*?)</p>', card, re.S) or [None, ""])[1])
        loc = _text((re.search(r'class="job-location"[^>]*>(.*?)</p>', card, re.S) or [None, ""])[1])
        workplace = pick("workplace")
        local = "remoto" if re.search(r"home.?office|remot", workplace, re.I) else loc
        desc = f"modelo: {workplace}; salario: {pick('salary')}; contrato: {pick('employment-type')}"
        out.append(_item("trabalhabrasil", m_id.group(1), "https://www.trabalhabrasil.com.br" + m_href.group(1),
                         _text(m_t.group(1)), company, local, None, desc))
    return out


def fetch_trabalhabrasil(termo, get):
    """/vagas-de-emprego/<term-slug> (nationwide; ?pagina=N paginates), 15 cards/page, 2 pages. Needs a browser-like
    User-Agent (the default urllib one gets 403, so the injected `get` must send one, as descobrir.get does).
    No remote filter in the URL: remote jobs are recognised by the Home-Office badge."""
    base = "https://www.trabalhabrasil.com.br/vagas-de-emprego/" + (_slug(termo) or "desenvolvedor")
    out = []
    for page in (1, 2):
        items = parse_trabalhabrasil(get(base + (f"?pagina={page}" if page > 1 else "")))
        out += items
        if len(items) < 15:
            break
    return out


BOARDS = {
    "eu.dev.br": fetch_eudev,
    "infojobs": fetch_infojobs,
    "geekhunter": fetch_geekhunter,
    "remotar": fetch_remotar,
    "programathor": fetch_programathor,
    "solides": fetch_solides,
    "trabalhabrasil": fetch_trabalhabrasil,
}
