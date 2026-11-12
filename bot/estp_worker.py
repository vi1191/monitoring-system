# estp_worker.py
import time
from playwright.sync_api import sync_playwright

def run_estp_dry_run(cars_list, login_str, password_str, employee_str):
    print(f"--- Запуск ЕСТП (API-режим). Машин к отправке: {len(cars_list)} ---")
    
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
            for index, car_data in enumerate(cars_list):
                gov = car_data['gov_number']
                sla_type = car_data.get('sla', 'Некорректный трек ТС')
                comment = car_data.get('comment', '')
                
                print(f"[{index+1}/{len(cars_list)}] Отправка для {gov}...")
                
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
                        print(f"  ! Не найден ID для {gov}")
                        continue
                    
                    if not csrf_token:
                        print(f"  ! Не найден CSRF-токен для {gov}")
                        continue
                    
                    print(f"  Найден ID: {request_id}, CSRF: {csrf_token[:10]}...")
                    
                    # Определяем код SLA
                    sla_code = "14" if "Некорректный" in sla_type else "10"
                    
                    # Формируем данные с CSRF-токеном
                    form_data = {
                        '_csrf': csrf_token,
                        'request[id]': request_id,
                        'request[sla]': sla_code,
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
                                print(f"  ✅ {msg}")
                            else:
                                print(f"  ❌ Ошибка: {json_resp.get('output', 'Неизвестная ошибка')}")
                        except Exception:
                            # Если ответ не JSON, проверяем как текст
                            text = response.text()
                            if "успешно" in text.lower():
                                print(f"  ✅ Заявка для {gov} создана (текстовый ответ).")
                            else:
                                print(f"  ! Неизвестный ответ: {text[:200]}")
                    else:
                        print(f"  ! Ошибка сервера: HTTP {response.status}")
                        
                    page.wait_for_timeout(500)
                    
                except Exception as e:
                    print(f"  ! Ошибка при отправке для {gov}: {e}")
            
            print("\nВсе заявки обработаны. Закрываем браузер...")
            
        except Exception as e:
            print(f"Критическая ошибка: {e}")
        finally:
            browser.close()