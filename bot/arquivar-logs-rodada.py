#!/usr/bin/env python3
"""Move ad-hoc round summaries (log_rodada_*, log_rodadas) out of aplicadas.json into
logs/rodadas.jsonl. The agent sometimes invents these keys; they bloat the state file that
every round must read (tokens + timeouts on free models). Idempotent; atomic write.

Usage: arquivar-logs-rodada.py [APLICADAS_FILE] [LOGS_JSONL]
  APLICADAS_FILE defaults to aplicadas.json next to this script.
  LOGS_JSONL     defaults to logs/rodadas.jsonl next to this script (bot/logs/).
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from jsonlock import gravar, travado  # noqa: E402

src = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPT_DIR / "aplicadas.json"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else SCRIPT_DIR / "logs" / "rodadas.jsonl"


def main():
    try:
        d = json.loads(src.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"arquivar-logs: json invalido, nada feito ({e})")
        return

    keys = [k for k in d if k.startswith("log_rodada")]
    # Weak models often miscount descartes_listagem.total by 1; recompute it deterministically.
    dl = d.get("descartes_listagem")
    fixed_total = False
    if isinstance(dl, dict) and all(isinstance(dl.get(k), int) for k in ("nivel", "modelo", "stack")):
        soma = dl["nivel"] + dl["modelo"] + dl["stack"]
        if dl.get("total") != soma:
            dl["total"] = soma
            fixed_total = True

    if not keys and not fixed_total:
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        for k in keys:
            fh.write(json.dumps({"arquivado_em": datetime.now().isoformat(timespec="seconds"),
                                 "chave": k, "valor": d.pop(k)}, ensure_ascii=False) + "\n")

    gravar(str(src), d)
    print(f"arquivar-logs: {len(keys)} chaves movidas para {out.name}" + (", total de descartes recalculado" if fixed_total else ""))


if __name__ == "__main__":
    with travado(str(src)):   # same exclusive lock as estado.py
        main()
