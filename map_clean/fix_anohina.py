import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(current_dir, "streets_ets.json")
output_file = os.path.join(current_dir, "streets_fixed.json")

print(f"✅ Читаю файл: {input_file}")
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# МАГИЧЕСКИЕ КОЭФФИЦИЕНТЫ ДЛЯ ВАШИХ ДАННЫХ
# X в вашем файле отвечает за долготу (Lon), Y - за широту (Lat)
# Эти числа подобраны так, чтобы улица Академика Анохина легла ровно на карту.

def convert_point(x, y):
    # Убираем лишние нули и подгоняем масштаб под Москву
    lat = 55.654 + (y / 1000000.0) 
    lon = 37.472 + (x / 1000000.0)
    return [lat, lon]

for feature in data.get("features", []):
    if "coords" in feature:
        feature["coords"] = [convert_point(pt[0], pt[1]) for pt in feature["coords"]]

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

print("✅ ГОТОВО! Теперь улицы должны встать ровно.")