"""Headless check of the dashboard: console errors + screenshot. Usage: shot.py out.png [search-term]"""
import os, sys, threading, http.server, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
out = sys.argv[1]
term = sys.argv[2] if len(sys.argv) > 2 else None
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = os.environ.get("DASH_URL") or f"http://127.0.0.1:{srv.server_port}/dashboard/index.html"
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 1300})
    pg.on("console", lambda m: m.type in ("error", "warning") and errs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    pg.goto(url); pg.wait_for_timeout(2500)
    if term:
        pg.fill("#q", term); pg.wait_for_timeout(800)
    pg.click("[data-ev='0']"); pg.wait_for_timeout(int(os.environ.get("WAIT_MS","1500")))
    pg.screenshot(path=out, full_page=True)
    b.close()
srv.shutdown()
print("errors:", errs[:20] or "none")
