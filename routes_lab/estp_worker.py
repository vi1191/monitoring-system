# estp_worker.py
import time
from playwright.sync_api import sync_playwright

# SLA name -> numeric code expected by the ESTP form.
# 14 = track problems ("Некорректный трек ТС"), 10 = everything else.
def sla_code(sla_type):
    return "14" if "Некорректный" in (sla_type or "") else "10"


def run_estp_dry_run(cars_list, login_str, password_str, employee_str, on_progress=None):
    def report(msg):
        print(msg, flush=True)
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    report(f"--- Запуск ЕСТП (API-режим). Машин к отправке: {len(cars_list)} ---")
    
    with sync_playwright() as p:
        # headless=True — браузер работает в фоне
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # 1. Авторизация
            page.goto("https://estp.dgkh.msk.ru/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.fill('input[type="text"]', login_str)
            page.fill('input[type="password"]', password_str)
            page.click('button[type="submit"]')
            page.wait_for_timeout(5000) 
            
            # 2. Переход в Телеметрию
            page.goto("https://estp.dgkh.msk.ru/index.php?r=telemetry", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # 3. Выбор организации
            print("Выбираем организацию 'Жилищник Тропарево-Никулино'...")
            try:
                page.evaluate("document.querySelector('#car_org_chosen a.chosen-single').click()")
                page.wait_for_timeout(1000)
                page.evaluate('''
                    var options = document.querySelectorAll('#car_org_chosen .chosen-results li');
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].innerText.includes("Тропарево-Никулино")) {
                            options[i].click();
                            break;
                        }
                    }
                ''')
                page.wait_for_timeout(2000)
                print("Организация выбрана.")
            except Exception as e:
                print(f"! Не удалось выбрать организацию: {e}")
            
            # 4. Цикл по машинам
            results = []
            for index, car_data in enumerate(cars_list):
                gov = car_data['gov_number']
                sla_type = car_data.get('sla', 'Некорректный трек ТС')
                comment = car_data.get('comment', '')
                res_row = {"plate": gov, "sla": sla_type, "ok": False, "message": ""}
                results.append(res_row)
                done = index + 1

                report(f"[{done}/{len(cars_list)}] Отправка для {gov}...")
                if on_progress:
                    try:
                        on_progress({"done": done, "total": len(cars_list),
                                     "plate": gov, "phase": "start"})
                    except Exception:
                        pass
                
                try:
                    # Ищем машину
                    search_input = page.locator('input[name="search_ts"]')
                    search_input.fill(gov)
                    page.wait_for_timeout(1500)
                    
                    # Получаем ID машины и CSRF-токен (БЕЗ return)
                    result = page.evaluate(f'''
                        (function() {{
                            var links = document.querySelectorAll('a.reg_num');
                            var foundId = null;
                            for (var i = 0; i < links.length; i++) {{
                                if (links[i].innerText.includes("{gov}")) {{
                                    var nameAttr = links[i].getAttribute('name');
                                    if (nameAttr) {{
                                        foundId = nameAttr.split('_').pop();
                                    }}
                                    break;
                                }}
                            }}
                            
                            var csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || 
                                            document.querySelector('input[name="_csrf"]')?.value;
                            
                            return {{ id: foundId, csrf: csrfToken }};
                        }})()
                    ''')
                    
                    request_id = result.get('id') if result else None
                    csrf_token = result.get('csrf') if result else None
                    
                    if not request_id:
                        report(f"  ! Не найден ID для {gov}")
                        res_row["message"] = "ТС не найдено в ЕСТП"
                        continue
                    
                    if not csrf_token:
                        report(f"  ! Не найден CSRF-токен для {gov}")
                        res_row["message"] = "нет CSRF-токена"
                        continue
                    
                    report(f"  Найден ID: {request_id}")
                    
                    # Формируем данные с CSRF-токеном
                    form_data = {
                        '_csrf': csrf_token,
                        'request[id]': request_id,
                        'request[sla]': sla_code(sla_type),
                        'request[text]': comment,
                        'request[gauge]': '1',
                        'request[base]': '423',
                        'request[contact]': employee_str
                    }
                    
                    # Отправляем запрос через page.request
                    response = page.request.post(
                        "https://estp.dgkh.msk.ru/index.php?r=telemetry/create-estp-request",
                        form=form_data
                    )
                    
                    if response.status == 200:
                        try:
                            # Пытаемся прочитать JSON-ответ
                            json_resp = response.json()
                            if json_resp.get("error") == 0:
                                # Если error == 0, значит заявка создана
                                msg = json_resp.get("output", "Заявка создана")
                                report(f"  ✅ {gov}: {msg}")
                                res_row["ok"] = True
                                res_row["message"] = msg
                            else:
                                msg = json_resp.get("output", "Неизвестная ошибка")
                                report(f"  ❌ {gov}: {msg}")
                                res_row["message"] = msg
                        except Exception:
                            # Если ответ не JSON, проверяем как текст
                            text = response.text()
                            if "успешно" in text.lower():
                                report(f"  ✅ Заявка для {gov} создана (текстовый ответ).")
                                res_row["ok"] = True
                                res_row["message"] = "заявка создана"
                            else:
                                report(f"  ! {gov}: неизвестный ответ {text[:120]}")
                                res_row["message"] = text[:120]
                    else:
                        report(f"  ! {gov}: HTTP {response.status}")
                        res_row["message"] = f"HTTP {response.status}"
                        
                    if on_progress:
                        try:
                            on_progress({"done": done, "total": len(cars_list),
                                         "plate": gov, "phase": "done",
                                         "ok": res_row["ok"],
                                         "message": res_row["message"]})
                        except Exception:
                            pass
                    page.wait_for_timeout(500)
                    
                except Exception as e:
                    report(f"  ! Ошибка при отправке для {gov}: {e}")
                    res_row["message"] = str(e)[:120]
            
            report("Все заявки обработаны.")
            return results
            
        except Exception as e:
            report(f"Критическая ошибка: {e}")
            raise
        finally:
            browser.close()