#!/usr/bin/env python3
"""Offline tests for bot/fontes_boards.py: each parser runs against a trimmed real response saved in
tests/fixtures/boards. Run: python3 tests/test_fontes_boards.py"""
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bot"))
import fontes_boards as fb  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "boards")
CASES = [("eu.dev.br", "eudev", "html"), ("infojobs", "infojobs", "html"), ("geekhunter", "geekhunter", "html"),
         ("remotar", "remotar", "json"), ("programathor", "programathor", "html"), ("solides", "solides", "html"), ("trabalhabrasil", "trabalhabrasil", "html")]


def load(name, ext):
    with open(os.path.join(FIX, f"{name}.{ext}"), encoding="utf-8") as f:
        return f.read()


def check_items(fonte, items):
    assert len(items) >= 1, f"{fonte}: parser returned no items"
    ids = set()
    for it in items:
        for k in ("id", "url", "titulo"):
            assert it.get(k), f"{fonte}: empty {k} in {it}"
        assert it["url"].startswith("https://"), f"{fonte}: relative url {it['url']}"
        assert it["id"].startswith(fonte + ":") and it["fonte"] == fonte, f"{fonte}: bad id/fonte {it}"
        assert it["publicada"] is None or len(it["publicada"]) == 10, f"{fonte}: bad date {it['publicada']}"
        assert isinstance(it["empresa"], str) and isinstance(it["local"], str)
        assert not any("<" in it[k] or "&#x" in it[k] for k in ("titulo", "empresa", "local")), f"{fonte}: markup leak {it}"
        ids.add(it["id"])
    assert len(ids) == len(items), f"{fonte}: duplicate ids"


def main():
    for fonte, name, ext in CASES:
        parse = getattr(fb, "parse_" + name)
        items = parse(load(name, ext))
        check_items(fonte, items)
        print(f"ok parse_{name}: {len(items)} items, e.g. {items[0]['titulo']!r}")
    # board-specific behaviour worth pinning
    assert any(i["local"] == "remoto" for i in fb.parse_infojobs(load("infojobs", "html"))), "infojobs remote not detected"
    assert fb.parse_infojobs(load("infojobs", "html"), today=date(2026, 10, 5))[0]["publicada"] == "2026-09-16"
    assert all(i["publicada"] for i in fb.parse_solides(load("solides", "html"))), "solides date missing"
    assert all(i["_descricao"] for i in fb.parse_solides(load("solides", "html"))), "solides flight ref not resolved"
    assert any(i["local"] == "remoto" for i in fb.parse_trabalhabrasil(load("trabalhabrasil", "html"))), "tb remote"
    assert not any("Vencida" in i["titulo"] for i in fb.parse_programathor(load("programathor", "html"))), "expired kept"
    # fetch_* wiring with an injected get(): urls, term handling, request budget
    calls = []
    fixtures = {n: load(n, e) for _, n, e in CASES}

    def fake_get(url):
        calls.append(url)
        for key, name in (("eu.dev.br", "eudev"), ("infojobs", "infojobs"), ("geekhunter", "geekhunter"),
                          ("remotar", "remotar"), ("programathor", "programathor"), ("solides", "solides"), ("trabalhabrasil", "trabalhabrasil")):
            if key in url:
                return fixtures[name]
        raise AssertionError(url)

    for fonte, fetch in fb.BOARDS.items():
        calls.clear()
        items = fetch("desenvolvedor junior", fake_get)
        assert items and len(calls) <= 3, f"{fonte}: {len(calls)} requests"
        check_items(fonte, items)
    assert fb._slug("Desenvolvedor Júnior") == "desenvolvedor-junior"
    print("ok fetch_* wiring; all tests passed")


if __name__ == "__main__":
    main()
