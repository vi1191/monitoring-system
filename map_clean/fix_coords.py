import json
import os
import math

current_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(current_dir, "streets_ets.json")
output_file = os.path.join(current_dir, "streets_fixed.json")

print(f"✅ Читаю файл: {input_file}")
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Точная формула для этих данных
def fix_point(x, y):
    # В исходнике координаты перепутаны. 
    # x (это -0.022) - это на самом деле долгота, но сдвинутая.
    # y (это -0.017) - это широта.
    # Применяем точную формулу Меркатора.
    R = 6378137.0
    
    # Переводим в градусы
    lon = (x / R) * (180.0 / math.pi)
    lat = (2 * math.atan(math.exp(y / R)) - math.pi / 2) * (180.0 / math.pi)
    
    return [lat, lon]

# Перебираем все фичи
for feature in data.get("features", []):
    if "coords" in feature:
        feature["coords"] = [fix_point(pt[0], pt[1]) for pt in feature["coords"]]

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

print("✅ ГОТОВО! Улицы выпрямлены.")