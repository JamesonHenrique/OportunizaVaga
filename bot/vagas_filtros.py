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


_AUSENTE = object()


def mesclar(base, meu, atual):
    """3-way merge of a JSON object: what THIS process changed since it read `base` wins; everything else keeps the
    current file (`atual`), so a concurrent writer's additions survive. Dicts merge key by key, recursively."""
    if not (isinstance(base, dict) and isinstance(meu, dict) and isinstance(atual, dict)):
        return meu if meu != base else atual
    out = dict(atual)
    for k in set(base) | set(meu):
        b, m = base.get(k, _AUSENTE), meu.get(k, _AUSENTE)
        if m is _AUSENTE:                                   # this process deleted k
            if k in out and out[k] == b:
                del out[k]
        elif b is _AUSENTE or m != b:                       # this process added or changed k
            a = out.get(k, _AUSENTE)
            out[k] = mesclar(b if b is not _AUSENTE else {}, m, a) if isinstance(m, dict) and isinstance(a, dict) else m
    return out


def salvar_fila(path, base, meu):
    """06/10 (audit D3): descobrir.py and tg-garimpo.py both load the queue, spend minutes on the network and save
    the whole file — the last one to save dropped the other's new jobs. Now the save takes the queue lock, re-reads
    the file and applies only this process's own changes since `base` (a deep copy taken right after loading)."""
    import jsonlock   # bot/jsonlock.py (same lock estado.py uses for aplicadas.json)
    path = str(path)
    with jsonlock.travado(path):
        save_json(path, mesclar(base, meu, load_json(path, {})))


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
            nome = perfil_render.carregar(perfil_file).get("nome_perfil", "perfil")
            slug = re.sub(r"[^a-z0-9]+", "-", str(nome).lower()).strip("-")[:48] or "perfil"
            state_dir = str(BOT_DIR / "state" / slug)
        else:
            state_dir = str(BOT_DIR)
    aplicadas = os.environ.get("APLICADAS_FILE") or os.path.join(state_dir, "aplicadas.json")
    return {"perfil_file": perfil_file, "state_dir": state_dir, "aplicadas": aplicadas}


def descoberta_config(paths):
    """Raw optional tuning (descoberta.json): $OV_DESCOBERTA_CONFIG, state dir, then bot/. {} when absent."""
    for cand in (os.environ.get("OV_DESCOBERTA_CONFIG"),
                 os.path.join(paths["state_dir"], "descoberta.json"),
                 str(BOT_DIR / "descoberta.json")):
        if cand and os.path.exists(cand):
            return load_json(cand, {})
    return {}


def perfil_resolvido(perfil_file):
    """perfil_render.resolver() of the active profile (defaults when there is none)."""
    # strict: a corrupt profile stops here instead of becoming the junior/remote defaults
    return perfil_render.resolver(perfil_render.carregar(perfil_file))


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
