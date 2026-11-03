# bot_worker.py
import sys
import time
import json
import os
import math
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
BASE_RADIUS_KM = 5.0
BNSO_HOURS = 4
BNSO_WARN_HOURS = 2
MAX_REAL_DISTANCE_KM = 60

MIN_DT_SEC = 5
MIN_DIST_KM = 0.1

TP_SPEED_KMH = 200
TP_SPEED_DIST_KM = 5
TP_BIG_JUMP_KM = 30
TP_BIG_JUMP_SEC = 300

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

                try:
                    page.locator("#notifiaction_orders").wait_for(state="hidden", timeout=5000)
                except Exception:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)

                log("INFO", "Журнал: переключаю на 100 строк...")
                try:
                    log("DEBUG", "1. Ищу селектор страниц...")
                    pag_opt = page.locator(".ant-pagination-options .ant-select").first
                    pag_opt.click()
                    log("DEBUG", "2. Кликнул селектор, жду 1 сек...")
                    page.wait_for_timeout(1000)

                    log("DEBUG", "3. Ищу опцию 100...")
                    option_100 = page.locator(".ant-select-item-option-content", has_text="100").first
                    option_100.wait_for(state="visible", timeout=5000)
                    log("DEBUG", "4. Опция видна, кликаю с ожиданием ответа...")

                    with page.expect_response(
                        lambda r: "/services/mission?" in r.url and "is_archive=false" in r.url,
                        timeout=15000,
                     ):
                        option_100.click()
                    log("DEBUG", "5. Ответ получен, жду 1 сек...")
                    page.wait_for_timeout(1000)
                except Exception as e:
                    log("WARN", f"Ошибка пагинации: {e}")
                    log("DEBUG", "Журнал: пагинация завершена, иду дальше")

                unique_missions = {str(m.get("id")): m for m in captured_missions}
                all_missions = list(unique_missions.values())
                target_missions = [m for m in all_missions if self.target_date in str(m.get("date_start") or "")]
                target_missions.sort(key=lambda m: str(m.get("id", "")), reverse=True)

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
                    raw_token = page.evaluate("() => localStorage.getItem('ets.mos.ru/-ets-session')")
                    token = raw_token.strip('"').replace('\\"', '').strip('"') if raw_token else None
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

                        import concurrent.futures

                        def fetch_track(req):
                            try:
                                res = page.request.get(req["url"], headers={"Authorization": f"Token {token}"})
                                if res.status == 200:
                                    json_data = res.json()
                                    return {
                                        "car_id": req["car_id"],
                                        "status": 200,
                                        "track": json_data.get("track", []),
                                        "sensors_raw": json_data.get("cars_sensors"),
                                        "ets_fuel_start": json_data.get("sensor_start_value"),
                                        "ets_fuel_finish": json_data.get("sensor_finish_value"),
                                        "ets_fuel_refill": json_data.get("sensor_refill")
                                    }
                                else:
                                    return {"car_id": req["car_id"], "status": res.status, "track": [], "sensors_raw": None}
                            except Exception as e:
                                log("WARN", f"Ошибка запроса {req['car_id']}: {e}")
                                return {"car_id": req["car_id"], "status": 0, "track": [], "sensors_raw": None}

                        # Запускаем параллельно по 5 штук
                        batch_size = 10
                        for i in range(0, total_reqs, batch_size):
                            batch = requests_js[i:i + batch_size]
                            results = []
                            for req in batch:
                                try:
                                    res = page.request.get(req["url"], headers={"Authorization": f"Token {token}"})
                                    if res.status == 200:
                                        json_data = res.json()
                                        results.append({
                                            "car_id": req["car_id"],
                                            "status": 200,
                                            "track": json_data.get("track", []),
                                            "sensors_raw": json_data.get("cars_sensors"),
                                            "ets_fuel_start": json_data.get("sensor_start_value"),
                                            "ets_fuel_finish": json_data.get("sensor_finish_value"),
                                            "ets_fuel_refill": json_data.get("sensor_refill"),
                                            "raw_json": json_data
                                        })
                                    else:
                                        results.append({"car_id": req["car_id"], "status": res.status, "track": [], "sensors_raw": None})
                                except Exception as e:
                                    log("WARN", f"Ошибка запроса {req['car_id']}: {e}")
                                    results.append({"car_id": req["car_id"], "status": 0, "track": [], "sensors_raw": None})
                            done = min(i + batch_size, total_reqs)
                            self.status_msg.emit(f"Треки: {done}/{total_reqs}")
                            
                            for res in results:
                                cid = res["car_id"]
                                for car in target_cars:
                                    if car["car_id"] == cid:
                                        if res["status"] == 200:
                                            car["track_points"] = len(res["track"])
                                            car["_track_raw"] = res["track"]
                                            car["_sensors_raw"] = res.get("sensors_raw")
                                            car["_ets_fuel_start"] = res.get("ets_fuel_start")
                                            car["_raw_json"] = res.get("raw_json")
                                            car["_ets_fuel_finish"] = res.get("ets_fuel_finish")
                                            car["_ets_fuel_refill"] = res.get("ets_fuel_refill")
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

                # ---------- ТОПЛИВО (ИЗ КОРНЯ ОТВЕТА ЕТС) ----------
                f_start = car.get("_ets_fuel_start")
                f_finish = car.get("_ets_fuel_finish")
                f_refill = car.get("_ets_fuel_refill")

                car["fuel_start"] = round(float(f_start), 1) if f_start is not None else "-"
                car["fuel_fact"] = round(float(f_finish), 1) if f_finish is not None else "-"

                if f_refill is not None and float(f_refill) > 0:
                    car["fuel_refuel"] = f"+{round(float(f_refill), 1)}"
                    car["fuel_refuel_detail"] = f"{round(float(f_refill), 1)} л (ЕТС)"
                else:
                    car["fuel_refuel"] = "-"
                    car["fuel_refuel_detail"] = "-"

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
                        is_tp = (speed_kmh > TP_SPEED_KMH and dist_km > TP_SPEED_DIST_KM) or (dist_km > TP_BIG_JUMP_KM and dt < TP_BIG_JUMP_SEC)
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
                        
                # ---------- КЛАССИФИКАЦИЯ ----------
                if is_fake_coords:
                    problem = "Некорректное местоположение ТС"
                    detail = f"GPS-сбой: последняя точка в {last_dist_km:.0f} км от базы"
                elif low_valid:
                    problem = "Некорректный трек"
                    detail = f"валидных {valid_pts}/{total_pts} ({valid_pts/total_pts*100:.0f}%)"
                elif not has_track:
                    # Если трека нет, проверяем связь
                    if bnso_no_data or bnso_broken:
                        problem = "Машина не на связи"
                        detail = "нет трека, связи нет" if bnso_no_data else f"нет трека, связь {int(silent_min/60)} ч"
                    else:
                        problem = "Некорректный трек"
                        detail = f"точек {valid_pts}/{total_pts}"
                elif teleports >= 1 and not last_on_base:
                    # Если трек есть, но есть телепорты, ставим сбой местоположения
                    problem = "Некорректное местоположение ТС"
                    parts = [f"телепортов {teleports}"]
                    if teleport_details: parts.append(f"({'; '.join(teleport_details)})")
                    if last_dist_km is not None: parts.append(f"последняя точка в {last_dist_km:.0f} км от базы")
                    detail = ", ".join(parts)
                elif bnso_broken and valid_pts < 10:
                    # БНСО ставим только если трек есть, но он совсем крошечный (машина просто пикнула и пропала)
                    problem = "Не работает БНСО"
                    detail = f"связь {int(silent_min/60)} ч, трек мал ({valid_pts} точек)"
                else:
                    # Если трек нормальный (много точек), но связь пропала, 
                    # мы ставим Норма, но в деталях пишем, что связи нет
                    problem = "Норма"
                    detail = f"точек {valid_pts}/{total_pts}"
                    if bnso_broken or bnso_warn:
                        detail += f", связь {int(silent_min/60)} ч"
                    if teleports > 0: detail += f", было телепортов {teleports}"
                    if last_on_base: detail += f", на базе ({last_dist_km:.1f} км)"
                    elif out_minutes > 0 and out_dist_km is not None: detail += f", на выезде {out_minutes} мин в {out_dist_km:.0f} км"
                    elif last_dist_km is not None: detail += f", последняя точка в {last_dist_km:.1f} км от базы"
                                # ПРИНУДИТЕЛЬНОЕ ЗАПОЛНЕНИЕ ТОПЛИВА ИЗ КОРНЯ
                f_start = car.get("_ets_fuel_start")
                f_finish = car.get("_ets_fuel_finish")
                f_refill = car.get("_ets_fuel_refill")

                car["fuel_start"] = round(float(f_start), 1) if f_start is not None else "-"
                car["fuel_fact"] = round(float(f_finish), 1) if f_finish is not None else "-"

                if f_refill is not None and float(f_refill) > 0:
                    car["fuel_refuel"] = f"+{round(float(f_refill), 1)}"
                    car["fuel_refuel_detail"] = f"{round(float(f_refill), 1)} л (ЕТС)"
                else:
                    car["fuel_refuel"] = "-"
                    car["fuel_refuel_detail"] = "-"
                car["problem_type"] = problem
                car["track_detail"] = detail
                car["tech_to"] = "ОК"
                car["insurance"] = "ОК"
                offline_cars.append(car)

            offline_cars.sort(key=lambda x: (x["problem_type"] == "Норма", x["gov_number"]))

            t_total = time.time() - t_start
            t_analyze = time.time() - t_analysis

            log("INFO", f"Анализ: готово за {t_analyze:.1f} сек")
            log("INFO", "===== ИТОГИ =====")
            log("INFO", f"Машин в работе:      {len(target_cars)}")
            log("INFO", f"Треков получено:     {tracks_ok} / {len(target_cars)} ({tracks_err} ошибок)")
            log("INFO", f"Время сбора:         {t_total:.1f} сек")
            log("INFO", "==================")

 # --- ФИНАЛЬНЫЙ ПАРСИНГ ТОПЛИВА ИЗ JSON ---
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

                # 2. Записываем в таблицу
                car["fuel_start"] = round(float(f_start), 1) if f_start is not None else "-"
                car["fuel_fact"] = round(float(f_finish), 1) if f_finish is not None else "-"

                if f_refill is not None and float(f_refill) > 0:
                    car["fuel_refuel"] = f"+{round(float(f_refill), 1)}"
                    car["fuel_refuel_detail"] = f"{round(float(f_refill), 1)} л (ЕТС)"
                else:
                    car["fuel_refuel"] = "-"
                    car["fuel_refuel_detail"] = "-"

            self.finished.emit(offline_cars)

        except Exception as e:
            log("ERR", f"Критическая ошибка: {type(e).__name__}: {e}")
            self.error.emit(f"{type(e).__name__}: {e}")