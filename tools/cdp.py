"""Drive the running game through Chrome DevTools Protocol (dev tool).

Start the game with:  LegendsOfIdleon.exe --remote-debugging-port=9222
Usage:
  python cdp.py targets
  python cdp.py shot <out.png> [--target game]
  python cdp.py eval "<js expression>"
  python cdp.py click <x> <y>          # coordinates in CSS pixels of the page
  python cdp.py reload
"""
import base64
import io
import json
import sys
import urllib.request

import websocket

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PORT = 9222


def targets():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as r:
        return json.load(r)


def pick(kind="game"):
    ts = [t for t in targets() if t.get("type") in ("page", "iframe")]
    if kind == "game":
        for t in ts:
            if t["url"].endswith("/game/index.html") or "static/game" in t["url"]:
                return t
    for t in ts:
        if t.get("type") == "page":
            return t
    raise SystemExit("no target")


class Session:
    def __init__(self, target):
        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})


def game_context(page):
    """execution context id of the game iframe (static/game/index.html)"""
    tree = page.call("Page.getFrameTree")["frameTree"]
    frame_id = None
    for ch in tree.get("childFrames", []):
        if "static/game" in ch["frame"]["url"]:
            frame_id = ch["frame"]["id"]
    page.n += 1
    page.ws.send(json.dumps({"id": page.n, "method": "Runtime.enable"}))
    ctx = None
    while True:
        msg = json.loads(page.ws.recv())
        if msg.get("method") == "Runtime.executionContextCreated":
            c = msg["params"]["context"]
            aux = c.get("auxData", {})
            if aux.get("frameId") == frame_id and aux.get("isDefault"):
                ctx = c["id"]
        if msg.get("id") == page.n:
            break
    return ctx


def main():
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == "targets":
        for t in targets():
            print(t.get("type"), t.get("id"), t.get("url")[:150])
        return
    page = Session(pick("page"))
    if cmd == "shot":
        r = page.call("Page.captureScreenshot", format="png")
        open(a[1], "wb").write(base64.b64decode(r["data"]))
    elif cmd == "eval":
        expr = open(a[2], encoding="utf-8").read() if a[1] == "-f" else a[1]
        r = page.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True,
                      contextId=game_context(page))
        val = r.get("result", {}).get("value", r)
        if "--out" in a:  # full value to a file
            with open(a[a.index("--out") + 1], "w", encoding="utf-8") as f:
                f.write(val if isinstance(val, str) else json.dumps(val, ensure_ascii=False))
        else:
            print(json.dumps(val, ensure_ascii=False, indent=1)[:20000])
    elif cmd == "click":
        import time
        x, y = float(a[1]), float(a[2])
        page.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        time.sleep(0.05)
        for t in ("mousePressed", "mouseReleased"):
            page.call("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)
            time.sleep(0.08)
    elif cmd == "watch":  # watch <seconds> [js]: run js in the game frame, print console output
        import time
        page.call("Log.enable")
        ctx = game_context(page)
        if len(a) > 2:
            page.n += 1
            page.ws.send(json.dumps({"id": page.n, "method": "Runtime.evaluate",
                                     "params": {"expression": a[2], "contextId": ctx}}))
        end = time.time() + float(a[1])
        page.ws.settimeout(1)
        while time.time() < end:
            try:
                msg = json.loads(page.ws.recv())
            except Exception:
                continue
            m = msg.get("method")
            if m == "Runtime.consoleAPICalled":
                p = msg["params"]
                print(p["type"], " ".join(str(x.get("value", x.get("description", ""))) for x in p["args"])[:500])
            elif m == "Runtime.exceptionThrown":
                print("EXC", json.dumps(msg["params"]["exceptionDetails"])[:1500])
            elif m == "Log.entryAdded":
                e = msg["params"]["entry"]
                print("LOG", e.get("level"), e.get("text", "")[:500], e.get("url", ""))
    elif cmd == "move":
        page.call("Input.dispatchMouseEvent", type="mouseMoved", x=float(a[1]), y=float(a[2]))
    elif cmd == "reload":
        page.call("Page.reload")


if __name__ == "__main__":
    main()
