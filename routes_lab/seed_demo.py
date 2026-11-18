# seed_demo.py
# Offline fixture: real plates/models from the fleet list + synthetic tracks,
# so the map and the assignment panel can be exercised without logging into ETS.
#
#   python seed_demo.py            # fill the store in routes.db (today)
#   python seed_demo.py --clean    # drop all assignments for the day
import json
import math
import os
import random
from datetime import datetime

from routes_db import RoutesDB
from store import ZONES_PATH, norm_plate

# plates/models/categories are the real fleet records (map/src/data.js)
FLEET = [
    ("А414МА777", "ЭД 244КМ КАМАЗ 53605-А4", "Дороги", "Норма"),
    ("4628РА77", "Трактор МТЗ 320.4 с навесным", "Тротуары/Дворы", "Норма"),
    ("7922МР77", "Трактор Беларус 320.4М", "Тротуары/Дворы", "Норма"),
    ("5529РЕ77", "Трактор Беларус 82.1 (щётка)", "Тротуары/Дворы", "Не работает БНСО"),
    ("8714НЕ77", "BUCHER CITYCAT 1000", "Тротуары/Дворы", "Норма"),
    ("А894ММ77", "Самосвал КАМАЗ 65115-А4", "Дороги", "Норма"),
    ("О359ММ977", "Автосамосвал МАЗ 555025", "Дороги", "Машина не на связи"),
    ("6798РА77", "Погрузочно-уборочная ПУМ 4853", "Тротуары/Дворы", "Норма"),
    ("3003МН77", "Полуприцеп ОПМ-2,0", "Тротуары/Дворы", "Некорректное местоположение ТС"),
    ("Х894ВН977", "КДМ-360К КАМАЗ", "Дороги", "Норма"),
    ("4561МО77", "Экскаватор-погрузчик ЧЛМЗ 335.1", "Дороги", "Норма"),
    ("А446ТО799", "ГАЗ A22R32 автомастерская", "Спец/Вспом", "Норма"),
]

BASE = (55.667, 37.432)     # Малая Очаковская, 8с4
DISTRICT = (55.655, 37.485)


def load_zones():
    with open(ZONES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["zones"]


def dist(a, b):
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * 0.58) * 111.0


def pick_zones(zones, kind, center, count, used):
    cand = [z for z in zones if z["kind"] == kind and z["centroid"]
            and z["id"] not in used and not z.get("thin")]
    cand.sort(key=lambda z: dist(z["centroid"], center))
    return cand[:count]


def make_track(zones, seed):
    """Synthetic GPS trace: walk between zone centroids with GPS jitter."""
    rng = random.Random(seed)
    pts = []
    for zi, z in enumerate(zones):
        if not z["centroid"]:
            continue
        for step in range(14):
            t = step / 13.0
            lat = z["centroid"][0] + (rng.random() - 0.5) * 0.0016
            lon = z["centroid"][1] + (rng.random() - 0.5) * 0.0026
            if zi and step < 3:
                prev = zones[zi - 1]["centroid"]
                lat = prev[0] + (lat - prev[0]) * t
                lon = prev[1] + (lon - prev[1]) * t
            pts.append([round(lat, 6), round(lon, 6)])
    return [{"coords": p, "is_valid": True} for p in pts]


def build_cars(zones, day, with_assignments=True):
    db = RoutesDB()
    cars, used = [], set()
    for i, (plate, model, cat, problem) in enumerate(FLEET):
        kind = "mun" if "Двор" in cat else "odh"
        if plate == "А446ТО799":
            picked = []
        else:
            count = {"Норма": 6, "Не работает БНСО": 4}.get(problem, 3)
            picked = pick_zones(zones, kind, DISTRICT, count, used)
            used.update(z["id"] for z in picked)

        if with_assignments:
            for seq, z in enumerate(picked, start=1):
                db._conn.execute(
                    """INSERT OR IGNORE INTO assignments (day, plate, zone_id, seq, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (day, plate, z["id"], seq, datetime.now().isoformat(timespec="seconds")))
        db._conn.commit()

        track = make_track(picked, seed=i * 7 + 3)
        cars.append({
            "car_id": str(900 + i),
            "gov_number": plate,
            "model_name": model,
            "cat_b": cat,
            "mission_status": "Выполняется",
            "order_number": f"Ф-{1200 + i}",
            "percent": 0 if not track else random.Random(i).randint(35, 100),
            "fuel_start": round(180 + i * 7.5, 1),
            "fuel_refuel": "+40.0" if i % 4 == 0 else "-",
            "fuel_fact": round(120 + i * 5.5, 1),
            "distance": round(len(track) * 0.42, 1),
            "problem_type": problem,
            "track_detail": f"точек {len(track)}" if track else "нет трека",
            "valid_points": len(track),
            "_track_raw": track,
        })
    db.close()
    return cars


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(ZONES_PATH):
        print("zones.json not found - run: python preprocess_zones.py")
        return 2

    zones = load_zones()
    db = RoutesDB()
    db.import_zones(zones)
    if args.clean:
        db._conn.execute("DELETE FROM assignments WHERE day = ?", (args.day,))
        db._conn.commit()
        print(f"assignments for {args.day} cleared")
        db.close()
        return 0
    db.close()

    cars = build_cars(zones, args.day)
    print(f"zones loaded: {len(zones)}")
    print(f"demo cars:    {len(cars)}")
    d = RoutesDB()
    st = d.stats(args.day)
    print(f"assignments:  {st['assignments']} rows, {st['cars']} cars, {st['zones']} zones")
    d.close()
    print(f"cars json:    data/demo_cars.json")
    out = os.path.join(os.path.dirname(ZONES_PATH), "demo_cars.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cars, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
