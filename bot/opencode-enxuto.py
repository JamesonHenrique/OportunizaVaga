#!/usr/bin/env python3
"""Prints a LEAN OPENCODE_CONFIG_CONTENT (JSON) for the unattended robots (loop, follow-up).

Every opencode call ships the schemas of all enabled MCP tools and built-in tools. The robots use one
browser MCP and a handful of built-ins, so the rest is pure token cost on EVERY call (about 9 per session).
Measured in the maintainer's PRIVATE setup (their own MCP set, same model, one-line prompt, first-call
context): 15,346 tokens of system + tool schemas with the old config vs 11,051 with this one, i.e. -28%
per call. That is a private measurement; yours depends on which MCPs you have configured.

What it does (merged by opencode over your own config, so nothing else changes):
  - every OTHER MCP found in your opencode config is disabled ({"enabled": false}; no URL/header is copied);
  - the browser MCP ($OV_BROWSER_MCP, default "playwright-chrome-real") is kept with its command read from
    your config MINUS the "vision" capability (`--caps vision`: the coordinate tools were never called in
    the maintainer's logged rounds, but their schemas shipped with every request);
  - built-in tools the robots never used are denied: edit, glob, grep, websearch, task, todowrite, plus the
    browser tools never used in a week of rounds (PW_NEGAR: close, screenshot, drag, hover, resize, ...; measured
    -2,145 tokens per call) (override with OV_ENXUTO_NEGAR="a,b,c"). write and webfetch stay: models use them.
    The agent can still grep/edit through bash; this only removes the dedicated tools' schemas.

Usage: python3 bot/opencode-enxuto.py   -> JSON on stdout, or NOTHING when off/unavailable (fail-open:
the caller then keeps its own config, e.g. $OV_OPENCODE_CONFIG_CONTENT).
Opt-in: OV_OPENCODE_ENXUTO=1 (off by default in the public repo: it denies built-in tools). Config file: $OV_OPENCODE_USER_CONFIG, $OPENCODE_CONFIG, or
~/.config/opencode/opencode.jsonc|json.
"""
import json
import os
import re
import sys

NEGAR = ["edit", "glob", "grep", "websearch", "task", "todowrite"]
# Browser MCP tools never used in a week of real rounds (network_requests: few calls, ~10 KB output each).
# Measured (same model, one-line prompt, first call): 11,191 -> 9,046 tokens with these denied.
PW_NEGAR = ["close", "take_screenshot", "emulate_media", "drop", "network_request", "network_requests",
            "drag", "hover", "resize", "navigate_back", "console_messages"]
_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
_VIRGULA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')


def carregar_jsonc(raw):
    """JSON with comments / trailing commas (opencode.jsonc). String-aware: '//' inside a URL survives."""
    sem = _TOKEN.sub(lambda m: m.group(0) if m.group(0)[0] == '"' else "", raw)
    sem = _VIRGULA.sub(lambda m: m.group(0) if m.group(0)[0] == '"' else "", sem)
    return json.loads(sem)


def caminho_config():
    for c in (os.environ.get("OV_OPENCODE_USER_CONFIG"), os.environ.get("OPENCODE_CONFIG"),
              os.path.join(os.path.expanduser("~"), ".config", "opencode", "opencode.jsonc"),
              os.path.join(os.path.expanduser("~"), ".config", "opencode", "opencode.json")):
        if c and os.path.isfile(c):
            return c
    raise FileNotFoundError("opencode config not found")


def sem_visao(cmd):
    """Drop the vision capability from an MCP command (`--caps vision` or `--caps=vision`; others are kept)."""
    out, i = [], 0
    while i < len(cmd):
        a = cmd[i]
        if a == "--caps" and i + 1 < len(cmd):
            caps = [c for c in str(cmd[i + 1]).split(",") if c.strip() and c.strip() != "vision"]
            if caps:
                out += [a, ",".join(caps)]
            i += 2
            continue
        if a.startswith("--caps="):
            caps = [c for c in a[7:].split(",") if c.strip() and c.strip() != "vision"]
            if caps:
                out.append("--caps=" + ",".join(caps))
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def enxuto(user_cfg, navegador):
    mcps = user_cfg.get("mcp") or {}
    bloco = mcps.get(navegador)
    cmd = bloco.get("command") if isinstance(bloco, dict) else None
    if not (isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd)):
        raise KeyError(f"MCP '{navegador}' with a command list not found in the opencode config")
    negar = [t.strip() for t in os.environ["OV_ENXUTO_NEGAR"].split(",") if t.strip()] \
        if os.environ.get("OV_ENXUTO_NEGAR") else NEGAR + [f"{navegador}_browser_{t}" for t in PW_NEGAR]
    cfg = {"mcp": {nome: {"enabled": False} for nome in mcps if nome != navegador},
           "permission": {"*": "allow", "skill": "deny"}}
    cfg["mcp"][navegador] = {"type": "local", "command": sem_visao(cmd), "enabled": True}
    cfg["permission"].update({t: "deny" for t in negar})
    return cfg


def opencode_v2():
    """True when the opencode the robot runs is major 2 (`opencode v2.0.31`; V1 prints a bare `1.19.3`).
    OV_OPENCODE_MAJOR overrides the probe (tests, or forcing a shape by hand)."""
    m = os.environ.get("OV_OPENCODE_MAJOR")
    if m:
        return m.strip() == "2"
    import subprocess
    binario = os.environ.get("OPENCODE_BIN") or os.path.join(os.path.expanduser("~"), ".opencode", "bin", "opencode")
    try:
        v = subprocess.run([binario, "--version"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return False
    m = re.search(r"(\d+)\.\d+\.\d+", v or "")
    return bool(m) and m.group(1) == "2"


def v2(cfg, user_cfg):
    """The same lean config in opencode 2's native shape (issue #21). V2 still reads the V1 shape, but two things
    only exist natively:
      - `codemode: false`: by default V2 hides MCP tools behind one `execute` tool that runs JS, while the prompt
        assumes direct browser_* tools; `execute` and `question` are also denied (nobody answers a robot);
      - `edit` covers write/patch in V2, so denying it like V1 would also block write: writes go to /tmp only.
    A disabled server needs its full definition plus `disabled: true` (a bare {"disabled": true} is rejected as
    malformed and the server keeps connecting). Rules: the last one that matches wins, as in V1."""
    mcps = user_cfg.get("mcp") or {}
    servers = {}
    for nome, s in cfg["mcp"].items():
        if s.get("enabled") is False:
            base = {k: v for k, v in (mcps.get(nome) or {}).items() if k in ("type", "url", "command")}
            servers[nome] = (base or {"type": "remote", "url": "http://127.0.0.1:9/"}) | {"disabled": True}
        else:
            servers[nome] = {k: v for k, v in s.items() if k != "enabled"} | {"codemode": False}
    regra = lambda a, r, e: {"action": a, "resource": r, "effect": e}  # noqa: E731
    acao = {"task": "subagent", "bash": "shell"}
    perms = [regra("*", "*", "allow")]
    perms += [regra(acao.get(t, t), "*", e) for t, e in cfg["permission"].items() if t not in ("*", "edit")]
    perms += [regra("edit", "*", "deny"), regra("edit", "/tmp/*", "allow"), regra("edit", "/tmp/*/../*", "deny"),
              regra("execute", "*", "deny"), regra("question", "*", "deny")]
    return {"mcp": {"servers": servers}, "permissions": perms}


def main():
    if os.environ.get("OV_OPENCODE_ENXUTO", "0") != "1":   # opt-in in the public repo (denies tools)
        return 0
    try:
        with open(caminho_config(), encoding="utf-8") as fh:
            user = carregar_jsonc(fh.read())
        cfg = enxuto(user, os.environ.get("OV_BROWSER_MCP") or "playwright-chrome-real")
        print(json.dumps(v2(cfg, user) if opencode_v2() else cfg, ensure_ascii=False))
    except Exception as e:   # fail-open: print nothing, the robot keeps its current config
        print(f"opencode-enxuto: {type(e).__name__}: {e}; config enxuta nao aplicada", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
