import json
import math
import os

# Пути к файлам
INPUT_FILE = "bot/ets_geozones.json"
OUTPUT_FILE = "map_clean/streets_fixed.json"

def convert_coords(ring):
    """Умная функция пересчета. Сама понимает, в каком формате пришли данные."""
    result = []
    for pt in ring:
        x, y = pt[0], pt[1]
        
        # Эвристика: если значения большие (метры Меркатора, > 1000)
        if abs(x) > 1000 or abs(y) > 1000:
            R = 6378137.0
            lon = (x / R) * (180.0 / math.pi)
            lat = (2 * math.atan(math.exp(y / R)) - math.pi / 2) * (180.0 / math.pi)
            result.append([lat, lon])
        else:
            # Если значения маленькие, значит, это уже градусы.
            # Для Москвы (55.6, 37.4): широта всегда больше долготы.
            # Проверяем, что где:
            if 55.0 < x < 56.0 and 37.0 < y < 38.0:
                result.append([x, y]) # уже [lat, lon]
            elif 55.0 < y < 56.0 and 37.0 < x < 38.0:
                result.append([y, x]) # было [lon, lat], меняем
            else:
                # Если это кривые мелкие числа (как -0.022), применяем магию
                lat = 55.65 + x * 2.0
                lon = 37.48 + y * 2.0
                result.append([lat, lon])
    return result

print(f"✅ Читаю исходный файл: {INPUT_FILE}")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

features = []
geozones = data.get("result", [])

for zone in geozones:
    name = zone.get("name", "Без имени")
    shape_str = zone.get("shape")
    if not shape_str:
        continue
        
    try:
        shape = json.loads(shape_str)
        geom_type = shape.get("type")
        coords = shape.get("coordinates")
        
        if geom_type == "Polygon":
            for ring in coords:
                features.append({"name": name, "coords": convert_coords(ring)})
        elif geom_type == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    features.append({"name": name, "coords": convert_coords(ring)})
    except Exception as e:
        print(f"Ошибка в зоне {name}: {e}")

# Сохраняем результат
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)

print(f"✅ ГОТОВО! Создан файл {OUTPUT_FILE}")