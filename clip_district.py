# clip_district.py
# Обрезает улицы и дворы по полигону района из district.geojson.
# Запуск: python clip_district.py

import json
import os
import sys

try:
    from shapely.geometry import LineString, Point, Polygon, mapping, shape
    from shapely.ops import unary_union
    from shapely.validation import make_valid
except ImportError:
    print("Нет библиотеки shapely. Выполните в командной строке:")
    print("    pip install shapely")
    sys.exit(1)

# ---------- Настройки путей ----------
BASE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.join(BASE, "map_clean")

STREETS_IN   = os.path.join(MAP_DIR, "streets_osm.json")
YARDS_IN     = os.path.join(MAP_DIR, "yards_osm.json")
DISTRICT_IN  = os.path.join(MAP_DIR, "district.geojson")

STREETS_OUT  = os.path.join(MAP_DIR, "streets_clipped.json")
YARDS_OUT    = os.path.join(MAP_DIR, "yards_clipped.json")
DISTRICT_OUT = os.path.join(MAP_DIR, "district.geojson")  # перезапишется тем же


def load_json(path):
    if not os.path.exists(path):
        print(f"⚠️  Файл не найден: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- 1. Загрузка улиц ----------
print("📂 Читаю улицы:", STREETS_IN)
streets_data = load_json(STREETS_IN)
if not streets_data:
    print("❌ Нет файла улиц. Сначала запустите get_osm_streets_clean.py")
    sys.exit(1)

features = streets_data["features"]
print(f"   Всего объектов: {len(features)}")


# ---------- 2. Полигон района из district.geojson ----------
print("\n📐 Читаю полигон района:", DISTRICT_IN)
if not os.path.exists(DISTRICT_IN):
    print(f"❌ Нет файла {DISTRICT_IN}")
    print("   Положите туда полигон района (можно скачать с OSM).")
    sys.exit(1)

with open(DISTRICT_IN, encoding="utf-8-sig") as f:
    district_geo = json.load(f)

district = shape(district_geo["features"][0]["geometry"])
print(f"✅ Полигон загружен")
print(f"   Площадь: {district.area:.6f}°, границы {district.bounds}")

if not district.is_valid:
    print("⚠️  Полигон самопересекается — исправляю...")
    district = make_valid(district)
    if district.geom_type == "GeometryCollection":
        polys = [g for g in district.geoms if g.geom_type == "Polygon"]
        district = max(polys, key=lambda p: p.area)
    print(f"   После исправления: площадь {district.area:.6f}°, границы {district.bounds}")


# ---------- 3. Обрезка ----------
def point_in(p, poly):
    return poly.contains(p) or poly.touches(p)


def keep_line(f, poly, ratio=0.5):
    """Линия остаётся, если >=ratio её точек внутри полигона."""
    coords = f.get("coords", [])
    if len(coords) < 2:
        return False
    pts = [Point(lo, la) for la, lo in coords]
    inside = sum(point_in(p, poly) for p in pts)
    return inside / len(pts) >= ratio


def keep_polygon(f, poly, ratio=0.5):
    """Полигон остаётся, если >=ratio его площади внутри."""
    ring = [(lo, la) for la, lo in f.get("coords", [])]
    if len(ring) < 3:
        return False
    try:
        g = Polygon(ring)
    except Exception:
        return False
    if not g.is_valid or g.area == 0:
        return False
    try:
        inter_area = g.intersection(poly).area
    except Exception:
        return False
    return inter_area / g.area >= ratio


# --- Улицы ---
streets_kept = [f for f in features if keep_line(f, district, 0.5)]
print(f"\n✂️  Улицы: {len(streets_kept)} из {len(features)} осталось")
with open(STREETS_OUT, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": streets_kept},
              f, ensure_ascii=False)
print(f"   Сохранено: {STREETS_OUT}")

# --- Дворы (если есть) ---
yards_data = load_json(YARDS_IN)
if yards_data:
    yards_kept = [f for f in yards_data["features"] if keep_polygon(f, district, 0.5)]
    print(f"\n✂️  Дворы: {len(yards_kept)} из {len(yards_data['features'])} осталось")
    with open(YARDS_OUT, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": yards_kept},
                  f, ensure_ascii=False)
    print(f"   Сохранено: {YARDS_OUT}")
else:
    print("\nℹ️  Дворов нет (yards_osm.json не найден) — пропускаю.")

print("\n🎉 ГОТОВО!")
print("\nВ index.html замените пути:")
print("   streets_osm.json  →  streets_clipped.json")
print("   yards_osm.json    →  yards_clipped.json")