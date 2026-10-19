"""Shorts Studio: a small dashboard to build and export vertical MP4 videos.

Run:  python -m shorts_studio.server   (requires ffmpeg on PATH)
"""
import json
import os
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import render

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("SHORTS_DATA", os.path.join(HERE, "data"))
MEDIA = os.path.join(DATA, "media")
EXPORTS = os.path.join(DATA, "exports")
MAX_UPLOAD = 500 * 1024 * 1024
VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv", ".m4v")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _file(self, folder, name, ctype, download=False):
        name = os.path.basename(name)
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            return self._send(404, {"error": "not found"})
        with open(path, "rb") as f:
            data = f.read()
        h = {"Content-Disposition": 'attachment; filename="%s"' % name} if download else {}
        self._send(200, data, ctype, h)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            return self._file(os.path.join(HERE, "static"), "index.html", "text/html")
        if p == "/api/clips":
            names = sorted(n for n in os.listdir(MEDIA) if n.lower().endswith(VIDEO_EXT))
            return self._send(200, names)
        if p.startswith("/media/"):
            return self._file(MEDIA, p[7:], "video/mp4")
        if p.startswith("/exports/"):
            return self._file(EXPORTS, p[9:], "video/mp4", download=True)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        p, _, query = self.path.partition("?")
        length = int(self.headers.get("Content-Length") or 0)
        if p == "/api/upload":
            m = re.search(r"name=([^&]+)", query)
            from urllib.parse import unquote
            name = os.path.basename(unquote(m.group(1))) if m else ""
            name = re.sub(r"[^\w.\- ]", "_", name)
            if not name.lower().endswith(VIDEO_EXT) or length <= 0 or length > MAX_UPLOAD:
                return self._send(400, {"error": "invalid upload"})
            with open(os.path.join(MEDIA, name), "wb") as f:
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            return self._send(200, {"name": name})
        if p == "/api/export":
            try:
                req = json.loads(self.rfile.read(min(length, 1 << 20)) or b"{}")
                out = "short-%s.mp4" % uuid.uuid4().hex[:10]
                render.render(req.get("clips"), MEDIA, os.path.join(EXPORTS, out),
                              req.get("caption", ""))
            except (ValueError, TypeError, AttributeError) as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # ffmpeg missing or failed
                return self._send(500, {"error": "render failed: %s" % e})
            return self._send(200, {"url": "/exports/" + out})
        self._send(404, {"error": "not found"})


def main(host="127.0.0.1", port=8000):
    os.makedirs(MEDIA, exist_ok=True)
    os.makedirs(EXPORTS, exist_ok=True)
    print("Shorts Studio on http://%s:%d" % (host, port))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
