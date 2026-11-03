# estp_worker.py
import time
from playwright.sync_api import sync_playwright

def run_estp_dry_run(car_data, login_str, password_str, employee_str):
    """
    Безопасный режим. Открывает ЕСТП, находит машину, заполняет форму,
    но НЕ нажимает кнопку "Отправить заявку".
    """
    print(f"--- Запуск ЕСТП для {car_data['gov_number']} ---")
    
    with sync_playwright() as p:
        # headless=False обязателен! Нам нужно видеть окно
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # 1. Авторизация
            page.goto("https://estp.dgkh.msk.ru/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            
            # На скриншотах не видно полей логина, предполагаем стандартные селекторы.
            # Если логин не вставляется - мы поправим селекторы позже.
            page.fill('input[type="text"]', login_str)
            page.fill('input[type="password"]', password_str)
            page.click('button[type="submit"]')
            page.wait_for_timeout(4000) # Ждем загрузки главной страницы
            
            # 2. Переход в Телеметрию
            page.goto("https://estp.dgkh.msk.ru/index.php?r=telemetry", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # 3. Поиск машины
            gov = car_data['gov_number']
            page.fill('input[name="search_ts"]', gov)
            page.press('input[name="search_ts"]', 'Enter')
            page.wait_for_timeout(2000)
            
            # Кликаем по первой найденной машине в списке
            car_link = page.locator('a.car_reg_num').first
            car_link.click()
            page.wait_for_timeout(2000)
            
            # 4. Открываем окно "Заявка на сервис"
            page.click('button#popup_btn_estp')
            page.wait_for_timeout(1000)
            
            # 5. Заполняем поля
            # Вставляем сотрудника
            page.fill('input#estp_contact_string', employee_str)
            
            # Определяем тип заявки на основе данных из ЕТС
            problem = car_data.get('problem_type', '')
            
            if 'Некорректное местоположение' in problem or 'Некорректный трек' in problem:
                page.select_option('select#estp_request_sla', label='Некорректный трек ТС')
                text_to_fill = "некорректное местоположение ТС"
            elif 'БНСО' in problem or 'не на связи' in problem:
                page.select_option('select#estp_request_sla', label='Проведение работ по восстановлению неработающего БНСО')
                text_to_fill = "машина не выходит на связь"
            else:
                text_to_fill = "Требуется проверка" # fallback
                
            page.fill('textarea#estp_request_text', text_to_fill)
            
            # ВАЖНО: Окно остается открытым! 
            # Бот ждет 60 секунд, чтобы вы успели посмотреть, и закрывает браузер.
            print("Форма заполнена! У вас есть 60 секунд, чтобы проверить её.")
            page.wait_for_timeout(60000)
            
        except Exception as e:
            print(f"Ошибка при работе с ЕСТП: {e}")
        finally:
            browser.close()