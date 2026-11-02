"""Local editing server. Run:  python server.py   then open http://localhost:8765/
Serves this folder and saves maps as maps/<name>.json (plus maps/index.json for the public viewer).
"""

import json, os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(ROOT, "maps")
PORT = 8765
NAME = re.compile(r"^[\w][\w \-.]{0,60}$")
os.makedirs(MAPS, exist_ok=True)


def names():
    return sorted(
        f[:-5] for f in os.listdir(MAPS) if f.endswith(".json") and f != "index.json"
    )


def write_index():
    with open(os.path.join(MAPS, "index.json"), "w", encoding="utf-8") as f:
        json.dump(names(), f)


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def reply(self, code, obj=None):
        body = json.dumps(obj if obj is not None else {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def map_path(self):
        n = os.path.basename(self.path.split("?")[0][len("/api/maps/") :])
        from urllib.parse import unquote

        n = unquote(n)
        return (n, os.path.join(MAPS, n + ".json")) if NAME.match(n) else (None, None)

    def do_GET(self):
        if self.path == "/api/ping":
            return self.reply(200, {"ok": True})
        if self.path == "/api/maps":
            return self.reply(200, names())
        super().do_GET()

    def do_PUT(self):
        n, p = self.map_path()
        if not n:
            return self.reply(400, {"error": "bad name"})
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if not isinstance(data.get("features"), list):
            return self.reply(400, {"error": "bad map"})
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        write_index()
        self.reply(200)

    def do_POST(self):
        if not self.path.startswith("/api/rename/"):
            return self.reply(404, {"error": "not found"})
        from urllib.parse import unquote

        old = unquote(os.path.basename(self.path[len("/api/rename/") :]))
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        new = data.get("to", "")
        src, dst = os.path.join(MAPS, old + ".json"), os.path.join(MAPS, new + ".json")
        if (
            not (NAME.match(old) and NAME.match(new))
            or not os.path.exists(src)
            or os.path.exists(dst)
        ):
            return self.reply(400, {"error": "cannot rename"})
        os.rename(src, dst)
        write_index()
        self.reply(200)

    def do_DELETE(self):
        n, p = self.map_path()
        if n and os.path.exists(p):
            os.remove(p)
            write_index()
        self.reply(200)


if __name__ == "__main__":
    write_index()
    print(f"Editing server: http://localhost:{PORT}/   (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
