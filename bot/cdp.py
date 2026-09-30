#!/usr/bin/env python3
"""bot/cdp.py — minimal Chrome DevTools Protocol client for the deterministic readers (no LLM).

Opens its OWN background tab in the robot's Chrome (CDP, default http://localhost:9222, override CDP_URL), reads
text, clicks with REAL mouse events (Input.dispatchMouseEvent: some sites ignore element.click()) and closes only
its tab — the browser is shared. Callers must hold the Chrome lock (bot/chrome-lock.sh).
Needs the `websocket-client` package (pip install websocket-client).
"""
import json
import os
import urllib.request

CDP = os.environ.get("CDP_URL", "http://localhost:9222")


class Chrome:
    def __init__(self):
        import websocket
        ws = json.load(urllib.request.urlopen(CDP + "/json/version", timeout=10))["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws, timeout=30, suppress_origin=True)
        self.n = 0

    def call(self, method, params=None, sid=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if sid:
            msg["sessionId"] = sid
        self.ws.send(json.dumps(msg))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.n:
                return r.get("result", {})

    def pages(self):
        return {t["targetId"]: t for t in self.call("Target.getTargets").get("targetInfos", []) if t["type"] == "page"}

    def abrir(self, url):
        tid = self.call("Target.createTarget", {"url": url, "background": True})["targetId"]
        return tid, self.anexar(tid)

    def anexar(self, tid):
        return self.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    def fechar(self, tid):
        self.call("Target.closeTarget", {"targetId": tid})

    def js(self, sid, expr):
        return self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid).get("result", {}).get("value")

    def estado(self, sid):
        return self.js(sid, "location.href") or "", self.js(sid, "document.body ? document.body.innerText : ''") or ""

    def clicar_iframe(self, sid, trecho_src):
        """Real click in the middle of the visible iframe whose src contains trecho_src (Google GSI button)."""
        pos = self.js(sid, """(() => { const f = [...document.querySelectorAll('iframe')].find(x => (x.src||'').includes(%s)
            && x.getBoundingClientRect().width > 10); if (!f) return null; f.scrollIntoView({block: 'center'});
          const r = f.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()""" % json.dumps(trecho_src))
        if not pos:
            return False
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", {"type": t, "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1}, sid)
        return True

    def clicar(self, sid, texto):
        """Real mouse click on the smallest visible element whose text/identifier matches."""
        pos = self.js(sid, """(() => { const w = %s;
          const els = [...document.querySelectorAll('[data-identifier],button,[role=button],[role=link],a,li,div')]
            .filter(e => e.offsetParent !== null && ((e.getAttribute('data-identifier')||'') === w
                         || (e.innerText||'').trim() === w || (e.innerText||'').includes(w)));
          els.sort((a, b) => (a.innerText||'').length - (b.innerText||'').length);
          const e = els[0]; if (!e) return null; e.scrollIntoView({block: 'center'});
          const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()""" % json.dumps(texto))
        if not pos:
            return False
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", {"type": t, "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1}, sid)
        return True
