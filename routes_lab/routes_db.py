# routes_db.py
# SQLite storage for route assignments: which zone is assigned to which vehicle
# on which day, in which order, and whether it was sent to ETS.
#
# Assignments are keyed by zone_id (stable id), never by zone name: names are
# not unique in the ETS dump (16 polygons share the name "MKAD, Leningradskaya
# interchange").
import json
import os
import sqlite3
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "routes.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS zones (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    kind      TEXT NOT NULL,
    ets_id    TEXT,
    area_m2   INTEGER DEFAULT 0,
    centroid  TEXT,
    thin      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cars (
    plate   TEXT PRIMARY KEY,
    model   TEXT,
    grp     TEXT,
    cat_b   TEXT,
    photo   TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    day        TEXT NOT NULL,
    plate      TEXT NOT NULL,
    zone_id    TEXT NOT NULL,
    seq        INTEGER NOT NULL DEFAULT 1,
    status     TEXT NOT NULL DEFAULT 'draft',
    sent_at    TEXT,
    updated_at TEXT,
    UNIQUE (day, plate, zone_id)
);

CREATE INDEX IF NOT EXISTS idx_assign_day  ON assignments (day);
CREATE INDEX IF NOT EXISTS idx_assign_zone ON assignments (zone_id);
CREATE INDEX IF NOT EXISTS idx_assign_car  ON assignments (day, plate);
"""


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def prev_day(day):
    d = datetime.strptime(day, "%Y-%m-%d") - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


class RoutesDB:
    def __init__(self, path=DB_PATH):
        self.path = path
        # The map API serves requests from its own threads; all access is
        # serialized by Store._lock, so a single shared connection is fine.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    # ---------------- zones ----------------
    def import_zones(self, zones):
        """Upsert zones coming from data/zones.json. Names may repeat, ids not."""
        rows = [(
            z["id"], z.get("name") or "", z.get("kind") or "mun",
            z.get("ets_id"), int(z.get("area_m2") or 0),
            json.dumps(z.get("centroid")), 1 if z.get("thin") else 0,
        ) for z in zones]
        with self._conn:
            self._conn.executemany(
                """INSERT INTO zones (id, name, kind, ets_id, area_m2, centroid, thin)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name = excluded.name, kind = excluded.kind,
                     ets_id = excluded.ets_id, area_m2 = excluded.area_m2,
                     centroid = excluded.centroid, thin = excluded.thin""",
                rows,
            )
        # Geometry lives in zones.json only; drop assignments pointing to removed zones.
        with self._conn:
            self._conn.execute(
                "DELETE FROM assignments WHERE zone_id NOT IN (SELECT id FROM zones)"
            )
        return len(rows)

    def all_zones(self):
        out = []
        for r in self._conn.execute(
                "SELECT id, name, kind, area_m2, centroid, thin FROM zones"):
            out.append({
                "id": r["id"], "name": r["name"], "kind": r["kind"],
                "area_m2": r["area_m2"], "thin": bool(r["thin"]),
                "centroid": json.loads(r["centroid"]) if r["centroid"] else None,
            })
        return out

    # ---------------- cars ----------------
    def upsert_cars(self, cars):
        rows = [(c["plate"], c.get("model"), c.get("grp"), c.get("cat_b"),
                 c.get("photo")) for c in cars if c.get("plate")]
        if not rows:
            return 0
        with self._conn:
            self._conn.executemany(
                """INSERT INTO cars (plate, model, grp, cat_b, photo)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(plate) DO UPDATE SET
                     model = excluded.model, grp = excluded.grp,
                     cat_b = excluded.cat_b, photo = excluded.photo""",
                rows,
            )
        return len(rows)

    def car_info(self, plate):
        r = self._conn.execute("SELECT * FROM cars WHERE plate = ?", (plate,)).fetchone()
        return dict(r) if r else None

    # ---------------- assignments ----------------
    def route(self, day, plate):
        rows = self._conn.execute(
            """SELECT a.zone_id, a.seq, a.status, z.name, z.kind, z.area_m2, z.centroid
               FROM assignments a LEFT JOIN zones z ON z.id = a.zone_id
               WHERE a.day = ? AND a.plate = ? ORDER BY a.seq""",
            (day, plate)).fetchall()
        return [dict(r) for r in rows]

    def routes(self, day):
        """{plate: [assignment, ...]} for the whole shift."""
        out = {}
        rows = self._conn.execute(
            """SELECT a.plate, a.zone_id, a.seq, a.status, z.name, z.kind,
                      z.area_m2, z.centroid
               FROM assignments a LEFT JOIN zones z ON z.id = a.zone_id
               WHERE a.day = ? ORDER BY a.plate, a.seq""", (day,)).fetchall()
        for r in rows:
            d = dict(r)
            out.setdefault(d.pop("plate"), []).append(d)
        return out

    def next_seq(self, day, plate):
        r = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) m FROM assignments WHERE day = ? AND plate = ?",
            (day, plate)).fetchone()
        return r["m"] + 1

    def assign(self, day, plate, zone_id):
        """Toggle-safe: returns the resulting row, or None when it was removed."""
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO assignments (day, plate, zone_id, seq, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(day, plate, zone_id) DO NOTHING""",
                (day, plate, zone_id, self.next_seq(day, plate), now_iso()),
            )
            if cur.rowcount == 0:  # already there -> toggle off
                self._conn.execute(
                    "DELETE FROM assignments WHERE day = ? AND plate = ? AND zone_id = ?",
                    (day, plate, zone_id))
                self._compact(day, plate)
                return None
            r = self._conn.execute(
                """SELECT a.seq, a.status, z.name, z.kind FROM assignments a
                   LEFT JOIN zones z ON z.id = a.zone_id
                   WHERE a.day = ? AND a.plate = ? AND a.zone_id = ?""",
                (day, plate, zone_id)).fetchone()
        return {
            "zone_id": zone_id, "plate": plate, "day": day,
            "seq": r["seq"], "status": r["status"],
            "name": r["name"], "kind": r["kind"],
        }

    def unassign(self, day, plate, zone_id):
        with self._conn:
            self._conn.execute(
                "DELETE FROM assignments WHERE day = ? AND plate = ? AND zone_id = ?",
                (day, plate, zone_id))
            self._compact(day, plate)

    def clear_route(self, day, plate):
        with self._conn:
            self._conn.execute(
                "DELETE FROM assignments WHERE day = ? AND plate = ?", (day, plate))

    def reorder(self, day, plate, zone_ids):
        """Persist drag-and-drop order of one vehicle's route."""
        with self._conn:
            for i, zid in enumerate(zone_ids, start=1):
                self._conn.execute(
                    "UPDATE assignments SET seq = ?, updated_at = ? "
                    "WHERE day = ? AND plate = ? AND zone_id = ?",
                    (i, now_iso(), day, plate, zid))

    def _compact(self, day, plate):
        """Renumber seq 1..n after a removal so numbers never show as 1,3,7."""
        rows = self._conn.execute(
            "SELECT id FROM assignments WHERE day = ? AND plate = ? ORDER BY seq",
            (day, plate)).fetchall()
        for i, r in enumerate(rows, start=1):
            self._conn.execute("UPDATE assignments SET seq = ? WHERE id = ?",
                               (i, r["id"]))

    def set_status(self, day, plate, status):
        ts = now_iso() if status == "sent" else None
        with self._conn:
            self._conn.execute(
                "UPDATE assignments SET status = ?, sent_at = COALESCE(?, sent_at) "
                "WHERE day = ? AND plate = ?",
                (status, ts, day, plate))

    # ---------------- control panel ----------------
    def coverage(self, day, active_plates=None):
        """Uncovered zones, double-assigned zones, vehicles with empty routes."""
        assigned = {}
        for r in self._conn.execute(
                """SELECT a.zone_id, a.plate FROM assignments a
                   WHERE a.day = ? ORDER BY a.plate""", (day,)):
            assigned.setdefault(r["zone_id"], []).append(r["plate"])

        uncovered = [
            {"id": r["id"], "name": r["name"], "kind": r["kind"]}
            for r in self._conn.execute(
                """SELECT z.id, z.name, z.kind FROM zones z
                   WHERE z.id NOT IN (SELECT zone_id FROM assignments WHERE day = ?)
                   ORDER BY z.kind, z.name""", (day,))
        ]
        conflicts = [
            {"zone_id": zid, "plates": plates}
            for zid, plates in assigned.items() if len(plates) > 1
        ]
        covered = set(assigned)
        by_car = self.routes(day)
        empty = []
        if active_plates:
            empty = [p for p in active_plates if p not in by_car]

        # ODH zones are MKAD interchanges across the whole city, so a single
        # coverage ratio over both kinds is meaningless. Report them apart.
        counts = {}
        for r in self._conn.execute("SELECT kind, COUNT(*) c FROM zones GROUP BY kind"):
            counts[r["kind"]] = r["c"]
        kind_covered = {}
        for r in self._conn.execute(
                """SELECT z.kind, COUNT(DISTINCT a.zone_id) c
                   FROM assignments a JOIN zones z ON z.id = a.zone_id
                   WHERE a.day = ? GROUP BY z.kind""", (day,)):
            kind_covered[r["kind"]] = r["c"]

        total = self._conn.execute("SELECT COUNT(*) c FROM zones").fetchone()["c"]
        return {
            "day": day,
            "zones_total": total,
            "zones_covered": len(covered),
            "uncovered": uncovered,
            "conflicts": conflicts,
            "empty_cars": empty,
            "mun_total": counts.get("mun", 0),
            "mun_covered": kind_covered.get("mun", 0),
            "odh_total": counts.get("odh", 0),
            "odh_covered": kind_covered.get("odh", 0),
        }

    def last_assignment(self, day, zone_id):
        """Who was here on the previous day that had any assignment."""
        r = self._conn.execute(
            """SELECT a.day, a.plate FROM assignments a
               WHERE a.zone_id = ? AND a.day < ?
               ORDER BY a.day DESC LIMIT 1""", (zone_id, day)).fetchone()
        return dict(r) if r else None

    def stats(self, day):
        r = self._conn.execute(
            """SELECT COUNT(*) rows_, COUNT(DISTINCT plate) cars_,
                      COUNT(DISTINCT zone_id) zones_
               FROM assignments WHERE day = ?""", (day,)).fetchone()
        return {"assignments": r["rows_"], "cars": r["cars_"], "zones": r["zones_"]}
