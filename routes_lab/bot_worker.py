# bot_worker.py
import sys
import time
import json
import os
import math
import requests
import concurrent.futures
from datetime import datetime, timedelta

from PyQt6.QtCore import QThread, pyqtSignal
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from auth import load_credentials
from ets_stream import EtsStream
from config import (
    CACHE_FILE,
    ETS_LOGIN_URL,
    ETS_MAP_URL,
)

LOGIN_INPUT = "input[name='login'], input[placeholder*='огин'], input[placeholder*='Логин']"
PASS_INPUT  = "input[type='password']"
SUBMIT_BTN  = "button[type='submit'], button:has-text('Войти'), button:has-text('Вход')"

# --- Параметры анализа ---
BASE_LAT, BASE_LON = 55.667, 37.432
BASE_RADIUS_KM = 3.0
BNSO_HOURS = 4
BNSO_WARN_HOURS = 2
MAX_REAL_DISTANCE_KM = 10

MIN_DT_SEC = 5
MIN_DIST_KM = 0.1

TP_SPEED_KMH = 100
TP_SPEED_DIST_KM = 2
TP_BIG_JUMP_KM = 5
TP_BIG_JUMP_SEC = 600

_log_counter = 0

def log(level: str, msg: str):
    global _log_counter
    _log_counter += 1
    ts = time.strftime("%H:%M:%S")
    stream = sys.stderr if level in ("ERR", "WARN") else sys.stdout
    print(f"[{_log_counter:03d}] {ts} {level:4s} | {msg}", file=stream, flush=True)


class BotWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    status_msg = pyqtSignal(str)

    def __init__(self, target_date: str = None):
        super().__init__()
        self.target_date = target_date if target_date else datetime.now().strftime("%Y-%m-%d")

    def run(self):
        global _log_counter
        _log_counter = 0

        t_start = time.time()
        t_stage = t_start

        def stage(name: str):
            nonlocal t_stage
            now = time.time()
            dt = now - t_stage
            log("INFO", f"{name}: OK ({dt:.1f} сек)")
            t_stage = now

        try:
            login_str, password_str = load_credentials()
            if not login_str or not password_str:
                self.error.emit("Нет сохранённых логинов ЕТС.")
                return

            cache = {}
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:
                    cache = {}

            stream = EtsStream()
            captured_missions = []
            captured_cars = []

            def on_response(response):
                if "/services/mission?" in response.url and "is_archive=false" in response.url:
                    try:
                        result = response.json().get("result", {})
                        rows = result.get("rows", []) if isinstance(result, dict) else []
                        if rows:
                            captured_missions.extend(rows)
                    except Exception:
                        pass
                if "car_actual" in response.url:
                    try:
                        rows = response.json().get("result", {}).get("rows", [])
                        if rows:
                            captured_cars.clear()
                            captured_cars.extend(rows)
                    except Exception:
                        pass

            with sync_playwright() as p:
                log("INFO", f"Запуск браузера (Дата: {self.target_date})...")
                self.status_msg.emit("Запуск браузера...")
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context()
                page = ctx.new_page()
                page.set_default_timeout(30000)
                page.on("websocket", stream.on_ws)
                page.on("response", on_response)

                # --- Логин ---
                log("INFO", "Логин в ЕТС...")
                self.status_msg.emit("Логин в ЕТС...")
                page.goto(ETS_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
                try:
                    page.fill(LOGIN_INPUT, login_str)
                    page.fill(PASS_INPUT, password_str)
                    page.click(SUBMIT_BTN)
                except PWTimeout:
                    self.error.emit("Не найдены поля логина.")
                    browser.close()
                    return
                page.wait_for_timeout(5000)
                if "/login" in page.url:
                    self.error.emit("Логин не удался.")
                    browser.close()
                    return
                stage("Логин")

                # --- Карта: WS + car_actual ---
                log("INFO", "Карта: собираю WS и car_actual...")
                self.status_msg.emit("Карта: собираю WS и car_actual...")
                try:
                    page.goto(ETS_MAP_URL)
                except Exception:
                    pass
                page.wait_for_timeout(12000)
                
                # --- Журнал заданий ---
                log("INFO", "Журнал заданий: загружаю...")
                date_start = f"{self.target_date}T00:00:00"
                date_end = f"{self.target_date}T23:59:59"
                journal_url = f"https://ets.mos.ru/#/missions/missions?date_start={date_start}&date_end={date_end}"

                page.goto(journal_url)
                page.wait_for_timeout(5000)

                # Ждем, пока прогрузится уведомление (если есть)
                try:
                    page.locator("#notifiaction_orders").wait_for(state="hidden", timeout=5000)
                except Exception:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)

                log("INFO", "Журнал: данные получены из потока (пагинация не требуется)")

                # --- ПРЯМОЙ ЗАПРОС К API ДЛЯ ПОЛУЧЕНИЯ ВСЕХ МИССИЙ ---
                raw_token = page.evaluate("() => localStorage.getItem('ets.mos.ru/-ets-session')")
                token = raw_token.strip('"').replace('\\"', '').strip('"') if raw_token else None
                
                if token:
                    target_dt = datetime.strptime(self.target_date, "%Y-%m-%d")
                    yesterday = (target_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                    
                    filters_json = json.dumps({
                        "date_start_gte": yesterday,
                        "date_start_lte": self.target_date
                    })
                    
                    api_url = f"https://ets.mos.ru/services/mission?is_archive=false&filters={filters_json}"
                    
                    log("INFO", f"Запрашиваю все миссии за {self.target_date} через API (без лимитов)...")
                    
                    res = page.request.get(api_url, headers={"Authorization": f"Token {token}"})
                    
                    if res.status == 200:
                        json_data = res.json()
                        rows = json_data.get("result", {}).get("rows", [])
                        if rows:
                            captured_missions.clear()
                            captured_missions.extend(rows)
                            log("INFO", f"API: получено {len(rows)} миссий за {self.target_date}")
                        else:
                            log("WARN", "API вернул пустой список миссий")
                    else:
                        log("WARN", f"API вернул статус {res.status}")

                # --- ФИЛЬТРАЦИЯ МИССИЙ ПО ДАТЕ И СТАТУСУ ---
                unique_missions = {str(m.get("id")): m for m in captured_missions}
                all_missions = list(unique_missions.values())

                target_day_start = datetime.strptime(self.target_date, "%Y-%m-%d")
                target_day_end = target_day_start.replace(hour=23, minute=59, second=59)

                target_missions = []
                for m in all_missions:
                    if m.get("is_archive"):
                        continue
                    
                    try:
                        d_start = datetime.fromisoformat(m.get("date_start", "").replace("Z", "+00:00")).replace(tzinfo=None)
                        d_end = datetime.fromisoformat(m.get("date_end", "").replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        continue
                    
                    if not (d_start <= target_day_end and d_end >= target_day_start):
                        continue
                    
                    if m.get("waybill_status") and m.get("waybill_status") not in ("active", "closed"):
                        continue
                    
                    target_missions.append(m)

                target_missions.sort(key=lambda m: str(m.get("id", "")), reverse=True)

                log("INFO", f"Миссий всего: {len(all_missions)}")
                log("INFO", f"Миссий активных на {self.target_date}: {len(target_missions)}")

                car_map = {}
                for row in captured_cars:
                    gov = str(row.get("gov_number", "")).strip()
                    if gov:
                        car_map[gov] = {
                            "gps_code": str(row.get("gps_code", "") or ""),
                            "garage_number": row.get("garage_number", "?"),
                            "model_name": row.get("model_name", "?"),
                        }

                target_cars = []
                seen_car_ids = set()
                for m in target_missions:
                    car_id = str(m.get("car_id", ""))
                    if not car_id or car_id in seen_car_ids:
                        continue
                    seen_car_ids.add(car_id)

                    gov = str(m.get("car_gov_number", "?")).strip()
                    info = car_map.get(gov)
                    gps = info["gps_code"] if info else ""

                    target_cars.append({
                        "car_id": car_id,
                        "mission_id": str(m.get("id", "")),
                        "order_number": m.get("order_number", "-"),
                        "gps_code": gps,
                        "gov_number": gov,
                        "garage_number": (info["garage_number"] if info else m.get("car_garage_number", "?")),
                        "model_name": (info["model_name"] if info else m.get("car_model_name", "?")),
                        "mission_status": m.get("status_name", "?"),
                        "percent": m.get("current_percentage", 0),
                        "distance": 0,
                        "fuel_start": "-",
                        "fuel_refuel": "-",
                        "fuel_refuel_detail": "-",
                        "fuel_fact": "-",
                        "track_status": "Норма",
                        "track_points": 0,
                        "valid_points": 0,
                        "teleports": 0,
                        "silent_min": None,
                        "track_detail": "-",
                        "_track_raw": [],
                        "_sensors_raw": None,
                    })

                # --- Треки ---
                tracks_ok = 0
                tracks_err = 0
                if target_cars:
                    if not token:
                        self.error.emit("Токен не найден.")
                    else:
                        from_dt = int(datetime.strptime(self.target_date, "%Y-%m-%d").timestamp())
                        to_dt = int((datetime.strptime(self.target_date, "%Y-%m-%d") + timedelta(days=1)).timestamp())

                        requests_js = []
                        for car in target_cars:
                            if car["car_id"]:
                                url = f"https://ets.mos.ru/tracks-caching/tracks?version=4&car_id={car['car_id']}&from_dt={from_dt}&to_dt={to_dt}&sensors=1"
                                requests_js.append({"url": url, "car_id": car["car_id"]})

                        total_reqs = len(requests_js)
                        self.status_msg.emit(f"Треки: 0/{total_reqs}")

                        batch_size = 10

                        def fetch_one(req):
                            try:
                                res = requests.get(
                                    req["url"],
                                    headers={"Authorization": f"Token {token}"},
                                    timeout=60
                                )
                                if res.status_code == 200:
                                    json_data = res.json()
                                    return {
                                        "car_id": req["car_id"],
                                        "status": 200,
                                        "track": json_data.get("track", []),
                                        "sensors_raw": json_data.get("cars_sensors"),
                                        "ets_fuel_start": json_data.get("sensor_start_value"),
                                        "ets_fuel_finish": json_data.get("sensor_finish_value"),
                                        "ets_fuel_refill": json_data.get("sensor_refill"),
                                        "raw_json": json_data
                                    }
                                else:
                                    return {"car_id": req["car_id"], "status": res.status_code, "track": [], "sensors_raw": None}
                            except Exception as e:
                                log("WARN", f"Ошибка запроса {req['car_id']}: {e}")
                                return {"car_id": req["car_id"], "status": 0, "track": [], "sensors_raw": None}

                        for i in range(0, total_reqs, batch_size):
                            batch = requests_js[i:i + batch_size]
                            
                            with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                                futures = {executor.submit(fetch_one, req): req for req in batch}
                                
                                for future in concurrent.futures.as_completed(futures):
                                    res = future.result()
                                    cid = res["car_id"]
                                    
                                    for car in target_cars:
                                        if car["car_id"] == cid:
                                            if res["status"] == 200:
                                                car["track_points"] = len(res["track"])
                                                car["_track_raw"] = res["track"]
                                                car["_sensors_raw"] = res.get("sensors_raw")
                                                car["_raw_json"] = res.get("raw_json")
                                                tracks_ok += 1
                                            else:
                                                car["track_status"] = "Ошибка API"
                                                car["track_detail"] = f"HTTP {res['status']}"
                                                tracks_err += 1
                                            break
                            
                            done = min(i + batch_size, total_reqs)
                            self.status_msg.emit(f"Треки: {done}/{total_reqs}")

                stage("Треки")
                browser.close()

            for gps_code, info in stream.states.items():
                ts = info.get("timestamp", 0)
                if ts and ts > 0:
                    cache[gps_code] = ts
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f)
            except Exception:
                pass

            # ============================================================
            # АНАЛИЗ
            # ============================================================
            self.status_msg.emit(f"Анализ: {len(target_cars)} машин...")
            t_analysis = time.time()
            offline_cars = []
            now_time = time.time()

            for car in target_cars:
                gps = car["gps_code"]
                info = stream.states.get(gps) if gps else None

                # ---------- СВЯЗЬ (БНСО) ----------
                silent_min = None
                if info:
                    ts = info.get("timestamp", 0)
                    if ts and ts > 0:
                        silent_min = (now_time - ts) / 60.0
                elif gps and gps in cache:
                    silent_min = (now_time - cache[gps]) / 60.0
                if silent_min is not None and silent_min > 24 * 60:
                    silent_min = None

                bnso_broken = silent_min is not None and silent_min > BNSO_HOURS * 60
                bnso_warn = silent_min is not None and silent_min > BNSO_WARN_HOURS * 60 and not bnso_broken
                bnso_no_data = (silent_min is None)

                # ---------- ТРЕК ----------
                track = car.get("_track_raw", [])
                total_pts = len(track)
                valid_points = [p for p in track if p.get("coords") and p["coords"][0] != 0 and p.get("is_valid", True)]
                valid_pts = len(valid_points)
                car["valid_points"] = valid_pts
                has_track = valid_pts >= 2
                low_valid = total_pts > 0 and valid_pts / total_pts < 0.3

                # ---------- ТЕЛЕПОРТЫ И ПРОБЕГ ----------
                teleports = 0
                tp_idx_set = set()
                teleport_details = []
                if has_track:
                    for j in range(valid_pts - 1):
                        p1, p2 = valid_points[j], valid_points[j + 1]
                        c1, c2 = p1["coords"], p2["coords"]
                        t1, t2 = p1.get("timestamp", 0) or 0, p2.get("timestamp", 0) or 0
                        dt = abs(t2 - t1)
                        if dt < MIN_DT_SEC: continue
                        dist_km = math.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2) * 111.0
                        if dist_km < MIN_DIST_KM: continue
                        speed_kmh = dist_km / (dt / 3600.0)
                        # Считаем телепортом ЛЮБОЙ скачок больше 1 км за < 10 минут ИЛИ больше 5 км
                        is_tp = (dist_km > 2.0 and dt < 300) or (dist_km > 10)
                        if is_tp:
                            teleports += 1
                            tp_idx_set.add(j + 1)
                            if len(teleport_details) < 3:
                                teleport_details.append(f"{dist_km:.0f}км/{dt//60}мин({speed_kmh:.0f}км/ч)")
                car["teleports"] = teleports

                distance_km = 0.0
                if has_track:
                    for j in range(valid_pts - 1):
                        if (j + 1) in tp_idx_set: continue
                        c1, c2 = valid_points[j]["coords"], valid_points[j + 1]["coords"]
                        d = math.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2) * 111.0
                        if d < 50: distance_km += d
                car["distance"] = round(distance_km, 1)
                last_dist_km = None
                last_on_base = False
                last_ts = 0
                is_fake_coords = False

                if has_track:
                    clean_points = [p for i, p in enumerate(valid_points) if i not in tp_idx_set]
                    if not clean_points: clean_points = valid_points
                    last = clean_points[-1]
                    lc = last["coords"]
                    last_ts = last.get("timestamp", 0) or 0
                    last_dist_km = math.sqrt((lc[0]-BASE_LAT)**2 + (lc[1]-BASE_LON)**2) * 111.0
                    last_on_base = last_dist_km < BASE_RADIUS_KM

                    if last_dist_km > MAX_REAL_DISTANCE_KM:
                        dists = [math.sqrt((p["coords"][0]-BASE_LAT)**2 + (p["coords"][1]-BASE_LON)**2) * 111.0 for p in clean_points]
                        if dists:
                            dists.sort()
                            median_d = dists[len(dists)//2]
                            if median_d < MAX_REAL_DISTANCE_KM or last_dist_km > 200 or teleports > 0:
                                is_fake_coords = True

                out_minutes = 0
                out_dist_km = None
                if has_track:
                    out_of_base_since = None
                    last_out_dist = None
                    for i, p in enumerate(valid_points):
                        if i in tp_idx_set: continue
                        coords, ts = p.get("coords"), p.get("timestamp")
                        if not coords or not ts: continue
                        d = math.sqrt((coords[0]-BASE_LAT)**2 + (coords[1]-BASE_LON)**2) * 111.0
                        if d < BASE_RADIUS_KM:
                            out_of_base_since = None
                            last_out_dist = None
                        else:
                            if out_of_base_since is None: out_of_base_since = ts
                            last_out_dist = d
                    if out_of_base_since is not None and last_ts:
                        out_minutes = int((last_ts - out_of_base_since) / 60)
                        out_dist_km = last_out_dist
                        
                # ---------- КЛАССИФИКАЦИЯ (ЖЕЛЕЗОБЕТОННАЯ) ----------
                # 1. Проверяем срывы (телепорты)
                has_teleports = teleports > 0
                
                # Проверка на улетевшие точки (дальше 100 км)
                has_far_points = False
                for p in car.get("_track_raw", []):
                    c = p.get("coords")
                    if c and len(c) == 2:
                        dist = math.sqrt((c[0]-BASE_LAT)**2 + (c[1]-BASE_LON)**2) * 111.0
                        if dist > 100:
                            has_far_points = True
                            break

                if has_teleports or has_far_points:
                    problem = "Некорректное местоположение ТС"
                    detail = f"срыв трека (телепортов: {teleports})" if teleports > 0 else "GPS-сбой"
                    
                # 2. Смотрим на количество точек трека
                elif valid_pts == 0:
                    # Точек вообще нет. Проверяем, есть ли связь с БНСО
                    if bnso_no_data or bnso_broken:
                        problem = "Машина не на связи"
                        detail = "нет трека, связи нет"
                    else:
                        # Связь есть, но точек нет (машина молчит по GPS)
                        problem = "Не работает БНСО"
                        detail = "не отображается трек (связь есть)"
                        
                # 3. Точки есть, но их мало (меньше 50)
                elif valid_pts < 50:
                    problem = "Не работает БНСО"
                    detail = f"не отображается трек (всего {valid_pts} точек)"
                    
                # 4. Всё в порядке (точек больше 50)
                else:
                    problem = "Норма"
                    detail = f"точек {valid_pts}/{total_pts}"
                    if last_on_base: 
                        detail += f", на базе ({last_dist_km:.1f} км)"
                    elif out_minutes > 0 and out_dist_km is not None: 
                        detail += f", на выезде {out_minutes} мин в {out_dist_km:.0f} км"
                    elif last_dist_km is not None: 
                        detail += f", последняя точка в {last_dist_km:.1f} км от базы"

                car["problem_type"] = problem
                car["track_detail"] = detail
                car["tech_to"] = "ОК"
                car["insurance"] = "ОК"
                offline_cars.append(car)

            offline_cars.sort(key=lambda x: (x["problem_type"] == "Норма", x["gov_number"]))

            # ============================================================
            # ФИНАЛЬНЫЙ ПАРСИНГ ТОПЛИВА
            # ============================================================
            for car in offline_cars:
                raw = car.get("_raw_json")
                if raw:
                    f_start = raw.get("sensor_start_value")
                    f_finish = raw.get("sensor_finish_value")
                    f_refill = raw.get("sensor_refill")

                    car["fuel_start"] = round(float(f_start), 1) if f_start is not None else "-"
                    car["fuel_fact"] = round(float(f_finish), 1) if f_finish is not None else "-"

                    if f_refill is not None and float(f_refill) > 0:
                        car["fuel_refuel"] = f"+{round(float(f_refill), 1)}"
                        car["fuel_refuel_detail"] = f"{round(float(f_refill), 1)} л (ЕТС)"
                    else:
                        car["fuel_refuel"] = "-"
                        car["fuel_refuel_detail"] = "-"
                else:
                    car["fuel_start"] = "-"
                    car["fuel_fact"] = "-"
                    car["fuel_refuel"] = "-"
                    car["fuel_refuel_detail"] = "-"

            t_total = time.time() - t_start
            t_analyze = time.time() - t_analysis

            log("INFO", f"Анализ: готово за {t_analyze:.1f} сек")
            log("INFO", "===== ИТОГИ =====")
            log("INFO", f"Машин в работе:      {len(target_cars)}")
            log("INFO", f"Треков получено:     {tracks_ok} / {len(target_cars)} ({tracks_err} ошибок)")
            log("INFO", f"Время сбора:         {t_total:.1f} сек")
            log("INFO", "==================")

            self.finished.emit(offline_cars)

        except Exception as e:
            log("ERR", f"Критическая ошибка: {type(e).__name__}: {e}")
            self.error.emit(f"{type(e).__name__}: {e}")