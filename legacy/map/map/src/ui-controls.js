import { MACHINES, SUBTYPE_ORDER, STREETS } from './data.js';
import { escAttr } from './utils.js';
import { renderList, getVisibleMachines } from './ui.js';
import { confirmAction } from './dialogs.js';
import { 
  rbRoutesByVehicle, selectedForShow, activeRouteIndex, history, activeUchastok,
  routeFilterActive, setRouteFilterActive, setActiveUchastok, setRbRoutesByVehicle, setActiveRouteIndex, setSelectedForShow,
  setHistory, STORAGE_KEY, undoStack, restoreSnapshot, updateUndoButton,
  activeVehicle, miniRouteVehicle, setActiveVehicle, setMiniRouteVehicle,
  pinnedRouteIndexByVehicle, setPinnedRouteIndexByVehicle
} from './state.js';
import { renderEditorStreets, renderStreetLayer, cancelEditing, persistStreets } from './editor.js';
import { renderRouteTabs, renderMiniRoute, renderPicker, renderRouteOnMap, setPinnedRouteArea, setHoveredRouteArea } from './routes.js';
import { applyMachineOverrides, getMachineOverrides } from './machine-actions.js';

export function toggleSidebar() { document.getElementById('sidebar').classList.toggle('collapsed'); }
export function toggleDropdown(id) { document.getElementById(id).classList.toggle('open'); }
export function toggleTheme() { document.body.classList.toggle('dark'); }

export async function resetAll() {
  if (!await confirmAction('Сбросить все изменения?')) return;
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem('zhilischnik_v45_streets');
  location.reload();
}

export function toggleEditMode() {
  const on = document.body.classList.toggle('edit-mode');
  import('./state.js').then(m => m.setEditMode(on));
  const b = document.getElementById('edit-mode-btn');
  if (b) b.innerHTML = on ? 'Готово' : '✏️ <span>Редактировать</span>';
  const badge = document.getElementById('mode-badge');
  if (badge) {
    badge.className = on ? 'edit' : 'view';
    badge.textContent = on ? '✏️ Редактирование' : '👁 Просмотр';
  }
}

export function openHistory() {
  document.getElementById('editor-panel')?.classList.remove('open');
  document.getElementById('history-panel').classList.add('open');
  renderHistory();
}

function renderHistory() {
  const body = document.getElementById('history-body');
  if (!body) return;
  if (!history || !history.length) {
    body.innerHTML = '<div class="hp-empty">История пуста</div>';
    return;
  }
  body.innerHTML = history.map(h =>
    '<div class="hp-item"><div class="hp-time">' + escAttr(h.time || '') + '</div>' + escAttr(h.action || '') + '</div>'
  ).join('');
}

export function exportCSV() {
  const headers = ['Госномер','Модель','Год','Вид','Категория','Участок','Подтип','Маршрут'];
  const rows = [headers];
  MACHINES.forEach(m => {
    const routes = rbRoutesByVehicle[m.plate] || [];
    const routeStr = routes.map((r, i) => (r && r.items && r.items.length) ? ('М' + (i + 1) + ':' + r.items.length) : '').filter(Boolean).join(' | ');
    rows.push([m.plate, m.model || '', m.year || '', m.vid || '', m.cat_b || '', m.area || '', m.subtype || '', routeStr]);
  });
  const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'karta-tehniki-' + new Date().toISOString().slice(0, 10) + '.csv';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
  toast('CSV экспортирован', 'success');
}

export async function exportHTML() {
  try {
    let html = window.__SINGLE_FILE_TEMPLATE__;
    if (!html) {
      html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
    }
    const data = {
      rbRoutesByVehicle,
      streets: STREETS.map(({ _layer, ...s }) => s),
      selectedForShow: Array.from(selectedForShow),
      activeRouteIndex,
      pinnedRouteIndexByVehicle,
      history: history || [],
      activeUchastok,
      machineOverrides: getMachineOverrides(),
      subtypeOrder: SUBTYPE_ORDER
    };
    const inject = '<script>window.__EMBEDDED_DATA__ = ' +
      JSON.stringify(data).replace(/</g, '\\u003c') + ';</' + 'script>';
    html = html.replace('</body>', inject + '</body>');

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'karta_tehniki_' + new Date().toISOString().slice(0, 10) + '.html';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 200);
    toast('HTML-файл сохранён', 'success');
  } catch (err) {
    toast('Ошибка экспорта: ' + err.message, 'error');
  }
}

let onboardingStep = 0;
function renderOnboarding() {
  const steps = document.querySelectorAll('#onboarding .ob-step');
  steps.forEach((el, i) => el.classList.toggle('active', i === onboardingStep));
  document.querySelectorAll('#ob-dots span').forEach((el, i) => el.classList.toggle('active', i === onboardingStep));
  document.getElementById('ob-prev').style.display = onboardingStep ? '' : 'none';
  document.getElementById('ob-next').textContent = onboardingStep === steps.length - 1 ? 'Готово' : 'Далее →';
}
export function startOnboarding() {
  onboardingStep = 0;
  renderOnboarding();
  document.getElementById('onboarding-overlay').classList.add('open');
}
export function onboardingPrev() { onboardingStep = Math.max(0, onboardingStep - 1); renderOnboarding(); }
export function onboardingNext() {
  if (onboardingStep >= document.querySelectorAll('#onboarding .ob-step').length - 1) {
    document.getElementById('onboarding-overlay').classList.remove('open');
  } else { onboardingStep++; renderOnboarding(); }
}
export function printRoutes() {
  const area = document.getElementById('print-area');
  if (!area) return;

  const now = new Date();
  const dateStr = now.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });

  let html = '<h1>Сводка маршрутов</h1>';
  html += '<p style="font-size:12px;color:#566573;margin-bottom:10px;">Дата: ' + escAttr(dateStr) + ' · Всего транспорта: ' + MACHINES.length + '</p>';
  html += '<table><thead><tr><th>Госномер</th><th>Модель</th><th>Маршруты</th></tr></thead><tbody>';

  MACHINES.forEach(m => {
    const routes = rbRoutesByVehicle[m.plate] || [];
    const hasRoutes = routes.some(r => r && r.items && r.items.length > 0);
    if (!hasRoutes) return;

    const routeParts = routes
      .map((r, i) => {
        if (!r || !r.items || !r.items.length) return '';
        const name = r.name || ('М' + (i + 1));
        const count = r.items.length;
        const names = r.items.map(s => escAttr(s.name || '')).join(', ');
        return name + ' (' + count + ' пунктов): ' + names;
      })
      .filter(Boolean)
      .join(' | ');

    html += '<tr>' +
      '<td>' + escAttr(m.plate || '') + '</td>' +
      '<td>' + escAttr(m.model || '') + '</td>' +
      '<td>' + routeParts + '</td>' +
      '</tr>';
  });

  html += '</tbody></table>';
  area.innerHTML = html;
  window.print();
}

export function undoLastAction() {
  if (undoStack.length === 0) {
    toast('Нечего отменять', 'info');
    return;
  }
  const entry = undoStack.pop();
  try {
    restoreSnapshot(entry.snap);
    renderList();
    
    import('./editor.js').then(m => {
      m.renderStreetLayer(); 
      m.renderEditorStreets();
    });
    
    if (miniRouteVehicle) {
      renderRouteTabs();
      renderMiniRoute();
      renderPicker();
    }
    renderRouteOnMap();
    persistStreets();
    saveData(false);
    toast('Отменено: ' + (entry.label || 'действие'), 'success');
  } catch (e) {
    console.error('undo error:', e);
    toast('Ошибка отмены', 'error');
  } finally {
    updateUndoButton();
  }
}

export function toggleExpandSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.toggle('expanded');
}

export function toggleRouteFilter() {
  const btn = document.getElementById('on-route-count');
  setRouteFilterActive(!routeFilterActive);
  btn?.classList.toggle('active', routeFilterActive);
  btn?.setAttribute('aria-pressed', String(routeFilterActive));
  renderList();
}

export function clearMachineFilters() {
  setRouteFilterActive(false);
  setActiveUchastok(null);
  setPinnedRouteArea(null);
  document.getElementById('on-route-count')?.classList.remove('active');
  document.getElementById('on-route-count')?.setAttribute('aria-pressed', 'false');
  document.querySelectorAll('.uch-btn').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
  renderList();
  renderRouteOnMap();
}

// Переключатель наложений скрыт до реализации отрисовки маршрутов на карте.

export function selectUchastok(num) {
  const btn = document.querySelector(`.uch-btn[data-u="${num}"]`);
  if (!btn) return;
  if (activeUchastok === num) {
    setActiveUchastok(null);
  } else {
    setActiveUchastok(num);
  }
  setPinnedRouteArea(activeUchastok === null ? null : activeUchastok + 'уч');
  setHoveredRouteArea(null);
  document.getElementById('search').value = '';
  setRouteFilterActive(false);
  document.getElementById('on-route-count')?.classList.remove('active');
  document.getElementById('on-route-count')?.setAttribute('aria-pressed', 'false');
  document.querySelectorAll('.uch-btn').forEach(b => { b.classList.toggle('active', Number(b.dataset.u) === activeUchastok); b.setAttribute('aria-pressed', String(Number(b.dataset.u) === activeUchastok)); });
  renderList();
  saveData(false);
}

export function toggleLegend() {
  const legend = document.getElementById('legend');
  if (legend) legend.classList.toggle('open');
}

export function toggleSelectAll() {
  const visible = getVisibleMachines();
  const select = visible.some(m => !selectedForShow.has(m.plate));
  visible.forEach(m => { if (select) selectedForShow.add(m.plate); else selectedForShow.delete(m.plate); });
  renderList();
  saveData(false);
}

export function toggleForShow(plate) {
  if (selectedForShow.has(plate)) selectedForShow.delete(plate);
  else selectedForShow.add(plate);
  renderList();
  saveData(false);
}

export function saveData(showIndicator = false) {
  try {
    const data = {
      rbRoutesByVehicle: rbRoutesByVehicle,
      selectedForShow: Array.from(selectedForShow),
      activeRouteIndex: activeRouteIndex,
      pinnedRouteIndexByVehicle,
      history: history || [],
      activeUchastok: activeUchastok,
      machineOverrides: getMachineOverrides(),
      subtypeOrder: SUBTYPE_ORDER
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    if (showIndicator) toast('Сохранено', 'success');
    return true;
  } catch (e) {
    toast('Ошибка сохранения: ' + e.message, 'error');
    return false;
  }
}

export function loadData() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      if (data.rbRoutesByVehicle) setRbRoutesByVehicle(data.rbRoutesByVehicle);
      if (data.selectedForShow) setSelectedForShow(new Set(data.selectedForShow));
      if (typeof data.activeRouteIndex === 'number') setActiveRouteIndex(data.activeRouteIndex);
      if (data.pinnedRouteIndexByVehicle) setPinnedRouteIndexByVehicle(data.pinnedRouteIndexByVehicle);
      if (data.history) setHistory(data.history);
      // A persisted list filter must not unexpectedly hide machines on every tab.
      applyMachineOverrides(data);
      return;
    }
    if (window.__EMBEDDED_DATA__) {
      const d = window.__EMBEDDED_DATA__;
      if (Array.isArray(d.streets) && !localStorage.getItem('zhilischnik_v45_streets')) {
        localStorage.setItem('zhilischnik_v45_streets', JSON.stringify({ streets: d.streets }));
      }
      if (d.rbRoutesByVehicle) setRbRoutesByVehicle(d.rbRoutesByVehicle);
      if (d.selectedForShow) setSelectedForShow(new Set(d.selectedForShow));
      if (typeof d.activeRouteIndex === 'number') setActiveRouteIndex(d.activeRouteIndex);
      if (d.pinnedRouteIndexByVehicle) setPinnedRouteIndexByVehicle(d.pinnedRouteIndexByVehicle);
      if (d.history) setHistory(d.history);
      applyMachineOverrides(d);
    }
  } catch (e) {
    console.warn("loadData error:", e);
  }
}

function toast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast ' + (type || '');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}