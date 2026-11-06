import requests
import json
import os

def download_one_street():
    street_name = "Академика Анохина"
    print(f"Запрос к OpenStreetMap для улицы: {street_name}...")
    
    # Ищем только эту улицу в Москве
    query = f"""
    [out:json][timeout:25];
    area["name"="Москва"]->.searchArea;
    way["name"~"{street_name}",i](area.searchArea);
    out geom;
    """
    
    headers = {
        'User-Agent': 'MonitoringSystem/1.0 (contact: vi1191@users.noreply.github.com)'
    }
    
    # Используем основной сервер, он обычно справляется с маленькими запросами
    url = "https://overpass-api.de/api/interpreter"
    
    try:
        print("Отправка запроса...")
        response = requests.get(url, params={'data': query}, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get('elements', [])
        print(f"Получено элементов: {len(elements)}")
        
        features = []
        for el in elements:
            if 'geometry' in el:
                name = el.get('tags', {}).get('name', 'Без названия')
                coords = [[pt['lat'], pt['lon']] for pt in el['geometry']]
                features.append({
                    "name": name,
                    "coords": coords
                })
        
        # Сохраняем в map_clean
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(current_dir, "..", "map_clean", "streets_osm.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
        
        print(f"✅ ГОТОВО! Найдено участков: {len(features)}")
        print(f"Файл сохранен: {output_file}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    download_one_street()