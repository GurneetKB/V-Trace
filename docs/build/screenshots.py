"""Capture app screenshots for the report and deck by driving headless Edge (Chrome DevTools protocol).

Needs the app running (streamlit run app.py) and the demo cameras processed. Signs in with the account in
.streamlit/secrets.toml, describes the demo vehicle (docs/DEMO_GUIDE.md), selects it and captures each step into
docs/screenshots/.

    python docs/build/screenshots.py [http://localhost:8501] [dark|light]
"""
import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501/"
THEME = sys.argv[2] if len(sys.argv) > 2 else "dark"
OUT = ROOT / "docs" / "screenshots"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ADMIN = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text())["admin"]
# Demo scenario (docs/DEMO_GUIDE.md): the red Citroen seen in camA, camB and camC.
QUERY_TIME = "00:42.00"                                   # camB_centre#156, the red Citroen
DEMO = {"colour": "red", "type": "suv"}
PORT = 9350


class Page:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def cmd(self, method, **params):
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    async def js(self, expr):
        r = await self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    async def wait_text(self, text, secs=120):
        for _ in range(secs * 2):
            if await self.js(f"document.body && document.body.innerText.includes({json.dumps(text)})"):
                await asyncio.sleep(1.5)
                return True
            await asyncio.sleep(0.5)
        raise TimeoutError(text)

    async def click_xy(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            await self.cmd("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)

    async def click(self, selector_js):
        """selector_js: JS expression returning an element; scrolls it into view and clicks its centre."""
        for _ in range(20):                        # the page may still be (re)rendering
            r = await self.js(f"""(() => {{ const e = {selector_js}; if (!e) return null;
                e.scrollIntoView({{block: 'center'}}); const b = e.getBoundingClientRect();
                return [b.x + b.width / 2, b.y + b.height / 2]; }})()""")
            if r:
                break
            await asyncio.sleep(0.5)
        if not r:
            html = await self.js("(() => { const l = [...document.querySelectorAll('label')].find(e => e.innerText.includes('Colour'));"
                                 " return l ? l.closest('[data-testid]').outerHTML.slice(0, 1500) : 'no label'; })()")
            await self.shot("_debug_failed_click.png")
            raise LookupError(f"{selector_js}\n--- DOM near 'Colour':\n{html}")
        await asyncio.sleep(0.4)
        await self.click_xy(*r)
        await asyncio.sleep(0.8)

    async def type(self, text):
        await self.cmd("Input.insertText", text=text)

    async def shot(self, name, scroll_to=None):
        await self.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=1430, y=890)   # no hover tooltips
        if scroll_to:
            await self.js(f"(() => {{ const e = {scroll_to}; e && e.scrollIntoView({{block: 'start'}}); }})()")
            await asyncio.sleep(1.0)
        r = await self.cmd("Page.captureScreenshot", format="png")
        (OUT / name).write_bytes(base64.b64decode(r["data"]))
        print("saved", OUT / name)


def button_in_column(label, text):
    """The button labelled `label` in the column that also shows `text` (e.g. a vehicle's start time)."""
    return (f"[...document.querySelectorAll('button')].find(b => b.innerText.includes({json.dumps(label)}) && "
            f"(c => c && c.innerText.includes({json.dumps(text)}))(b.closest('[data-testid=stColumn]')))")


def by_text(tag, text):
    return (f"[...document.querySelectorAll({json.dumps(tag)})].find(e => e.innerText && "
            f"e.innerText.trim().includes({json.dumps(text)}) && e.offsetParent !== null)")


async def run(ws_url):
    async with websockets.connect(ws_url, max_size=None) as ws:
        p = Page(ws)
        await p.cmd("Page.enable")
        await p.cmd("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1.5, mobile=False)
        await p.cmd("Page.navigate", url=URL)
        for _ in range(40):                                       # first visit: dark-mode default reloads once
            if await p.js("localStorage.getItem('vtrace-dark-default')"):
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(4)
        if THEME == "light":
            await p.js("localStorage.setItem('stActiveTheme-/-v2', JSON.stringify('Light'))")
            await p.cmd("Page.reload")
        await p.wait_text("Sign in")
        await p.shot("login.png")
        for attempt in range(3):                                  # the first-visit theme reload can wipe the form
            await p.js("document.querySelector('input[aria-label=\"Username\"]').focus()")
            await p.type(ADMIN["username"])
            await p.js("document.querySelector('input[aria-label=\"Password\"]').focus()")
            await p.type(ADMIN["password"])
            await p.click(by_text("button", "Sign in"))
            try:
                await p.wait_text("Describe the vehicle", 25)         # the demo cameras load automatically
                break
            except TimeoutError:
                await p.cmd("Page.reload")
                await p.wait_text("Sign in")

        # 1 describe -> 2 ranked matches
        await p.click("document.querySelector('input[aria-label^=\"Colour\"]')")
        await p.click(by_text("[role=option]", DEMO["colour"]))
        await p.click("document.querySelector('input[aria-label^=\"Type\"]')")
        await p.click(by_text("[role=option]", DEMO["type"]))
        await p.click(by_text("button", "Search"))
        await p.wait_text("#1 ·")
        await p.shot("search.png", scroll_to=by_text("h3", "Best matches"))

        # 3 select -> where it was seen
        await p.click(button_in_column("Select", QUERY_TIME))
        await p.wait_text("Where this vehicle was seen")
        await p.shot("seen.png", scroll_to=by_text("h3", "Where this vehicle"))
        await p.js("window.scrollBy(0, 600)")
        await asyncio.sleep(1)
        await p.shot("seen_more.png")

        # how it works page
        await p.click("[...document.querySelectorAll('a')].find(a => a.innerText.includes('How it works'))")
        await p.wait_text("Re-ID model on the VeRi-776 benchmark")
        await p.shot("evaluation.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="vtrace-edge-")
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={profile}", "--window-size=1440,900", "about:blank"])
    try:
        for _ in range(40):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except Exception:
                time.sleep(0.5)
        asyncio.run(run(next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")))
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
