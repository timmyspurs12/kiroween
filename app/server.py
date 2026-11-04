#!/usr/bin/env python3
"""NecroSpec API + static server (stdlib only, no third-party dependencies).

Endpoints
---------
GET  /api/health    -> {"status": "ok", "version", "engine"}
GET  /api/samples   -> sample corpus metadata (id, filename, title, origin,
                       description, note, expect_ok, source)
POST /api/analyze   -> body {"source": str, "filename": str}
                       -> full NecroSpec analysis envelope
GET  /api/engine    -> engine metadata (supported subset description)

Static: serves app/web_dist (the built frontend) with SPA fallback to
index.html for client-side routes.

Usage:  python3 app/server.py [--port 8747] [--host 0.0.0.0]
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from necro.analyzer import analyze  # noqa: E402
from necro.fixtures import SAMPLES  # noqa: E402
from necro import __version__ as ENGINE_VERSION  # noqa: E402

WEB_DIST = os.path.join(APP_DIR, "web_dist")
MAX_BODY = 2 * 1024 * 1024  # 2 MiB (preflight itself caps source at 32 KiB)
CONTENT_TYPES = ("text/html", "text/css", "text/javascript",
                 "application/javascript", "application/json",
                 "image/svg+xml", "image/png", "image/x-icon",
                 "font/woff2", "font/woff")

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "NecroSpec/1.0"

    # ---- helpers -------------------------------------------------------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status, code, message):
        self._send_json({"error": {"code": code, "message": message}}, status)

    def _serve_static(self, path):
        # resolve inside WEB_DIST only
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(WEB_DIST, rel))
        if not full.startswith(WEB_DIST):
            self._send_error_json(403, "FORBIDDEN", "path escapes web root")
            return
        if not os.path.isfile(full):
            # SPA fallback: unknown non-asset paths get index.html
            if "." not in os.path.basename(rel):
                full = os.path.join(WEB_DIST, "index.html")
            if not os.path.isfile(full):
                self._send_error_json(
                    404, "NO_FRONTEND_BUILD",
                    "frontend build not found; run 'npm run build' in frontend/ "
                    "or start the Vite dev server instead")
                return
        ext = os.path.splitext(full)[1]
        ctype = MIME.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",
                         "no-cache" if ext == ".html" else "max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    # ---- routes --------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._send_json({
                "status": "ok",
                "engine": "NecroSpec Rev6.4.2 subset",
                "version": ENGINE_VERSION,
            })
        elif path == "/api/samples":
            self._send_json({
                "samples": [{k: s[k] for k in
                             ("id", "filename", "title", "origin",
                              "description", "note", "expect_ok", "source")}
                            for s in SAMPLES],
            })
        elif path == "/api/engine":
            self._send_json({
                "engine": "NecroSpec static analysis (Rev6.4.2 frozen subset)",
                "version": ENGINE_VERSION,
                "layers": [
                    {"layer": 1, "name": "Preflight",
                     "desc": "fixed-format frame validation (cols 1-6/7/8-72/73+, "
                             "character set, size limits)"},
                    {"layer": 2, "name": "Lexical",
                     "desc": "column 8-72 token stream; reserved-word classification"},
                    {"layer": 3, "name": "Grammar",
                     "desc": "recursive-descent parse of the Rev4 §2.2.2 EBNF subset"},
                    {"layer": 4, "name": "AST",
                     "desc": "symbol table, PICTURE expansion, semantic rules"},
                ],
                "unsupported_note": "syntax outside the frozen subset is rejected "
                                    "with explicit diagnostics; success is never "
                                    "fabricated",
            })
        elif path.startswith("/api/"):
            self._send_error_json(404, "UNKNOWN_ENDPOINT",
                                  f"no such API endpoint: {path}")
        else:
            if not os.path.isdir(WEB_DIST):
                self._send_error_json(
                    503, "NO_FRONTEND_BUILD",
                    "frontend build not found; run 'npm run build' in frontend/")
                return
            self._serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/analyze":
            self._send_error_json(404, "UNKNOWN_ENDPOINT",
                                  f"no such API endpoint: {path}")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error_json(400, "BAD_REQUEST", "invalid Content-Length")
            return
        if length <= 0 or length > MAX_BODY:
            self._send_error_json(413, "PAYLOAD_TOO_LARGE",
                                  f"body must be 1..{MAX_BODY} bytes")
            return
        raw = self.rfile.read(length)
        try:
            req = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_error_json(400, "BAD_JSON", f"request is not valid JSON: {exc}")
            return
        if not isinstance(req, dict) or not isinstance(req.get("source"), str):
            self._send_error_json(422, "MISSING_SOURCE",
                                  "body must be {\"source\": str, \"filename\"?: str}")
            return
        filename = req.get("filename")
        if filename is not None and not isinstance(filename, str):
            self._send_error_json(422, "BAD_FILENAME", "filename must be a string")
            return
        try:
            result = analyze(req["source"], filename)
        except Exception as exc:  # engine must never 500-mask a crash
            self._send_error_json(
                500, "ENGINE_FAILURE",
                f"internal analyzer failure — please report: {type(exc).__name__}: {exc}")
            return
        self._send_json(result)

    def log_message(self, fmt, *args):  # quieter logs, still informative
        sys.stderr.write("[necrospec] %s\n" % (fmt % args))


def main():
    ap = argparse.ArgumentParser(description="NecroSpec API + static server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8747)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"NecroSpec server listening on http://{args.host}:{args.port} "
          f"(static root: {WEB_DIST})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
