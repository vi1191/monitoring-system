# store.py
# Shared state between the Qt GUI (main thread) and the local map API server
# (worker threads). Everything the map needs is pulled over HTTP, so the same
# map/index.html runs unchanged in a plain browser pointed at 127.0.0.1:8001.
import json
import os
import threading
from datetime import datetime

from routes_db import RoutesDB

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "routes.db")
ZONES_PATH = os.path.join(HERE, "data", "zones.json")

# Golden-angle palette: distinct hues for ~20 vehicles, then lightness steps.
GOLDEN = 137.50776405003785


def stable_color(plate):
    """Deterministic color for a car that is not in the current shift list.

    Assignments survive a refresh, so a route can belong to a vehicle that is
    off the road today (yesterday's shift, a manual entry). It still needs a
    stable color instead of a random one that changes on every poll.
    """
    import zlib
    return car_color(zlib.crc32(str(plate).encode("utf-8")) % 200)


def hsl_to_hex(h, s, l):
    s, l = s / 100.0, l / 100.0
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = l - c / 2.0
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return "#%02x%02x%02x" % (
        round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))


def car_color(index):
    hue = (index * GOLDEN) % 360
    light = 42 + (index // 20) * 10
    return hsl_to_hex(hue, 62, min(light, 62))


def norm_plate(value):
    """Gov numbers arrive with trailing spaces / trailer suffixes."""
    if not value:
        return ""
    s = str(value).upper()
    for junk in ("ПРИЦЕП", "РТР"):
        s = s.replace(junk, "")
    return "".join(ch for ch in s if ch.isalnum())


class Store:
    """Thread-safe facade over the routes database + current shift data."""

    def __init__(self, db_path=DB_PATH):
        self._lock = threading.RLock()
        self.db = RoutesDB(db_path)
        self.day = datetime.now().strftime("%Y-%m-%d")
        self.active_plate = None
        self.cars = []            # last ETS collection (live or cache)
        self._tracks = {}         # plate -> [[lat, lon], ...]
        self.listeners = []       # callables() after any mutation
        self.zones_meta = self._load_zones_meta()
        # Collection state, shown by the map: idle | queued | running | done | error
        self.ets = {"status": "idle", "kind": None, "day": None, "progress": "",
                    "source": "нет данных", "error": None, "cars": 0,
                    "updated_at": None, "elapsed": None}
        # ESTP ticket pipeline: queued | running | done | error
        self.estp = {"status": "idle", "total": 0, "done": 0, "current": None,
                     "results": [], "error": None}
        self._want = None         # pending collection request
        self._estp_want = None    # pending estp tickets
        self._seq = 0

    # ---------- plumbing ----------
    def _load_zones_meta(self):
        if not os.path.exists(ZONES_PATH):
            return {}
        with open(ZONES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {z["id"]: {"name": z["name"], "kind": z["kind"]}
                for z in data.get("zones", [])}

    def changed(self, fn):
        self.listeners.append(fn)

    def _notify(self):
        for fn in list(self.listeners):
            try:
                fn()
            except Exception:
                pass

    def zones_ready(self):
        return bool(self.zones_meta)

    # ---------- shift data from ETS ----------
    def set_cars(self, cars):
        with self._lock:
            self.cars = cars or []
            self._tracks = {}
            rows = []
            for c in self.cars:
                plate = norm_plate(c.get("gov_number"))
                if not plate:
                    continue
                pts = [p["coords"] for p in (c.get("_track_raw") or [])
                       if isinstance(p, dict) and p.get("coords")]
                self._tracks[plate] = pts
                rows.append({
                    "plate": plate,
                    "model": c.get("model_name"),
                    "cat_b": c.get("cat_b"),
                    "grp": c.get("problem_type"),
                })
            self.db.upsert_cars(rows)
            self.ets["cars"] = len(self._tracks)

    def plates(self):
        with self._lock:
            return [norm_plate(c.get("gov_number")) for c in self.cars
                    if c.get("gov_number")]

    def color_map(self):
        """plate -> color, stable for the current shift ordering."""
        plates = [p for p in dict.fromkeys(self.plates()) if p]
        return {p: car_color(i) for i, p in enumerate(plates)}

    def set_day(self, day):
        with self._lock:
            self.day = day
            self._notify()

    def set_active(self, plate):
        with self._lock:
            self.active_plate = norm_plate(plate) or None
            self._notify()

    # ---------- queries ----------
    def state(self, day=None):
        day = day or self.day
        with self._lock:
            routes = self.db.routes(day)
            colors = self.color_map()
            plates = [p for p in dict.fromkeys(self.plates()) if p]
            assigned_ids = {a["zone_id"] for rows in routes.values() for a in rows}
            cars_out = []
            for c in self.cars:
                plate = norm_plate(c.get("gov_number"))
                if not plate:
                    continue
                items = routes.get(plate, [])
                cars_out.append({
                    "plate": plate,
                    "model": c.get("model_name"),
                    "problem": c.get("problem_type"),
                    "detail": c.get("track_detail"),
                    "percent": c.get("percent"),
                    "distance": c.get("distance"),
                    "cat_b": c.get("cat_b"),
                    "zones": len(items),
                    "status": (items[0]["status"] if items else None),
                    "color": colors.get(plate),
                    # Fuel
                    "fuel_start": c.get("fuel_start"),
                    "fuel_refuel": c.get("fuel_refuel"),
                    "fuel_refuel_detail": c.get("fuel_refuel_detail"),
                    "fuel_fact": c.get("fuel_fact"),
                    # Track diagnostics
                    "track_points": c.get("track_points", 0),
                    "valid_points": c.get("valid_points", 0),
                    "teleports": c.get("teleports", 0),
                })
            seen = set()
            cars_out_dedup = []
            for c in cars_out:
                if c["plate"] in seen:
                    continue
                seen.add(c["plate"])
                cars_out_dedup.append(c)
            # Routes may outlive the shift list: a car assigned yesterday or by hand
            # is not on the road today, but its plan is still real work.
            ghosts = []
            for plate in sorted(routes):
                rows = routes[plate]
                if not rows or plate in seen:
                    continue
                col = colors.get(plate) or stable_color(plate)
                colors[plate] = col
                info = self.db.car_info(plate) or {}
                ghosts.append({"plate": plate, "zones": len(rows), "color": col,
                               "model": info.get("model")})
            control = self.db.coverage(day, active_plates=list(seen))
            return {
                "day": day,
                "active": self.active_plate,
                "plates": plates,
                "cars": cars_out_dedup,
                "ghosts": ghosts,
                "colors": colors,
                "routes": routes,
                "control": control,
                "unassigned_zones": len(assigned_ids),
                "zones_total": len(self.zones_meta),
                "ets": dict(self.ets),
                "estp": dict(self.estp),
                "server_time": datetime.now().isoformat(timespec="seconds"),
            }

    def track(self, plate):
        with self._lock:
            return self._tracks.get(norm_plate(plate), [])

    def car_detail(self, plate):
        plate = norm_plate(plate)
        with self._lock:
            for c in self.cars:
                if norm_plate(c.get("gov_number")) == plate:
                    return {
                        "plate": plate,
                        "model": c.get("model_name"),
                        "mission": c.get("mission_status"),
                        "order_number": c.get("order_number"),
                        "percent": c.get("percent"),
                        "problem": c.get("problem_type"),
                        "detail": c.get("track_detail"),
                        "distance": c.get("distance"),
                        "cat_b": c.get("cat_b"),
                        "fuel_start": c.get("fuel_start"),
                        "fuel_refuel": c.get("fuel_refuel"),
                        "fuel_refuel_detail": c.get("fuel_refuel_detail"),
                        "fuel_fact": c.get("fuel_fact"),
                        "track_points": c.get("track_points", 0),
                        "valid_points": c.get("valid_points", 0),
                        "teleports": c.get("teleports", 0),
                        "silent_min": c.get("silent_min"),
                        "gps_code": c.get("gps_code"),
                        "garage_number": c.get("garage_number"),
                    }
        return None

    # ---------- mutations (called from the HTTP thread) ----------
    def known_plate(self, plate):
        """A plate is writable if it is on shift now or was seen before."""
        with self._lock:
            if any(norm_plate(c.get("gov_number")) == plate for c in self.cars):
                return True
        return self.db.car_info(plate) is not None

    def toggle_zone(self, zone_id, plate=None, day=None):
        plate = norm_plate(plate or self.active_plate)
        if not plate:
            return {"ok": False, "error": "no_active_car"}
        if zone_id not in self.zones_meta:
            # Rejecting unknown ids keeps typos and stale client state from
            # creating assignments that no UI can ever show or remove.
            return {"ok": False, "error": f"unknown_zone: {zone_id}"}
        if not self.known_plate(plate):
            return {"ok": False, "error": f"unknown_car: {plate}"}
        row = self.db.assign(day or self.day, plate, zone_id)
        self._notify()
        meta = self.zones_meta.get(zone_id, {})
        return {"ok": True, "assigned": row is not None, "row": row,
                "zone": {"id": zone_id, "name": meta.get("name"),
                         "kind": meta.get("kind")}}

    def clear_route(self, plate=None, day=None):
        plate = norm_plate(plate or self.active_plate)
        if plate:
            self.db.clear_route(day or self.day, plate)
            self._notify()
        return {"ok": True}

    def reorder(self, zone_ids, plate=None, day=None):
        plate = norm_plate(plate or self.active_plate)
        if plate and isinstance(zone_ids, list):
            self.db.reorder(day or self.day, plate, [str(z) for z in zone_ids])
            self._notify()
        return {"ok": True}

    def send_route(self, plate=None, day=None):
        """Stub for the real ETS call: persists status='sent' and returns payload."""
        plate = norm_plate(plate or self.active_plate)
        day = day or self.day
        if not plate:
            return {"ok": False, "error": "no_active_car"}
        route = self.db.route(day, plate)
        self.db.set_status(day, plate, "sent")
        self._notify()
        return {
            "ok": True, "stub": True, "plate": plate, "day": day,
            "zone_ids": [r["zone_id"] for r in route],
            "ets_payload_preview": {
                "date": day, "car_gov_number": plate,
                "geozones": [r["zone_id"] for r in route],
            },
        }

    def export_csv(self, day=None):
        """Routes of one day as CSV text (semicolon + BOM: opens in Excel)."""
        day = day or self.day
        lines = ["Дата;Номер ТС;Порядок;Зона;Тип;Статус"]
        for plate, rows in sorted(self.db.routes(day).items()):
            for r in rows:
                lines.append(f"{day};{plate};{r['seq']};{r['name'] or r['zone_id']};"
                             f"{r['kind'] or ''};{r['status']}")
        return "\ufeff" + "\r\n".join(lines) + "\r\n"

    def export_cars_csv(self):
        """Current shift as CSV: plates, status, fuel, mileage, zones."""
        day = self.day
        routes = self.db.routes(day)
        head = ("Номер ТС;Марка;Категория;Статус;Детали;Пробег км;Вып. %;"
                "Топливо выезд;Топливо заправка;Топливо факт;Точек;Телепортов;Зон;Заявка ЕСТП")
        lines = [head]
        for c in self.cars:
            plate = norm_plate(c.get("gov_number"))
            if not plate:
                continue
            problem = c.get("problem_type") or ""
            pct = c.get("percent")
            lines.append(";".join(str(v) for v in (
                plate, c.get("model_name") or "", c.get("cat_b") or "",
                problem, (c.get("track_detail") or "").replace(";", ","),
                c.get("distance") or 0, "" if pct is None else pct,
                c.get("fuel_start"), c.get("fuel_refuel"), c.get("fuel_fact"),
                c.get("valid_points"), c.get("teleports"),
                len(routes.get(plate, [])),
                "да" if problem and problem != "Норма" else "",
            )))
        return "\ufeff" + "\r\n".join(lines) + "\r\n"

    def last_here(self, zone_id, day=None):
        row = self.db.last_assignment(day or self.day, zone_id)
        if row:
            row["car"] = self.db.car_info(row["plate"])
        return row

    # ---------- ETS collection pipeline ----------

    def request_collection(self, kind="live", day=None):
        """Queue a collection job. The Qt main thread polls take_collection()."""
        with self._lock:
            self._seq += 1
            self._want = {"kind": kind, "day": day or self.day, "seq": self._seq}
            self.ets["status"] = "queued"
            self.ets["progress"] = "ждём потока Qt…"
            self.ets["error"] = None
            self._notify()
            return dict(self._want)

    def take_collection(self):
        with self._lock:
            req, self._want = self._want, None
            return req

    def set_ets(self, **kw):
        """Update the ETS status blob (progress, errors, source, etc.)."""
        with self._lock:
            self.ets.update(kw)
            self.ets["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self._notify()

    # ---------- ESTP ticket pipeline ----------

    def request_estp(self, tickets):
        """Queue ESTP tickets: [{plate, gov_number, sla, comment}, ...]."""
        with self._lock:
            clean = []
            for t in tickets or []:
                plate = norm_plate(t.get("plate") or t.get("gov_number"))
                if not plate or not t.get("sla"):
                    continue
                clean.append({"plate": plate, "gov_number": t.get("gov_number") or plate,
                              "problem_type": t.get("problem_type") or "",
                              "sla": t["sla"], "comment": t.get("comment") or ""})
            if not clean:
                return {"ok": False, "error": "no_valid_tickets"}
            self._estp_want = clean
            self.estp.update({"status": "queued", "total": len(clean), "done": 0,
                               "current": None, "results": [], "error": None})
            self._notify()
            return {"ok": True, "queued": len(clean)}

    def take_estp(self):
        with self._lock:
            req, self._estp_want = self._estp_want, None
            return req

    def set_estp(self, **kw):
        with self._lock:
            self.estp.update(kw)
            self.estp["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self._notify()

    def estp_result(self, plate, ok, message):
        """Append/replace the outcome of one ticket, keyed by plate."""
        with self._lock:
            results = [r for r in self.estp.get("results", []) if r.get("plate") != plate]
            results.append({"plate": plate, "ok": bool(ok), "message": message})
            self.estp["results"] = results
            self.estp["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self._notify()

    def estp_issue_counts(self):
        """How many cars fall into each problem class (for the panel badge)."""
        with self._lock:
            out = {}
            for c in self.cars:
                p = c.get("problem_type") or ""
                if p and p != "Норма":
                    out[p] = out.get(p, 0) + 1
            return out
