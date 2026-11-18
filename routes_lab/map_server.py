# map_server.py
# Tiny local HTTP API + static file server for the map.
#
# The map is a plain web app: it pulls state with GET /api/state and posts
# mutations back. That keeps Python<->JS typed (JSON, no string interpolation)
# and lets the very same map/index.html be opened in Chrome for debugging.
import json
import os
import posixpath
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8001


class MapAPI:
    """Dispatch table: (method, path) -> callable(query, payload) -> dict."""

    def __init__(self, store):
        self.store = store

    def handle(self, method, path, query, payload):
        s = self.store
        try:
            if method == "GET":
                if path == "/api/state":
                    return {"ok": True, "state": s.state(query.get("day", [None])[0])}
                if path == "/api/track":
                    plate = query.get("plate", [""])[0]
                    return {"ok": True, "coords": s.track(plate),
                            "car": s.car_detail(plate)}
                if path == "/api/car":
                    return {"ok": True, "car": s.car_detail(query.get("plate", [""])[0])}
                if path == "/api/last_here":
                    return {"ok": True,
                            "last": s.last_here(query.get("zone_id", [""])[0])}
                if path == "/api/health":
                    return {"ok": True, "zones_ready": s.zones_ready(),
                            "day": s.day, "cars": len(s.cars), "ets": s.ets}
                if path == "/api/collect/status":
                    return {"ok": True, "ets": s.ets}
                if path == "/api/estp/status":
                    return {"ok": True, "estp": s.estp, "issues": s.estp_issue_counts()}
                return {"ok": False, "error": "unknown_endpoint", "path": path}

            if method == "POST":
                act = payload.get("action")
                if act == "zone/toggle":
                    return s.toggle_zone(payload.get("zone_id"), payload.get("plate"))
                if act == "route/clear":
                    return s.clear_route(payload.get("plate"))
                if act == "route/reorder":
                    return s.reorder(payload.get("zone_ids"), payload.get("plate"))
                if act == "route/send":
                    return s.send_route(payload.get("plate"))
                if act == "car/active":
                    s.set_active(payload.get("plate"))
                    return {"ok": True, "active": s.active_plate}
                if act == "day":
                    s.set_day(payload.get("day"))
                    return {"ok": True, "day": s.day}
                if act == "collect":
                    req = s.request_collection("live", payload.get("day"))
                    return {"ok": True, "queued": req}
                if act == "estp/submit":
                    return s.request_estp(payload.get("tickets"))
                if act == "log":
                    lvl = payload.get("level", "js")
                    print(f"    [{lvl}] {payload.get('msg', '')}", flush=True)
                    return {"ok": True}
                return {"ok": False, "error": "unknown_action", "action": act}

            return {"ok": False, "error": "method_not_allowed"}
        except Exception as exc:  # never kill the request thread on a bad call
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


class Handler(SimpleHTTPRequestHandler):
    root = HERE

    def __init__(self, *args, api=None, **kwargs):
        self.api = api
        super().__init__(*args, directory=self.root, **kwargs)

    # ---- static ----
    def translate_path(self, path):
        rel = urlparse(path).path
        rel = posixpath.normpath(rel).lstrip("/")
        if rel in ("", ".", "index.html", "/"):
            rel = "map/index.html"
        full = posixpath.normpath(posixpath.join(self.root.replace("\\", "/"), rel))
        if not full.startswith(self.root.replace("\\", "/")):
            full = self.root
        return full.replace("/", os.sep)

    def end_headers(self):
        if self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        # --- CSV export (raw text, not JSON) ---
        if parsed.path == "/api/export_cars.csv":
            # BOM is already inside the string returned by Store.
            body = self.api.store.export_cars_csv().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="shift.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/export.csv":
            csv_text = self.api.store.export_csv(day)
            body = csv_text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="routes.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.startswith("/api/"):
            return self._json(self.api.handle("GET", parsed.path,
                                              parse_qs(parsed.query), None))
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._json({"ok": False, "error": "not_found"}, 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except Exception as exc:
            return self._json({"ok": False, "error": f"bad_json: {exc}"}, 400)
        return self._json(self.api.handle("POST", parsed.path,
                                          parse_qs(parsed.query), payload))

    def log_message(self, fmt, *args):
        # Tiles and /api/state polling are chatty; keep the console readable.
        if self.path and self.path.startswith("/api/"):
            return
        super().log_message(fmt, *args)


class MapServerThread(threading.Thread):
    def __init__(self, store, port=DEFAULT_PORT):
        super().__init__(daemon=True)
        self.port = port
        self.server = None
        self.api = MapAPI(store)
        self.error = None

    def run(self):
        handler = lambda *a, **k: Handler(*a, api=self.api, **k)  # noqa: E731
        try:
            ThreadingHTTPServer.allow_reuse_address = True
            self.server = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
            self.server.serve_forever()
        except Exception as exc:
            self.error = exc
            print(f"Map server error: {exc}", flush=True)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
