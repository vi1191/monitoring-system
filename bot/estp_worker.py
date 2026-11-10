# estp_worker.py
import time
from playwright.sync_api import sync_playwright

def run_estp_dry_run(cars_list, login_str, password_str, employee_str):
    print(f"--- Запуск ЕСТП. Машин к отправке: {len(cars_list)} ---")
    
    with sync_playwright() as p:
        # headless=False обязателен, чтобы вы видели процесс
        browser = p.chromium.launch(headless=False) 
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
            page.wait_for_timeout(4000)
            
            # --- ВЫБОР ОРГАНИЗАЦИИ (через JS, так как это кастомный список) ---
            print("Выбираем организацию 'Жилищник Тропарево-Никулино'...")
            try:
                # Кликаем по выпадающему списку, чтобы он открылся
                page.evaluate("document.querySelector('#car_org_chosen a.chosen-single').click()")
                page.wait_for_timeout(1000)
                
                # Ищем в выпавшем списке нужный текст и кликаем по нему
                page.evaluate('''
                    var options = document.querySelectorAll('#car_org_chosen .chosen-results li');
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].innerText.includes("Тропарево-Никулино")) {
                            options[i].click();
                            break;
                        }
                    }
                ''')
                page.wait_for_timeout(3000) # Ждем, пока карта и список обновятся
                print("Организация выбрана.")
            except Exception as e:
                print(f"! Не удалось выбрать организацию: {e}")
            # -----------------------------------------------------------------
            
            # 3. Цикл по машинам
            for index, car_data in enumerate(cars_list):
                gov = car_data['gov_number']
                sla_type = car_data.get('sla', 'Другое')
                comment = car_data.get('comment', '')
                
                print(f"\n[{index+1}/{len(cars_list)}] Обработка {gov} (Тип: {sla_type})...")
                
                try:
                    # Поиск машины
                    search_input = page.locator('input[name="search_ts"]')
                    search_input.fill(gov)
                    page.wait_for_timeout(3000)
                    
                    # Находим элемент списка по тексту
                    car_item = page.locator(f'li:has-text("{gov}")').first
                    if car_item.count() == 0:
                        print(f"  ! Машина {gov} не найдена.")
                        continue
                        
                    car_item.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    
                    # Кликаем через JavaScript (игнорирует видимость и границы экрана)
                    print(f"  Кликаем по ссылке {gov} через JS...")
                    page.evaluate(f'''
                        var link = document.querySelector('a.reg_num[name*="car_reg_num"]');
                        if (link && link.innerText.includes("{gov}")) {{
                            link.click();
                        }} else {{
                            var allLinks = document.querySelectorAll('a.reg_num');
                            for (var i = 0; i < allLinks.length; i++) {{
                                if (allLinks[i].innerText.includes("{gov}")) {{
                                    allLinks[i].click();
                                    break;
                                }}
                            }}
                        }}
                    ''')
                    print(f"  Кликнули по машине {gov}. Ждем загрузки карточки...")
                    
                    # Ждем, пока в карточке появится номер машины
                    try:
                        page.wait_for_selector(f'th:has-text("Наименование") + td:has-text("{gov}")', timeout=10000)
                        print("  Карточка машины загружена.")
                    except:
                        print("  ! Карточка машины не загрузилась, но пробуем продолжить...")
                        
                    page.wait_for_timeout(2000)
                    
                    # Открываем окно заявки через JS
                    page.evaluate("document.querySelector('button#popup_btn_estp').click()")
                    page.wait_for_timeout(2000)
                    
                    # Заполняем поля
                    page.fill('input#estp_contact_string', employee_str)
                    page.select_option('select#estp_request_sla', label=sla_type)
                    page.fill('textarea#estp_request_text', comment)
                    page.wait_for_timeout(1000)
                    
                    # === ОТПРАВКА ===
                    print(f"  Заполнено. Отправляем...")
                    
                    # Скриншот ДО нажатия
                    page.screenshot(path=f"screenshot_before_{gov}.png")
                    
                    # Нажимаем кнопку "Отправить заявку"
                    page.click('button:has-text("Отправить заявку")')
                    print(f"  Кнопка 'Отправить' нажата. Ждем реакцию сайта...")
                    
                    page.wait_for_timeout(4000)
                    
                    # Скриншот ПОСЛЕ нажатия
                    page.screenshot(path=f"screenshot_after_{gov}.png")
                    
                    # Проверяем, не появилось ли всплывающее окно с подтверждением
                    try:
                        if page.locator('button:has-text("Да")').count() > 0:
                            page.locator('button:has-text("Да")').first.click()
                            print("  Нажато подтверждение 'Да'.")
                            page.wait_for_timeout(2000)
                    except:
                        pass
                        
                    print(f"  Заявка для {gov} обработана.")
                    
                except Exception as e:
                    print(f"  ! Ошибка при обработке {gov}: {e}")
                    # Перезагружаем страницу, чтобы начать заново
                    page.goto("https://estp.dgkh.msk.ru/index.php?r=telemetry", wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
            
            print("\nВсе заявки обработаны. Закрываем браузер...")
            page.wait_for_timeout(3000) 
            
        except Exception as e:
            print(f"Критическая ошибка: {e}")
        finally:
            browser.close()