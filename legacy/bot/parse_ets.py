import json
import math
import os

def parse_ets_json(input_file, output_file):
    print(f"Чтение файла: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Находим маршрут в ответе
    routes = data.get('result', [])
    if not routes:
        print("Ошибка: в файле нет данных о маршруте.")
        return

    route = routes[0]
    shapes = route.get('shapes', {})
    
    if not shapes:
        print("Ошибка: нет поля 'shapes' в маршруте.")
        return

    # Перебираем все объекты в shapes (там может быть несколько участков)
    all_geometries = []
    
    for obj_id, shape_str in shapes.items():
        try:
            # shape_str - это строка JSON, которую нужно распарсить
            shape_data = json.loads(shape_str)
            # Внутри лежит массив координат
            # Формат: {"coordinates": [[[x1, y1], [x2, y2], ...]], "type": "Polygon"}
            
            # Берем внешний контур полигона
            coords = shape_data['coordinates'][0] 
            
            # Пересчитываем из метров Меркатора в градусы
            # Формула для Web Mercator (EPSG:3857)
            # x = R * lon * pi / 180
            # y = R * ln(tan(pi/4 + lat * pi / 360))
            
            # R - радиус Земли (примерно 6378137 метров)
            R = 6378137.0
            
            geo_coords = []
            for x, y in coords:
                lon = (x / R) * (180.0 / math.pi)
                lat = (2 * math.atan(math.exp(y / R)) - math.pi / 2) * (180.0 / math.pi)
                geo_coords.append([lat, lon])
                
            all_geometries.append({
                "name": f"Участок {obj_id}",
                "coords": geo_coords
            })
            print(f"Обработан объект {obj_id}: {len(geo_coords)} точек.")
            
        except Exception as e:
            print(f"Ошибка при обработке объекта {obj_id}: {e}")

    # Сохраняем результат
    output_data = {
        "type": "FeatureCollection",
        "features": all_geometries
    }
    
    # Создаем папку, если ее нет
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False)
        
    print(f"Готово! Сохранено в {output_file}")

if __name__ == "__main__":
    # Пути к файлам
    input_path = "bot/ets_route.json"          # указываем путь от корня
    # Сохраняем в папку map_clean (на уровень выше)
    output_path = "map_clean/streets_ets.json" # указываем путь от корня
    
    parse_ets_json(input_path, output_path)