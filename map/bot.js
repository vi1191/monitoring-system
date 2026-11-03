import { chromium } from 'playwright';
import express from 'express';
import { analyzeWsData } from './ws-analysis.js';

const CONFIG = {
    // Настройки ЕСТП (для создания заявок)
    btnOpenTicket: '#popup_btn_estp',           
    inputEmployee: '#estp_contact_string',      
    selectIssueType: '#estp_request_sla_form-control', 
    inputText: '#estp_request_text',            
    btnSubmit: '#estp_button_apply',            
    EMPLOYEE_NAME: 'Иванов Валерий 89099479475',
    
    // Ссылки
    etsLoginUrl: 'https://ets.mos.ru/#/login',
    etsMissionsUrl: 'https://ets.mos.ru/#/missions/missions',
    estpTelemetryUrl: 'https://estp.dgkh.msk.ru/index.php?r=telemetry',
    
    // Координаты базы (Малая Очаковская, 8с4)
    BASE_LAT: 55.673, 
    BASE_LON: 37.455,
    MAX_DISTANCE_KM: 100,
    MAX_SPEED_KMH: 150,
};

let reportData = [];
let browser, pageEts, pageEstp;

// --- ВЕБ-СЕРВЕР ДЛЯ ОТЧЕТА ---
const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get('/', (req, res) => {
    let rows = reportData.map((item, index) => `
        <tr>
            <td><input type="checkbox" name="selected" value="${index}"></td>
            <td><b>${item.plate}</b></td>
            <td>${item.mission}</td>
            <td><span style="color: red;">${item.reason}</span></td>
            <td>${item.issueType}</td>
        </tr>
    `).join('');

    let html = `
    <!DOCTYPE html>
    <html>
    <head>
        <title>Отчет по мониторингу</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            button { padding: 10px 20px; background: #4CAF50; color: white; border: none; cursor: pointer; font-size: 16px; }
        </style>
    </head>
    <body>
        <h2>Отчет об отклонениях</h2>
        <p>Выберите машины для создания заявок:</p>
        <form id="reportForm">
            <table>
                <thead><tr><th>Выбрать</th><th>Госномер</th><th>Задание</th><th>Отклонение</th><th>Тип заявки</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
            <br>
            <button type="button" onclick="sendSelected()">Отправить выбранные заявки</button>
        </form>
        <div id="status" style="margin-top: 20px; font-weight: bold;"></div>
        <script>
            async function sendSelected() {
                const checkboxes = document.querySelectorAll('input[name="selected"]:checked');
                const selectedIndices = Array.from(checkboxes).map(cb => parseInt(cb.value));
                if (selectedIndices.length === 0) return alert("Вы ничего не выбрали!");
                
                document.getElementById('status').innerText = "Отправка... Ожидайте.";
                const response = await fetch('/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ indices: selectedIndices })
                });
                const result = await response.json();
                document.getElementById('status').innerText = result.message;
            }
        </script>
    </body>
    </html>
    `;
    res.send(html);
});

app.post('/submit', async (req, res) => {
    const indices = req.body.indices;
    await pageEstp.bringToFront();
    let successCount = 0;

    for (const index of indices) {
        const car = reportData[index];
        try {
            const vehicleLocator = pageEstp.locator(`text="${car.plate}"`).first();
            await vehicleLocator.waitFor({ state: 'visible', timeout: 5000 });
            await vehicleLocator.click();
            await pageEstp.waitForSelector(CONFIG.btnOpenTicket, { timeout: 5000 });
            
            await pageEstp.click(CONFIG.btnOpenTicket); 
            await pageEstp.waitForSelector(CONFIG.inputEmployee);
            await pageEstp.click(CONFIG.inputEmployee);
            await pageEstp.fill(CONFIG.inputEmployee, ''); 
            await pageEstp.type(CONFIG.inputEmployee, CONFIG.EMPLOYEE_NAME, { delay: 20 }); 
            await pageEstp.waitForTimeout(500); 
            await pageEstp.keyboard.press('Enter'); 
            
            await pageEstp.selectOption(CONFIG.selectIssueType, { label: car.issueType });
            await pageEstp.fill(CONFIG.inputText, `Анализ ЕТС: ${car.reason}`);
            await pageEstp.click(CONFIG.btnSubmit);
            await pageEstp.waitForTimeout(1500); 
            await pageEstp.keyboard.press('Escape'); 
            successCount++;
        } catch (err) {
            console.error(`Ошибка по ${car.plate}:`, err.message);
            await pageEstp.keyboard.press('Escape');
        }
    }
    res.json({ success: true, message: `Успешно создано заявок: ${successCount} из ${indices.length}` });
});

// --- ОСНОВНАЯ ЛОГИКА ---
async function runBot() {
    browser = await chromium.launch({ headless: false }); 
    const contextEts = await browser.newContext();
    pageEts = await contextEts.newPage();
    pageEts.setDefaultTimeout(15000);
    
    const contextEstp = await browser.newContext();
    pageEstp = await contextEstp.newPage();
    pageEstp.setDefaultTimeout(5000);

    // Перехват WebSocket
    let wsData = {};
    pageEts.on('websocket', ws => {
        ws.on('framereceived', event => {
            try {
                const parsed = JSON.parse(event.payload);
                for (const key in parsed) {
                    if (!wsData[key]) wsData[key] = [];
                    wsData[key].push(parsed[key]);
                }
            } catch (e) { }
        });
    });

    try {
        await pageEts.goto(CONFIG.etsLoginUrl); 
        await pageEstp.goto(CONFIG.estpTelemetryUrl);

        console.log('⏳ У ВАС 60 СЕКУНД. Войдите на ОБА сайта.');
        await pageEts.waitForTimeout(60000); 

        // 1. ПОЛУЧАЕМ СПИСОК МАШИН БЕЗ СВЯЗИ
        console.log('\n📡 Запрашиваем список ТС без связи...');
        const noSignalData = await pageEts.evaluate(async () => {
            const res = await fetch('https://ets.mos.ru/services/dashboard/car_in_work_overall?', { credentials: 'include' });
            return await res.json();
        });

        let offlineCars = [];
        if (noSignalData && noSignalData.result && Array.isArray(noSignalData.result.items)) {
            for (const item of noSignalData.result.items) {
                if (item.title.includes('ТС, не передающие сигнал')) {
                    for (const sub of item.subItems) {
                        if (sub.title === 'Не на линии') {
                            offlineCars = sub.subItems.map(s => s.title);
                        }
                    }
                }
            }
        }
        console.log(`🔍 Найдено машин без связи: ${offlineCars.length}`);

        // 2. ПЕРЕХОДИМ К ЖУРНАЛУ ЗАДАНИЙ
        await pageEts.goto(CONFIG.etsMissionsUrl);
        await pageEts.waitForTimeout(3000); 

        try {
            await pageEts.locator('.ant-pagination-options .ant-select-selector').click();
            await pageEts.waitForTimeout(300);
            await pageEts.locator('.ant-select-item-option:has-text("50 / стр.")').click();
            await pageEts.waitForTimeout(2000); 
        } catch (e) {}

        const today = new Date();
        const todayString = `${String(today.getDate()).padStart(2, '0')}.${String(today.getMonth() + 1).padStart(2, '0')}.${today.getFullYear()}`;
        
        console.log(`🔍 Ищем задания за ${todayString}...`);

        const rawCars = await pageEts.evaluate((todayStr) => {
            const results = [];
            document.querySelectorAll('td[id*="car_gov_number"]').forEach(cell => {
                const row = cell.closest('tr');
                if (!row) return;
                const dateCell = row.querySelector('td[id*="date_start"]');
                if (dateCell && dateCell.innerText.trim().startsWith(todayStr) && cell.innerText.trim()) {
                    const opCell = row.querySelector('td[id*="technical_operation_name"]');
                    results.push({ plate: cell.innerText.trim(), mission: opCell ? opCell.innerText.trim() : "Задание" });
                }
            });
            const unique = [];
            const map = new Set();
            results.forEach(item => {
                const key = `${item.plate}|${item.mission}`;
                if (!map.has(key)) { map.add(key); unique.push(item); }
            });
            return unique;
        }, todayString);

        console.log(`✅ Найдено заданий: ${rawCars.length}. Анализируем...`);

        // 3. АНАЛИЗ КАЖДОЙ МАШИНЫ
        for (const car of rawCars) {
            console.log(`   🔎 Анализ: ${car.plate}`);
            
            // Проверка связи (по API)
            if (offlineCars.includes(car.plate)) {
                console.log(`      ⚠️ ОТКЛОНЕНИЕ: Нет связи`);
                reportData.push({ 
                    plate: car.plate, 
                    mission: car.mission, 
                    reason: 'Нет связи (БНСО не передает данные)', 
                    issueType: 'Проведение работ по восстановлению неработающего БНСО' 
                });
                continue;
            }

            // Проверка трека (WebSocket)
            try {
                wsData = {};
                const cellLocator = pageEts.locator(`td[id*="car_gov_number"]:has-text("${car.plate}")`).first();
                const rowLocator = cellLocator.locator('xpath=ancestor::tr').first();
                const infoButton = rowLocator.locator('[id*="showMissionInfo"]').first();
                
                await infoButton.evaluate(node => node.click());
                await pageEts.waitForTimeout(3000); 

                const reason = analyzeWsData(wsData, CONFIG);

                await pageEts.evaluate(() => {
                    const closeBtn = document.querySelector('.modal-content .close, .modal-content button[aria-label="Close"], .ant-modal-close');
                    if (closeBtn) closeBtn.click();
                    else document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));
                });
                await pageEts.waitForTimeout(300);

                if (reason) {
                    console.log(`      ⚠️ ОТКЛОНЕНИЕ: ${reason}`);
                    reportData.push({ plate: car.plate, mission: car.mission, reason, issueType: 'Некорректный трек ТС' });
                } else {
                    console.log(`      ✅ В норме.`);
                }
            } catch (err) {
                console.log(`      ❌ Ошибка: ${err.message}`);
                await pageEts.keyboard.press('Escape');
            }
        }

        console.log(`\n✅ Анализ завершен. Найдено отклонений: ${reportData.length}`);
        
        app.listen(3000, () => {
            console.log('\n🌐 ОТЧЕТ ГОТОВ! Откройте: http://localhost:3000');
        });

    } catch (error) {
        console.error('❌ Критическая ошибка:', error);
        await browser.close();
    }
}

runBot();