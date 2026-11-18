# preprocess_zones.py
# MSK-77 (meters) -> WGS84, stable zone ids, geometry simplification.
# Reads the original ETS dump read-only and writes a compact zones.json
# that the browser can parse instantly (no proj4, no 14 MB geojson).
#
#   python preprocess_zones.py [--tolerance 2.0] [--out data/zones.json]
import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
# The raw ETS dump lives next to zones.json: 14 MB, rebuildable with
# get_ets_geozones.py, so it is kept out of git while zones.json is not.
SRC_GEOJSON = os.path.join(HERE, "data", "road_areas_raw.geojson")
DEFAULT_OUT = os.path.join(HERE, "data", "zones.json")

# Same definition that map_clean/index.html used for proj4js.
MSK77 = (
    "+proj=tmerc +lat_0=55.66666666667 +lon_0=37.5 +k=1 +x_0=0 +y_0=0 "
    "+ellps=bessel +towgs84=316.151,78.924,589.65,-1.57273,2.69209,2.34693,8.4507 "
    "+units=m +no_defs"
)
TO_WGS84 = Transformer.from_crs(MSK77, "EPSG:4326", always_xy=True)

# Round projected coordinates: 5 decimals ~= 1.1 m, enough for yards/MKAD.
COORD_NDIGITS = 5

ODH_NAME_HINTS = ("МКАД", "Проезд", "Парк", "Бульвар", "Шоссе", "Проспект", "Улица")
MUN_NAME_HINTS = ("д.", "корп.", "дом")


def classify(props):
    """ODH vs MUNICIPAL, same rules the original index.html used."""
    name = props.get("name") or ""
    t = props.get("type")
    if t in ("ODH", "MUNICIPAL"):
        return "odh" if t == "ODH" else "mun"
    if any(h in name for h in MUN_NAME_HINTS):
        return "mun"
    if any(h in name for h in ODH_NAME_HINTS):
        return "odh"
    return "mun"


def zone_id(name, ring_m):
    """Stable id: derived from name + raw geometry, before simplification.

    Re-running the ETS export keeps ids stable; changing --tolerance does not
    invalidate assignments because the hash is taken over the source ring.
    """
    h = hashlib.sha1()
    h.update((name or "").encode("utf-8"))
    h.update(b"|")
    for x, y in ring_m:
        h.update(f"{x:.1f},{y:.1f};".encode("ascii"))
    return "z" + h.hexdigest()[:10]


def _perp_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def rdp(points, tol):
    """Ramer-Douglas-Peucker, iterative (polygons here reach ~1000 vertices)."""
    n = len(points)
    if n < 3 or tol <= 0:
        return points[:]
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        dmax, idx = -1.0, -1
        a, b = points[i], points[j]
        for k in range(i + 1, j):
            d = _perp_dist(points[k], a, b)
            if d > dmax:
                dmax, idx = d, k
        if dmax > tol:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(points, keep) if k]


def dedupe(points):
    out = []
    for p in points:
        if not out or (abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9):
            out.append(p)
    return out


def centroid_and_area(ring):
    """Area-weighted centroid (shoelace) in the same units as the ring."""
    n = len(ring)
    if n == 0:
        return (0.0, 0.0), 0.0
    a2 = cx = cy = 0.0
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        a2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(a2) < 1e-9:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys)), 0.0
    return (cx / (3.0 * a2), cy / (3.0 * a2)), abs(a2) / 2.0


def load_rings(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    feats = data.get("features", [])
    rings = []
    for feat in feats:
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        if geom.get("type") != "Polygon":
            continue
        coords = (geom.get("coordinates") or [[]])[0]
        if len(coords) < 4:
            continue
        rings.append((props, [(c[0], c[1]) for c in coords]))
    return rings


def build(tolerance):
    raw = load_rings(SRC_GEOJSON)
    zones = {}
    skipped = 0
    for props, ring_m in raw:
        name = props.get("name") or ""
        zid = zone_id(name, ring_m)
        if zid in zones:
            continue  # exact geometry+name duplicate in the source dump
        simple = dedupe(rdp(ring_m, tolerance))
        degenerate = False
        if len(simple) < 4:
            # Degenerate slivers (area ~0) collapse under RDP. Keep them raw:
            # a yard we cannot click is worse than a thin polygon.
            simple = dedupe(ring_m)
            degenerate = True
        simple = simple[:-1] if simple[0] == simple[-1] else simple
        if len(simple) < 3:
            skipped += 1
            continue
        cen_m, area_m2 = centroid_and_area(simple)
        lon, lat = TO_WGS84.transform(cen_m[0], cen_m[1])
        latlon = []
        for x, y in simple:
            plon, plat = TO_WGS84.transform(x, y)
            latlon.append([round(plat, COORD_NDIGITS), round(plon, COORD_NDIGITS)])
        zone = {
            "id": zid,
            "name": name,
            "kind": classify(props),
            "ets_id": props.get("id") or props.get("geozone_id"),
            "area_m2": int(round(area_m2)),
            "centroid": [round(lat, COORD_NDIGITS), round(lon, COORD_NDIGITS)],
            "c": latlon,
        }
        if degenerate or area_m2 < 100:
            zone["thin"] = True
        zones[zid] = zone
    return list(zones.values()), len(raw), skipped


def main():
    ap = argparse.ArgumentParser(description="ETS geojson -> compact zones.json")
    ap.add_argument("--tolerance", type=float, default=2.0,
                    help="RDP tolerance in meters (default 2.0)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(SRC_GEOJSON):
        print(f"NOT FOUND: {SRC_GEOJSON}", file=sys.stderr)
        print("Скачай выгрузку зон:  python get_ets_geozones.py", file=sys.stderr)
        return 2

    src_size = os.path.getsize(SRC_GEOJSON)
    zones, total, skipped = build(args.tolerance)
    src_vertices = sum(len(z["c"]) for z in zones)

    payload = {
        "meta": {
            "source": os.path.relpath(SRC_GEOJSON, HERE).replace("\\", "/"),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tolerance_m": args.tolerance,
            "src_features": total,
            "skipped": skipped,
            "srs": "EPSG:4326 (pre-projected from MSK-77)",
        },
        "zones": sorted(zones, key=lambda z: (z["kind"], z["name"], z["id"])),
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    out_size = os.path.getsize(args.out)
    odh = sum(1 for z in zones if z["kind"] == "odh")
    print(f"source      : {src_size / 1024 / 1024:.1f} MB, {total} polygons")
    print(f"zones       : {len(zones)} (odh {odh}, mun {len(zones) - odh}), skipped {skipped}")
    print(f"vertices    : {src_vertices} after RDP @ {args.tolerance} m")
    print(f"output      : {args.out}  ({out_size / 1024:.0f} KB, "
          f"{out_size / src_size * 100:.1f}% of source)")


if __name__ == "__main__":
    sys.exit(main())
