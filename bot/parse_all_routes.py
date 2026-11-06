import json
import requests
import math
import os

TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxMDUxMTEsImNvbXBhbnlfaWQiOjEwMjI2Njk0MCwiY29tcGFuaWVzX2lkcyI6WzEwMjI2Njk0MF0sImVudiI6InByb2QiLCJ0aW1lc3RhbXAiOjE3OTM4NzE3NTkuNTQ1NjI5NX0.KWz-r73Azv-xsccggBDExlJ1g_hibCw-J1-93_edigs"

def mercator_to_geo(x, y):
    R = 6378137.0
    lon = (x / R) * (180.0 / math.pi)
    lat = (2 * math.atan(math.exp(y / R)) - math.pi / 2) * (180.0 / math.pi)
    return [lat, lon]

def download_all_routes():
    with open("bot/ets_all_routes.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    routes = data.get('result', [])

    # Возьмем только первые 5 маршрутов для теста
    test_routes = routes[:5]
    
    headers = {
        "Authorization": f"Token {TOKEN}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    for i, route in enumerate(test_routes):
        route_id = route.get('id')
        route_name = route.get('name', 'Без имени')
        print(f"\n--- Тест маршрута {i+1}: {route_name} (ID: {route_id}) ---")

        url = f"https://ets.mos.ru/services/route?id={route_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                route_data = response.json()
                print("Ключи в ответе:", list(route_data.keys()))
                
                # Проверяем, есть ли result и shapes
                result = route_data.get('result')
                if result:
                    print("Тип result:", type(result))
                    if isinstance(result, dict):
                        print("Ключи в result:", list(result.keys()))
                        shapes = result.get('shapes')
                        if shapes:
                            print(f"НАЙДЕНЫ shapes! Количество объектов: {len(shapes)}")
                            # Для теста выведем первый shape
                            first_key = list(shapes.keys())[0]
                            print(f"Пример shape (первые 100 символов): {shapes[first_key][:100]}...")
                        else:
                            print("Поле 'shapes' отсутствует или пустое.")
                    elif isinstance(result, list):
                        print(f"Result - это список, длина: {len(result)}")
                else:
                    print("Поле 'result' отсутствует.")
            else:
                print(f"Ошибка HTTP: {response.status_code}")
                print("Текст ответа:", response.text[:200])
                
        except Exception as e:
            print(f"Исключение: {e}")

if __name__ == "__main__":
    download_all_routes()