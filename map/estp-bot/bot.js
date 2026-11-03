const { chromium } = require('playwright');
const readline = require('readline');

const CONFIG = {
    // --- астройки для СТ (estp.dgkh.msk.ru) ---
    btnOpenTicket: '#popup_btn_estp',           
    inputEmployee: '#estp_contact_string',      
    selectIssueType: '#estp_request_sla_form-control', 
    inputText: '#estp_request_text',            
    btnSubmit: '#estp_button_apply',            
    btnCancel: 'button:has-text("тмена")',     
    EMPLOYEE_NAME: 'ванов алерий 89099479475',
    MAX_HOURS_NO_CONNECTION: 2, 

    // --- астройки для ТС (ets.mos.ru) ---
    // ы пока не знаем точных селекторов таблицы, поэтому бот 
    // будет использовать текстовый поиск. ам нужно будет их уточнить.
    etsLoginUrl: 'https://ets.mos.ru/#/login',
    etsMissionsUrl: 'https://ets.mos.ru/#/missions/missions',
    
    // --- астройки для СТ (арта) ---
    estpTelemetryUrl: 'https://estp.dgkh.msk.ru/index.php?r=telemetry'
};

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const askQuestion = (query) => new Promise(resolve => rl.question(query, resolve));

async function runBot() {
    console.log('🤖 апуск бота...');
    // апускаем браузер, чтобы вы видели процесс
    const browser = await chromium.launch({ headless: false }); 
    
    // Создаем  разных контекста, чтобы не терять сессии на разных сайтах
    const contextEts = await browser.newContext();
    const pageEts = await contextEts.newPage();
    
    const contextEstp = await browser.newContext();
    const pageEstp = await contextEstp.newPage();

    try {
        // --- Т 1: ТЯ  Х СТХ ---
        console.log('🔑 ткрываем ТС для сбора заданий...');
        await pageEts.goto(CONFIG.etsLoginUrl); 
        
        console.log('🔑 ткрываем СТ для создания заявок...');
        await pageEstp.goto(CONFIG.estpTelemetryUrl);

        console.log('⏳  40 С.  вас  окна браузера. ожалуйста, авторизуйтесь в Х (введите логин/пароль или войдите через осуслуги).');
        await pageEts.waitForTimeout(40000); 

        // --- Т 2: С СС Ш С ТС ---
        console.log('\n📊 ереход к урналу заданий на ТС...');
        await pageEts.goto(CONFIG.etsMissionsUrl);
        // дем загрузки таблицы (пока просто ждем 5 сек, так как не знаем точный ID таблицы)
        await pageEts.waitForTimeout(5000); 
        
        console.log('🔍 Собираем номера машин из урнала заданий...');
        
        // Я Ш: сли на ТС машины отображаются как "12377", 
        // Playwright может найти их по регулярному выражению.
        // ам нужно будет уточнить, как они выглядят в таблице.
        const plates = await pageEts.evaluate(() => {
            const text = document.body.innerText;
            // щем российские номера: 1 буква, 3 цифры, 2 буквы, 2-3 цифры
            const regex = /[-Я][0-9]{3}[-Я]{2}[0-9]{2,3}/g;
            const matches = text.match(regex);
            return matches ? [...new Set(matches)] : []; // бираем дубликаты
        });

        console.log(`✅ айдено машин: ${plates.length}. Список:`, plates);

        if (plates.length === 0) {
            console.log('⚠️ ашины не найдены. озможно, изменился формат номеров или таблица загрузилась не полностью.');
            // сли не нашли, ставим тестовые, чтобы проверить механику
            plates.push('462877'); 
        }

        // --- Т 3:   С Я (СТ) ---
        console.log('\n🚀 ереходим к созданию заявок на СТ...');
        // бедимся, что мы на карте
        await pageEstp.bringToFront();

        for (const plate of plates) {
            console.log(`\n===========================================`);
            console.log(`🚚 роверка машины: ${plate}`);
            
            try {
                // лик по машине в списке справа (Playwright умеет искать по тексту)
                const vehicleLocator = pageEstp.locator(`text="${plate}"`).first();
                await vehicleLocator.waitFor({ state: 'visible', timeout: 10000 });
                await vehicleLocator.click();
                
                await pageEstp.waitForSelector(CONFIG.btnOpenTicket, { timeout: 5000 });

                // тение времени коннекта
                const lastConnectRow = pageEstp.locator('tr:has-text("оследний коннект")').first();
                const lastConnectText = await lastConnectRow.locator('td').nth(1).innerText();
                console.log(`   🕒 ремя последнего коннекта: ${lastConnectText}`);

                const lastConnectDate = new Date(lastConnectText.trim());
                const now = new Date();
                const hoursDiff = (now - lastConnectDate) / (1000 * 60 * 60);

                let issueType = null;
                let comment = '';

                if (hoursDiff > CONFIG.MAX_HOURS_NO_CONNECTION) {
                    console.log(`   ⚠️ Т: ет связи ${hoursDiff.toFixed(1)} ч.`);
                    issueType = 'роведение работ по восстановлению неработающего С';
                    comment = `ашина не выходит на связь с ${lastConnectText.trim()}`;
                } else {
                    console.log(`   ✅ Связь в норме (${hoursDiff.toFixed(1)} ч. назад).`);
                    await pageEstp.keyboard.press('Escape'); 
                    continue; 
                }

                // аполнение формы
                console.log(`   📝 ормирование заявки...`);
                await pageEstp.click(CONFIG.btnOpenTicket); 
                await pageEstp.waitForSelector(CONFIG.inputEmployee);

                // ыбор сотрудника
                await pageEstp.click(CONFIG.inputEmployee);
                await pageEstp.fill(CONFIG.inputEmployee, ''); 
                await pageEstp.type(CONFIG.inputEmployee, CONFIG.EMPLOYEE_NAME, { delay: 50 }); 
                await pageEstp.waitForTimeout(1000); 
                await pageEstp.keyboard.press('Enter'); 
                
                // ыбор классификации
                await pageEstp.selectOption(CONFIG.selectIssueType, { label: issueType });
                
                // вод текста
                await pageEstp.fill(CONFIG.inputText, comment);

                // добрение
                console.log(`\n👀  . роверьте окно браузера (СТ)!`);
                const answer = await askQuestion(`тправить заявку по машине ${plate}? (y/n): `);
                
                if (answer.toLowerCase() === 'y') {
                    console.log(`   📤 тправка...`);
                    await pageEstp.click(CONFIG.btnSubmit);
                    await pageEstp.waitForTimeout(2000); 
                    console.log(`   ✅ аявка отправлена!`);
                    await pageEstp.keyboard.press('Escape'); 
                } else {
                    console.log(`   ❌ тменено.`);
                    await pageEstp.click(CONFIG.btnCancel);
                    await pageEstp.keyboard.press('Escape');
                }
            } catch (err) {
                console.error(`   ❌ шибка при обработке машины ${plate}:`, err.message);
                await pageEstp.keyboard.press('Escape');
            }
        }
        console.log('\n🏁 абота завершена.');
    } catch (error) {
        console.error('❌ ритическая ошибка:', error);
    } finally {
        rl.close();
        await browser.close();
    }
}

runBot();
