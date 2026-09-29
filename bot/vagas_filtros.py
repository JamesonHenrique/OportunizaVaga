#!/usr/bin/env python3
"""Shared helpers for the deterministic discovery scripts (descobrir.py, tg-garimpo.py).

No LLM, stdlib only, cross-platform. Everything is driven by the active profile
(perfil.json, see config/perfil.schema.json): accepted levels, refused levels, search
terms, job types to skip and work models. Nothing here is specific to one person or area.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
ROOT = BOT_DIR.parent
sys.path.insert(0, str(BOT_DIR))
import perfil_render  # noqa: E402  (profile resolution shared with the prompts)

# Words that reveal each canonical level in a TITLE (already accent-stripped, lowercase).
NIVEL_PALAVRAS = {
    "estagio": r"estagi\w*|intern|internship",
    "trainee": r"trainee|aprendiz",
    "junior": r"junior|jr|entry|associate",
    "pleno": r"pleno|pl|ii|mid[- ]?level",
    "senior": r"senior|sr|iii|iv",
    "especialista": r"especialista|staff|principal|arquitet[oa]",
    "lider": r"lead|lider|tech ?lead|coordenador|supervisor",
    "gestor": r"gerente|head|manager",
    "diretor": r"diretor|vp|director",
}


def norm(text):
    """Lowercase, accent-free, punctuation collapsed to single spaces."""
    t = unicodedata.normalize("NFKD", str(text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9#+.]+", " ", t)).strip()


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_json(path, data):
    """Atomic write (tmp + replace) so a crash never leaves half a file."""
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def resolve_paths():
    """Profile, state dir and aplicadas.json, following the same rules as bot/loop.sh.

    The loop exports STATE_DIR / APLICADAS_FILE / BOT_PERFIL; when a script runs standalone
    (cron) the same location is recomputed from the profile name.
    """
    perfil_file = os.environ.get("BOT_PERFIL") or ""
    if not perfil_file and (BOT_DIR / "perfil.json").exists():
        perfil_file = str(BOT_DIR / "perfil.json")
    state_dir = os.environ.get("STATE_DIR") or ""
    if not state_dir:
        if perfil_file and os.path.exists(perfil_file):
            nome = load_json(perfil_file, {}).get("nome_perfil", "perfil")
            slug = re.sub(r"[^a-z0-9]+", "-", str(nome).lower()).strip("-")[:48] or "perfil"
            state_dir = str(BOT_DIR / "state" / slug)
        else:
            state_dir = str(BOT_DIR)
    aplicadas = os.environ.get("APLICADAS_FILE") or os.path.join(state_dir, "aplicadas.json")
    return {"perfil_file": perfil_file, "state_dir": state_dir, "aplicadas": aplicadas}


def perfil_resolvido(perfil_file):
    """perfil_render.resolver() of the active profile (defaults when there is none)."""
    doc = load_json(perfil_file, {}) if perfil_file else {}
    return perfil_render.resolver(doc)


def _alt(niveis):
    parts = [NIVEL_PALAVRAS[n] for n in niveis if n in NIVEL_PALAVRAS]
    return re.compile(r"\b(" + "|".join(parts) + r")\b") if parts else None


def regex_niveis(info):
    """(accepted, refused) compiled regexes over normalized titles; either may be None."""
    return _alt(info["niveis"]), _alt(info["niveis_recusados"])


def nivel_ok(titulo, bom, fora):
    """False only when the title shows a refused level and no accepted one (ambiguous passes)."""
    t = norm(titulo)
    if fora and fora.search(t) and not (bom and bom.search(t)):
        return False
    return True


def regex_tipos(pular_tipos):
    """Regex over normalized titles for the profile's pular_tipos (free-text phrases)."""
    termos = set()
    for item in pular_tipos or []:
        base = re.sub(r"\([^)]*\)", " ", str(item))
        base = re.sub(r"(?i)fora do perfil", " ", base)
        for parte in base.split("/"):
            n = norm(parte)
            if len(n) >= 2:
                termos.add(re.escape(n))
    if not termos:
        return None
    return re.compile(r"(?<![a-z0-9])(" + "|".join(sorted(termos)) + r")(?![a-z0-9])")


def regex_lista(palavras):
    """Regex over normalized text for a plain list of words/phrases (None when empty)."""
    ps = [re.escape(norm(p)) for p in palavras or [] if norm(p)]
    if not ps:
        return None
    return re.compile(r"(?<![a-z0-9])(" + "|".join(ps) + r")(?![a-z0-9])")
