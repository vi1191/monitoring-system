import requests
import json
import os

def download_osm_streets():
    print("Запрос к российскому зеркалу OpenStreetMap (maps.mail.ru)...")
    
    # Район Тропарево-Никулино (Юг, Запад, Север, Восток)
    bbox = 55.6251, 37.4229, 55.6896, 37.5287
    
    # Запрашиваем все дороги (улицы, проезды) в этом квадрате
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"]({BBOX});
    );
    out geom;
    """
    
    headers = {
        'User-Agent': 'MonitoringSystem/1.0'
    }
    
    # РОССИЙСКОЕ ЗЕРКАЛО
    url = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    
    try:
        print(f"Отправка запроса для квадрата: {BBOX}")
        # Делаем POST-запрос (для больших запросов он надежнее)
        response = requests.post(url, data={'data': query}, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get('elements', [])
        print(f"Получено участков дорог: {len(elements)}")
        
        # Превращаем формат OSM в тот, который ждет ваш index.html
        features = []
        for el in elements:
            if 'geometry' in el:
                name = el.get('tags', {}).get('name', 'Без названия')
                
                # OSM отдает [lat, lon]. Нам нужно [lat, lon]
                coords = [[pt['lat'], pt['lon']] for pt in el['geometry']]
                
                features.append({
                    "name": name,
                    "coords": coords
                })
        
        # Сохраняем в папку map_clean
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(current_dir, "..", "map_clean", "streets_osm.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
        
        print(f"✅ ГОТОВО! Файл сохранен: {output_file}")
        print(f"Всего улиц: {len(features)}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    download_osm_streets()