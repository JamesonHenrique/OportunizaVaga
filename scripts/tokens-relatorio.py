#!/usr/bin/env python3
"""Token usage per unattended job, read-only from the opencode SQLite database.

  tokens-relatorio.py [DAYS=1]

Groups assistant messages by session title (the loop names sessions "candidaturas-YYYY-MM-DD-HHMM",
followups likewise), so you see which job burns the most context. Path of the database:
$OPENCODE_DB, else ~/.local/share/opencode/opencode.db. The schema is opencode's own (tables
session/message); if a future opencode version changes it, the script says so and exits 1.
"""
import collections
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path


def main(argv):
    days = float(argv[1]) if len(argv) > 1 else 1
    db = os.environ.get("OPENCODE_DB") or str(Path.home() / ".local" / "share" / "opencode" / "opencode.db")
    if not os.path.exists(db):
        print(f"banco do opencode nao encontrado: {db} (defina OPENCODE_DB)")
        return 1
    c = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    since = int((time.time() - days * 86400) * 1000)
    try:
        titles = dict(c.execute("select id,title from session"))
        rows = c.execute("select session_id,data from message where time_created>?", (since,))
        agg = collections.defaultdict(lambda: [0, 0, 0, set()])  # context, output, calls, sessions
        for sid, d in rows:
            j = json.loads(d)
            if j.get("role") != "assistant" or not j.get("tokens"):
                continue
            t = j["tokens"]
            g = agg[re.sub(r"-\d{4}-\d\d-\d\d.*", "", titles.get(sid, "?"))[:30]]
            g[0] += t.get("input", 0) + (t.get("cache") or {}).get("read", 0)
            g[1] += t.get("output", 0) + t.get("reasoning", 0)
            g[2] += 1
            g[3].add(sid)
    except sqlite3.Error as e:
        print(f"esquema inesperado no banco do opencode ({e}); versao nova?")
        return 1
    print(f"ultimos {days:g} dia(s) — job | sessoes | chamadas | contexto | ctx/chamada | output")
    for k, (ctx, out, n, s) in sorted(agg.items(), key=lambda x: -x[1][0])[:10]:
        print(f"{k} | {len(s)} | {n} | {ctx/1e6:.1f}M | {ctx/max(n, 1)/1e3:.0f}k | {out/1e3:.0f}k")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
