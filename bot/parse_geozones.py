import json
import math
import os

def mercator_to_geo(x, y):
    """Пересчет из метров Меркатора в градусы"""
    R = 6378137.0
    lon = (x / R) * (180.0 / math.pi)
    lat = (2 * math.atan(math.exp(y / R)) - math.pi / 2) * (180.0 / math.pi)
    return [lat, lon]

def parse_geozones():
    print("Чтение файла ets_geozones.json...")
    with open("bot/ets_geozones.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # Данные лежат в поле 'result'
    geozones = data.get('result', [])
    print(f"Найдено объектов: {len(geozones)}")

    all_features = []

    for i, zone in enumerate(geozones):
        name = zone.get('name', f"Объект {i}")
        shape_str = zone.get('shape')
        
        if not shape_str:
            print(f"[{i+1}] {name}: нет поля 'shape', пропускаем.")
            continue

        print(f"[{i+1}/{len(geozones)}] {name}: обработка...")

        try:
            # shape_str - это строка JSON
            shape_data = json.loads(shape_str)
            geom_type = shape_data.get('type')
            coords = shape_data.get('coordinates')

            if geom_type == 'Polygon':
                # Полигон: координаты первого контура
                for ring in coords:
                    geo_ring = [mercator_to_geo(x, y) for x, y in ring]
                    all_features.append({
                        "name": name,
                        "coords": geo_ring,
                        "type": "polygon"
                    })
            elif geom_type == 'MultiPolygon':
                # Мультиполигон: перебираем все полигоны
                for poly in coords:
                    for ring in poly:
                        geo_ring = [mercator_to_geo(x, y) for x, y in ring]
                        all_features.append({
                            "name": name,
                            "coords": geo_ring,
                            "type": "polygon"
                        })
            else:
                print(f"  Неизвестный тип геометрии: {geom_type}")

        except Exception as e:
            print(f"  Ошибка: {e}")

    # Сохраняем результат
    output_data = {
        "type": "FeatureCollection",
        "features": all_features
    }
    
    os.makedirs("map_clean", exist_ok=True)
    with open("map_clean/streets_ets.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False)
        
    print(f"Готово! Сохранено {len(all_features)} полигонов в map_clean/streets_ets.json")

if __name__ == "__main__":
    parse_geozones()