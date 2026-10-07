"""bot/cdp.py: the tab comes to front before any click (06/10: a hidden tab ignored Gupy's "Google" button)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import cdp  # noqa: E402


def _chrome():
    ch = cdp.Chrome.__new__(cdp.Chrome)   # no websocket: call/js are faked
    ch.chamadas = []
    ch.call = lambda metodo, params=None, sid=None: ch.chamadas.append(metodo) or {}
    ch.js = lambda sid, expr: {"x": 10, "y": 20}
    return ch


def test_clicar_traz_a_aba_para_frente_antes():
    ch = _chrome()
    assert ch.clicar("S", "Google")
    assert ch.chamadas == ["Page.bringToFront"] + ["Input.dispatchMouseEvent"] * 3, ch.chamadas


def test_clicar_iframe_traz_a_aba_para_frente_antes():
    ch = _chrome()
    assert ch.clicar_iframe("S", "accounts.google.com/gsi/button")
    assert ch.chamadas[0] == "Page.bringToFront", ch.chamadas


def test_frente_nunca_quebra_o_clique():
    ch = _chrome()

    def falha(metodo, params=None, sid=None):
        if metodo == "Page.bringToFront":
            raise RuntimeError("sem suporte")
        ch.chamadas.append(metodo)
        return {}
    ch.call = falha
    assert ch.clicar("S", "Google") and ch.chamadas == ["Input.dispatchMouseEvent"] * 3


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
    print("ok test_cdp")
