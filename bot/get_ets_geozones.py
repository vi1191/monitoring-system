# get_ets_geozones.py (расширенный перебор)
import json
import os
import requests
from playwright.sync_api import sync_playwright

try:
    from auth import load_credentials
    from config import ETS_LOGIN_URL
except ImportError:
    print("Ошибка: не найдены файлы auth.py или config.py.")
    exit(1)

OUTPUT_FILE = "../map_clean/road_areas_raw.geojson"

def fetch_geozones():
    login_str, password_str = load_credentials()
    if not login_str or not password_str:
        print("Нет логинов ЕТС.")
        return

    print("Запуск браузера для получения токена...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Логин в ЕТС...")
        page.goto(ETS_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.fill("input[name='login'], input[placeholder*='огин']", login_str)
        page.fill("input[type='password']", password_str)
        page.click("button[type='submit'], button:has-text('Войти')")
        page.wait_for_timeout(5000)

        raw_token = page.evaluate("() => localStorage.getItem('ets.mos.ru/-ets-session')")
        token = raw_token.strip('"').replace('\\"', '').strip('"') if raw_token else None
        browser.close()

    if not token:
        print("❌ Не удалось получить токен.")
        return

    print("✅ Токен получен. Запрашиваю данные...")
    headers = {"Authorization": f"Token {token}"}

    # 1. ОДХ
    print("Запрашиваю ОДХ (МКАД)...")
    odh_data = []
    try:
        res = requests.get("https://ets.mos.ru/services/geozones/odh_mkad", headers=headers, timeout=30)
        if res.status_code == 200:
            data = res.json()
            odh_data.extend(data.get("result", {}).get("rows", []))
            print(f"✅ ОДХ: {len(odh_data)}")
    except Exception as e:
        print(f"Ошибка ОДХ: {e}")

    # 2. Муниципальные (ДТ) — расширенный перебор (mf 1-10, obj 1-10)
    print("Запрашиваю Муниципальные (ДТ) с расширенным перебором...")
    mun_data = []
    seen_ids = set()

    for mf_id in range(1, 11):
        for obj_id in range(1, 11):
            url = f"https://ets.mos.ru/services/geozone_municipal_facility?municipal_facility_id={mf_id}&technical_operation_id=198&object_type_id={obj_id}&structure_id=null&work_type_code=1&limit=1000"
            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list):
                        rows = data
                    elif isinstance(data, dict):
                        res_data = data.get("result", {})
                        if isinstance(res_data, list):
                            rows = res_data
                        elif isinstance(res_data, dict):
                            rows = res_data.get("rows", [])
                        else:
                            rows = []
                    else:
                        rows = []
                    
                    for row in rows:
                        row_id = row.get("id") or row.get("municipal_facility_id") or row.get("name")
                        if row_id and row_id not in seen_ids:
                            seen_ids.add(row_id)
                            mun_data.append(row)
                    
                    if rows:
                        print(f"  mf={mf_id}, obj={obj_id}: {len(rows)} (всего: {len(mun_data)})")
            except:
                pass

    print(f"✅ Муниципальные (итого уникальных): {len(mun_data)}")

    if not odh_data and not mun_data:
        print("❌ Ничего не получено.")
        return

    features = []

    # ОДХ
    for zone in odh_data:
        shape_str = zone.get("shape_json")
        if not shape_str: continue
        try:
            geom = json.loads(shape_str)
            if geom["type"] == "Polygon":
                features.append({"type": "Feature", "properties": {"name": zone.get("name", "Без названия"), "type": "ODH"}, "geometry": {"type": "Polygon", "coordinates": [geom["coordinates"][0]]}})
            elif geom["type"] == "MultiPolygon":
                for poly in geom["coordinates"]:
                    features.append({"type": "Feature", "properties": {"name": zone.get("name", "Без названия"), "type": "ODH"}, "geometry": {"type": "Polygon", "coordinates": [poly[0]]}})
        except: pass

    # Муниципальные
    for zone in mun_data:
        shape_str = zone.get("shape_json") or zone.get("shape")
        if not shape_str: continue
        try:
            geom = json.loads(shape_str)
            name = zone.get("municipal_facility_name", zone.get("name", "Без названия"))
            if geom["type"] == "Polygon":
                features.append({"type": "Feature", "properties": {"name": name, "type": "MUNICIPAL"}, "geometry": {"type": "Polygon", "coordinates": [geom["coordinates"][0]]}})
            elif geom["type"] == "MultiPolygon":
                for poly in geom["coordinates"]:
                    features.append({"type": "Feature", "properties": {"name": name, "type": "MUNICIPAL"}, "geometry": {"type": "Polygon", "coordinates": [poly[0]]}})
        except: pass

    geojson_data = {"type": "FeatureCollection", "features": features}
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Готово! Сохранено {len(features)} полигонов (ОДХ: {len(odh_data)}, Муниципальные: {len(mun_data)})")

if __name__ == "__main__":
    fetch_geozones()