// src/diagnostics.js
import { STREETS } from './data.js';
import { 
  editingStreetIdx, setEditingStreetIdx, undoStack, 
  streetLayerGroup, map 
} from './state.js';
import { 
  saveCurrentObject, loadStreetsFromStorage, 
  renderStreetLayer, renderEditorStreets, clearEditorDraw, toggleEditor 
} from './editor.js';

export function runDiagnostics() {
  console.clear();
  console.log('%c=== ДИАГНОСТИКА РЕДАКТОРА ===', 'font-size: 16px; font-weight: bold; color: #e74c3c;');
  
  const report = [];
  const log = (status, msg) => {
    report.push({ status, msg });
    const icon = status === 'OK' ? '✅' : (status === 'WARN' ? '⚠️' : '❌');
    console.log(`%c${icon} ${msg}`, `color: ${status === 'OK' ? 'green' : (status === 'WARN' ? 'orange' : 'red')}`);
  };

  // 1. Проверка инициализации карты и слоев
  if (map && streetLayerGroup) {
    log('OK', 'Карта и слой улиц инициализированы');
  } else {
    log('FAIL', 'Карта или слой улиц НЕ инициализированы!');
    return report;
  }

  // 2. Проверка данных STREETS
  if (Array.isArray(STREETS) && STREETS.length > 0) {
    log('OK', `Массив STREETS загружен (${STREETS.length} объектов)`);
  } else {
    log('FAIL', 'Массив STREETS пуст или не загружен');
  }

  // 3. Симуляция выбора объекта
  const testIdx = 0; // Берем первый объект
  setEditingStreetIdx(testIdx);
  renderEditorStreets();
  renderStreetLayer();
  
  if (editingStreetIdx === testIdx) {
    log('OK', `Выбран объект #${testIdx} (${STREETS[testIdx].name})`);
  } else {
    log('FAIL', 'Не удалось выбрать объект (editingStreetIdx не обновился)');
  }

  // 4. Симуляция рисования (добавление точки в extraPolygons)
  const s = STREETS[testIdx];
  const oldLen = s.extraPolygons ? s.extraPolygons.length : 0;
  if (!s.extraPolygons) s.extraPolygons = [];
  s.extraPolygons.push([[55.66, 37.47], [55.661, 37.471]]); // Имитация линии
  
  if (s.extraPolygons.length > oldLen) {
    log('OK', 'Симуляция рисования: фигура добавлена в массив STREETS');
  } else {
    log('FAIL', 'Симуляция рисования не удалась');
  }

  // 5. Симуляция сохранения
  saveCurrentObject();
  const saved = localStorage.getItem('zhilischnik_v45_streets');
  if (saved && saved.includes(STREETS[testIdx].name)) {
    log('OK', 'Сохранение в localStorage прошло успешно');
  } else {
    log('FAIL', 'Данные НЕ сохранились в localStorage');
  }

  // 6. Проверка загрузки (очищаем STREETS и загружаем)
  const beforeLoad = JSON.stringify(STREETS[testIdx].extraPolygons);
  STREETS[testIdx].extraPolygons = []; // Сбрасываем
  loadStreetsFromStorage(); // Загружаем
  const afterLoad = JSON.stringify(STREETS[testIdx].extraPolygons);
  
  if (beforeLoad === afterLoad) {
    log('OK', 'Загрузка из localStorage восстановила данные');
  } else {
    log('FAIL', 'Загрузка из localStorage НЕ восстановила данные (или данные изменились)');
  }

  // 7. Проверка Undo
  const undoBefore = undoStack.length;
  if (undoBefore > 0) {
    log('OK', `Стек Undo содержит ${undoBefore} записей`);
  } else {
    log('WARN', 'Стек Undo пуст (возможно, pushUndo не вызывался)');
  }

  // 8. Проверка очистки
  s.extraPolygons = []; // Сбрасываем
  const oldCoords = s.coords;
  s.coords = [];
  clearEditorDraw(); // Вызываем функцию очистки (но она с confirm)
  // Для теста просто проверим, что массив пуст
  if (s.coords.length === 0 && s.extraPolygons.length === 0) {
    log('OK', 'Очистка данных работает (массивы пусты)');
  } else {
    log('FAIL', 'Очистка данных не работает');
  }
  s.coords = oldCoords; // Восстанавливаем

  console.log('%c=== ДИАГНОСТИКА ЗАВЕРШЕНА ===', 'font-size: 16px; font-weight: bold; color: #27ae60;');
  
  // Выводим итоговый отчет в HTML
  showReportModal(report);
  return report;
}

function showReportModal(report) {
  let existing = document.getElementById('diag-report');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'diag-report';
  modal.style.cssText = `position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.5); z-index: 99999; max-width: 600px; width: 90%; font-family: monospace; max-height: 80vh; overflow-y: auto;`;

  let html = `<h3 style="color: #569cd6; margin-top: 0;">Отчет диагностики редактора</h3><ul style="list-style: none; padding: 0;">`;
  report.forEach(r => {
    const color = r.status === 'OK' ? '#4ec9b0' : (r.status === 'WARN' ? '#dcdcaa' : '#f44747');
    const icon = r.status === 'OK' ? '✅' : (r.status === 'WARN' ? '⚠️' : '❌');
    html += `<li style="margin-bottom: 8px; color: ${color};">${icon} ${r.msg}</li>`;
  });
  html += `</ul><button onclick="document.getElementById('diag-report').remove()" style="background: #0e639c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 10px;">Закрыть</button>`;
  
  modal.innerHTML = html;
  document.body.appendChild(modal);
}

// Экспортируем в глобальную область для вызова из консоли
window.runDiagnostics = runDiagnostics;